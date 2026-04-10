import uuid
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .skyclient import SkyClient
from .skyconfig import config
from .skymetadata import SkyMetadata
from .skyacl import SkyACL


class MigrationTask:
    def __init__(
        self,
        migration_id: str,
        source_client: SkyClient,
        target_client: SkyClient,
        source_bucket: str,
        target_bucket: str,
        source_prefix: str = "",
        target_prefix: str = "",
        threads: int = 10,
        part_size: int = 8,
        storage_class: Optional[str] = None,
        preserve_metadata: bool = True,
        preserve_acl: bool = True,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None
    ):
        self.migration_id = migration_id
        self.source_client = source_client
        self.target_client = target_client
        self.source_bucket = source_bucket
        self.target_bucket = target_bucket
        self.source_prefix = source_prefix
        self.target_prefix = target_prefix
        self.threads = threads
        self.part_size = part_size
        self.storage_class = storage_class
        self.preserve_metadata = preserve_metadata
        self.preserve_acl = preserve_acl
        self.exclude_patterns = exclude_patterns or []
        self.include_patterns = include_patterns or []

        self.metadata_handler = SkyMetadata(source_client)
        self.acl_handler = SkyACL(source_client)
        self.target_metadata_handler = SkyMetadata(target_client)
        self.target_acl_handler = SkyACL(target_client)

        self.status = "pending"
        self.start_time = None
        self.end_time = None
        self.total_objects = 0
        self.processed_objects = 0
        self.failed_objects = 0
        self.total_bytes = 0
        self.transferred_bytes = 0
        self.failed_list = []
        self.checkpoint_file = Path.home() / ".skycli" / "checkpoints" / f"{migration_id}.json"

    def _should_include(self, key: str) -> bool:
        import fnmatch

        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False

        if self.include_patterns:
            for pattern in self.include_patterns:
                if fnmatch.fnmatch(key, pattern):
                    return True
            return False

        return True

    def _load_checkpoint(self) -> Optional[Dict]:
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_checkpoint(self):
        checkpoint_dir = self.checkpoint_file.parent
        if not checkpoint_dir.exists():
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_data = {
            "migration_id": self.migration_id,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "processed_keys": [item["key"] for item in self.failed_list],
            "status": self.status,
            "total_objects": self.total_objects,
            "processed_objects": self.processed_objects,
            "failed_objects": self.failed_objects
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

    def _migrate_object(self, obj: Dict) -> Dict:
        source_key = obj["Key"]
        if not self._should_include(source_key):
            return {"key": source_key, "success": True, "skipped": True}

        target_key = self.target_prefix + source_key[len(self.source_prefix):] if self.source_prefix else self.target_prefix + source_key

        try:
            if obj.get("Size", 0) > 5 * 1024 * 1024:
                self._upload_multipart(obj, target_key)
            else:
                self._upload_single(obj, target_key)

            if self.preserve_acl:
                try:
                    self.acl_handler.copy(
                        self.source_bucket, source_key,
                        self.target_bucket, target_key,
                        obj.get("VersionId")
                    )
                except Exception as e:
                    return {"key": source_key, "target_key": target_key, "success": True, "acl_warning": str(e)}

            return {"key": source_key, "target_key": target_key, "success": True}

        except Exception as e:
            return {"key": source_key, "target_key": target_key, "success": False, "error": str(e)}

    def _upload_single(self, obj: Dict, target_key: str):
        response = self.source_client.get_object(self.source_bucket, obj["Key"])
        body = response["Body"].read()

        metadata = None
        if self.preserve_metadata:
            info = self.source_client.head_object(self.source_bucket, obj["Key"])
            metadata = info.get("Metadata", {})
            content_type = info.get("ContentType")
            cache_control = info.get("CacheControl")
        else:
            metadata = {}

        self.target_client.put_object(
            bucket=self.target_bucket,
            key=target_key,
            body=body,
            metadata=metadata,
            content_type=content_type if self.preserve_metadata else None,
            cache_control=cache_control if self.preserve_metadata else None,
            storage_class=self.storage_class or obj.get("StorageClass", "STANDARD")
        )

    def _upload_multipart(self, obj: Dict, target_key: str):
        import hashlib

        source_response = self.source_client.get_object(self.source_bucket, obj["Key"])
        body = source_response["Body"].read()

        content_md5 = hashlib.md5(body).hexdigest()

        metadata = {}
        if self.preserve_metadata:
            info = self.source_client.head_object(self.source_bucket, obj["Key"])
            metadata = info.get("Metadata", {})

        self.target_client.put_object(
            bucket=self.target_bucket,
            key=target_key,
            body=body,
            metadata=metadata,
            content_type=info.get("ContentType") if self.preserve_metadata else None,
            storage_class=self.storage_class or obj.get("StorageClass", "STANDARD")
        )

    def run(self, progress_callback: Optional[Callable] = None, resume: bool = False) -> Dict:
        self.start_time = datetime.now()
        self.status = "running"

        checkpoint = self._load_checkpoint() if resume else None
        processed_keys = set(checkpoint.get("processed_keys", [])) if checkpoint else set()

        objects = list(self.source_client.list_objects_all(self.source_bucket, self.source_prefix))
        self.total_objects = len(objects)
        self.total_bytes = sum(obj.get("Size", 0) for obj in objects)

        for obj in objects:
            if obj["Key"] in processed_keys:
                self.processed_objects += 1
                continue

        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._migrate_object, obj): obj for obj in objects}

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                self.processed_objects += 1
                if result.get("success") and not result.get("skipped"):
                    self.transferred_bytes += futures[future].get("Size", 0)
                elif not result.get("success"):
                    self.failed_objects += 1
                    self.failed_list.append(result)

                if progress_callback:
                    progress_callback({
                        "processed": self.processed_objects,
                        "total": self.total_objects,
                        "failed": self.failed_objects,
                        "current": result
                    })

                self._save_checkpoint()

        self.status = "completed" if self.failed_objects == 0 else "completed_with_errors"
        self.end_time = datetime.now()

        return self.get_summary()

    def get_summary(self) -> Dict:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "migration_id": self.migration_id,
            "status": self.status,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "total_objects": self.total_objects,
            "processed_objects": self.processed_objects,
            "failed_objects": self.failed_objects,
            "total_bytes": self.total_bytes,
            "transferred_bytes": self.transferred_bytes,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "failed_list": self.failed_list[:100]
        }

    def cancel(self):
        self.status = "cancelled"
        self.end_time = datetime.now()
        self._save_checkpoint()


