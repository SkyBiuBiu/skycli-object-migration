import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .skyclient import SkyClient
from .skyconfig import config
from .skymetadata import SkyMetadata
from .skyacl import SkyACL


class ValidationTask:
    def __init__(
        self,
        validation_id: str,
        source_client: SkyClient,
        target_client: SkyClient,
        source_bucket: str,
        target_bucket: str,
        prefix: str = "",
        check_content: bool = True,
        check_metadata: bool = True,
        check_acl: bool = True,
        metadata_fields: Optional[List[str]] = None,
        threads: int = 10
    ):
        self.validation_id = validation_id
        self.source_client = source_client
        self.target_client = target_client
        self.source_bucket = source_bucket
        self.target_bucket = target_bucket
        self.prefix = prefix
        self.check_content = check_content
        self.check_metadata = check_metadata
        self.check_acl = check_acl
        self.metadata_fields = metadata_fields
        self.threads = threads

        self.status = "pending"
        self.start_time = None
        self.end_time = None
        self.total_objects = 0
        self.processed_count = 0
        self.content_passed = 0
        self.metadata_passed = 0
        self.acl_passed = 0
        self.failed = 0
        self.failed_objects = []
        self.report_file = Path.home() / ".skycli" / "validation-reports" / f"{validation_id}.json"

    def _get_source_objects(self) -> List[Dict]:
        return list(self.source_client.list_objects_all(self.source_bucket, self.prefix))

    def _validate_object(self, obj: Dict) -> Dict:
        source_key = obj["Key"]
        source_version_id = obj.get("VersionId")

        target_key = source_key

        try:
            target_head = self.target_client.head_object(self.target_bucket, target_key)
        except Exception as e:
            return {
                "key": source_key,
                "success": False,
                "errors": [f"Target object not found: {str(e)}"]
            }

        errors = []
        content_ok = True
        metadata_ok = True
        acl_ok = True

        if self.check_content:
            content_result = self._check_content(source_key, target_key, obj.get("Size", 0))
            if not content_result["match"]:
                content_ok = False
                errors.append(f"content_mismatch: {content_result.get('reason', 'unknown')}")

        if self.check_metadata:
            metadata_result = self._check_metadata(source_key, target_key, source_version_id)
            if not metadata_result["match"]:
                metadata_ok = False
                for field, info in metadata_result.get("differences", {}).items():
                    if not info.get("match", True):
                        errors.append(f"metadata_mismatch: {field}")

        if self.check_acl:
            acl_result = self._check_acl(source_key, target_key, source_version_id)
            if not acl_result["match"]:
                acl_ok = False
                errors.append("acl_mismatch")

        return {
            "key": source_key,
            "target_key": target_key,
            "success": content_ok and metadata_ok and acl_ok,
            "content_ok": content_ok,
            "metadata_ok": metadata_ok,
            "acl_ok": acl_ok,
            "errors": errors
        }

    def _check_content(self, source_key: str, target_key: str, source_size: int) -> Dict:
        try:
            source_head = self.source_client.head_object(self.source_bucket, source_key)
            target_head = self.target_client.head_object(self.target_bucket, target_key)

            if source_head.get("ContentLength") != target_head.get("ContentLength"):
                return {
                    "match": False,
                    "reason": f"Size mismatch: source={source_head.get('ContentLength')}, target={target_head.get('ContentLength')}"
                }

            source_etag = source_head.get("ETag", "").strip('"')
            target_etag = target_head.get("ETag", "").strip('"')

            if source_etag and target_etag and source_etag != target_etag:
                return {
                    "match": False,
                    "reason": f"ETag mismatch: source={source_etag}, target={target_etag}"
                }

            if source_size > 5 * 1024 * 1024:
                return {"match": True}

            source_response = self.source_client.get_object(self.source_bucket, source_key)
            source_data = source_response["Body"].read()
            source_md5 = hashlib.md5(source_data).hexdigest()

            target_response = self.target_client.get_object(self.target_bucket, target_key)
            target_data = target_response["Body"].read()
            target_md5 = hashlib.md5(target_data).hexdigest()

            if source_md5 != target_md5:
                return {
                    "match": False,
                    "reason": f"MD5 mismatch: source={source_md5}, target={target_md5}"
                }

            return {"match": True}

        except Exception as e:
            return {"match": False, "reason": str(e)}

    def _check_metadata(self, source_key: str, target_key: str, source_version_id: Optional[str] = None) -> Dict:
        try:
            source_metadata_handler = SkyMetadata(self.source_client)
            target_metadata_handler = SkyMetadata(self.target_client)

            source_meta = source_metadata_handler.get(self.source_bucket, source_key, source_version_id)
            target_meta = target_metadata_handler.get(self.target_bucket, target_key)

            fields = self.metadata_fields or ["ContentType", "ContentLength", "CacheControl", "Expires", "Metadata"]

            return source_metadata_handler.compare(source_meta, target_meta, fields)

        except Exception as e:
            return {"match": False, "reason": str(e)}

    def _check_acl(self, source_key: str, target_key: str, source_version_id: Optional[str] = None) -> Dict:
        try:
            source_acl_handler = SkyACL(self.source_client)
            target_acl_handler = SkyACL(self.target_client)

            source_acl = source_acl_handler.get(self.source_bucket, source_key, source_version_id)
            target_acl = target_acl_handler.get(self.target_bucket, target_key)

            return source_acl_handler.compare(source_acl, target_acl)

        except Exception as e:
            return {"match": False, "reason": str(e)}

    def run(self, progress_callback: Optional[Callable] = None) -> Dict:
        self.start_time = datetime.now()
        self.status = "running"

        objects = self._get_source_objects()
        self.total_objects = len(objects)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._validate_object, obj): obj for obj in objects}

            for future in as_completed(futures):
                result = future.result()
                self.processed_count += 1

                if result.get("content_ok", False):
                    self.content_passed += 1
                if result.get("metadata_ok", False):
                    self.metadata_passed += 1
                if result.get("acl_ok", False):
                    self.acl_passed += 1

                if not result.get("success", False):
                    self.failed += 1
                    self.failed_objects.append(result)

                if progress_callback:
                    progress_callback({
                        "total": self.total_objects,
                        "processed": self.processed_count,
                        "failed": self.failed
                    })

        self.status = "completed"
        self.end_time = datetime.now()
        self._save_report()

        return self.get_report()

    def _save_report(self):
        report_dir = self.report_file.parent
        if not report_dir.exists():
            report_dir.mkdir(parents=True, exist_ok=True)

        report_data = self.get_report()

        with open(self.report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

    def get_report(self) -> Dict:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "validation_id": self.validation_id,
            "timestamp": datetime.now().isoformat(),
            "status": self.status,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "prefix": self.prefix,
            "check_content": self.check_content,
            "check_metadata": self.check_metadata,
            "check_acl": self.check_acl,
            "summary": {
                "total_objects": self.total_objects,
                "content_passed": self.content_passed,
                "content_failed": self.total_objects - self.content_passed,
                "metadata_passed": self.metadata_passed if self.check_metadata else 0,
                "metadata_failed": self.total_objects - self.metadata_passed if self.check_metadata else 0,
                "metadata_skipped": self.total_objects if not self.check_metadata else 0,
                "acl_passed": self.acl_passed if self.check_acl else 0,
                "acl_failed": self.total_objects - self.acl_passed if self.check_acl else 0,
                "acl_skipped": self.total_objects if not self.check_acl else 0
            },
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "failed_objects": self.failed_objects[:100]
        }