def create_migration(
    source_config_name: str,
    source_bucket: str,
    target_config_name: str,
    target_bucket: str,
    source_prefix: str = "",
    target_prefix: str = "",
    threads: int = 10,
    part_size: int = 8,
    storage_class: Optional[str] = None,
    preserve_metadata: bool = True,
    preserve_acl: bool = True,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    profile: Optional[str] = None
) -> MigrationTask:
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
        verify_ssl=source_config.get("verify_ssl", True)
    )

    target_client = SkyClient(
        endpoint=target_config["endpoint"],
        access_key=target_config["access_key"],
        secret_key=target_config["secret_key"],
        region=target_config.get("region", "us-east-1"),
        use_path_style=target_config.get("use_path_style", False),
        verify_ssl=target_config.get("verify_ssl", True)
    )

    migration_id = f"mig-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    return MigrationTask(
        migration_id=migration_id,
        source_client=source_client,
        target_client=target_client,
        source_bucket=source_bucket,
        target_bucket=target_bucket,
        source_prefix=source_prefix,
        target_prefix=target_prefix,
        threads=threads,
        part_size=part_size,
        storage_class=storage_class,
        preserve_metadata=preserve_metadata,
        preserve_acl=preserve_acl,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns
    )


def get_migration_history() -> List[Dict]:
    checkpoint_dir = Path.home() / ".skycli" / "checkpoints"
    if not checkpoint_dir.exists():
        return []

    migrations = []
    for file in checkpoint_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            migrations.append(data)

    return sorted(migrations, key=lambda x: x.get("end_time", ""), reverse=True)


def get_migration(migration_id: str) -> Optional[Dict]:
    checkpoint_file = Path.home() / ".skycli" / "checkpoints" / f"{migration_id}.json"
    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