def create_validation(
    source_config_name: str,
    source_bucket: str,
    target_config_name: str,
    target_bucket: str,
    prefix: str = "",
    check_content: bool = True,
    check_metadata: bool = True,
    check_acl: bool = True,
    metadata_fields: Optional[List[str]] = None,
    threads: int = 10,
    profile: Optional[str] = None
) -> ValidationTask:
    source_config = config.get_profile(source_config_name, profile)
    target_config = config.get_profile(target_config_name, profile)

    if not source_config:
        raise ValueError(f"Source config '{source_config_name}' not found")
    if not target_config:
        raise ValueError(f"Target config '{target_config_name}' not found")

    source_client = SkyClient(
        endpoint=source_config["endpoint"],
        access_key=source_config["access_key"],
        secret_key=source_config["secret_key"],
        region=source_config.get("region", "us-east-1"),
        use_path_style=source_config.get("use_path_style", False),
        verify_ssl=source_config.get("verify_ssl", True),
        signature_version=source_config.get("signature_version", "s3v4")
    )

    target_client = SkyClient(
        endpoint=target_config["endpoint"],
        access_key=target_config["access_key"],
        secret_key=target_config["secret_key"],
        region=target_config.get("region", "us-east-1"),
        use_path_style=target_config.get("use_path_style", False),
        verify_ssl=target_config.get("verify_ssl", True),
        signature_version=target_config.get("signature_version", "s3v4")
    )

    validation_id = f"val-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return ValidationTask(
        validation_id=validation_id,
        source_client=source_client,
        target_client=target_client,
        source_bucket=source_bucket,
        target_bucket=target_bucket,
        prefix=prefix,
        check_content=check_content,
        check_metadata=check_metadata,
        check_acl=check_acl,
        metadata_fields=metadata_fields,
        threads=threads
    )


def get_validation_report(validation_id: str) -> Optional[Dict]:
    report_file = Path.home() / ".skycli" / "validation-reports" / f"{validation_id}.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def list_validation_reports() -> List[Dict]:
    report_dir = Path.home() / ".skycli" / "validation-reports"
    if not report_dir.exists():
        return []

    reports = []
    for file in report_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            reports.append(data)

    return sorted(reports, key=lambda x: x.get("timestamp", ""), reverse=True)
