import uuid
import json
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .skyclient import SkyClient
from .skyconfig import config
from .skymetadata import SkyMetadata
from .skyacl import SkyACL


class SyncTask:
    def __init__(
        self,
        sync_id: str,
        source_client: SkyClient,
        target_client: SkyClient,
        source_bucket: str,
        target_bucket: str,
        source_prefix: str = "",
        target_prefix: str = "",
        since: Optional[datetime] = None,
        since_last_sync: bool = False,
        delete: bool = False,
        threads: int = 10,
        part_size: int = 8,
        storage_class: Optional[str] = None,
        preserve_metadata: bool = True,
        preserve_acl: bool = True,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None
    ):
        self.sync_id = sync_id
        self.source_client = source_client
        self.target_client = target_client
        self.source_bucket = source_bucket
        self.target_bucket = target_bucket
        self.source_prefix = source_prefix
        self.target_prefix = target_prefix
        self.since = since
        self.since_last_sync = since_last_sync
        self.delete = delete
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
        self.uploaded = 0
        self.deleted = 0
        self.skipped = 0
        self.failed = 0
        self.total_bytes = 0
        self.transferred_bytes = 0
        self.failed_objects = 0
        self.failed_list = []

        self.state_file = Path.home() / ".skycli" / "sync-state" / f"{sync_id}.json"
        self.checkpoint_file = Path.home() / ".skycli" / "checkpoints" / f"{sync_id}.json"

    def _should_include(self, key: str) -> bool:
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False

        if self.include_patterns:
            for pattern in self.include_patterns:
                if fnmatch.fnmatch(key, pattern):
                    return True
            return False

        return True

    def _load_last_sync_time(self) -> Optional[datetime]:
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_sync = data.get("last_sync_time")
                if last_sync:
                    return datetime.fromisoformat(last_sync)
        return None

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
            "sync_id": self.sync_id,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "processed_keys": list(set(item["key"] for item in self.failed_list)),
            "status": self.status,
            "total_objects": self.total_objects,
            "processed_objects": self.processed_objects,
            "uploaded": self.uploaded,
            "deleted": self.deleted,
            "failed": self.failed,
            "skipped": self.skipped
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

    def _save_state(self):
        state_dir = self.state_file.parent
        if not state_dir.exists():
            state_dir.mkdir(parents=True, exist_ok=True)

        state_data = {
            "sync_id": self.sync_id,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "last_sync_time": datetime.now().isoformat(),
            "status": self.status
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    def _get_objects_since(self, since: datetime) -> List[Dict]:
        objects = []
        for obj in self.source_client.list_objects_all(self.source_bucket, self.source_prefix):
            last_modified = obj.get("LastModified")
            if last_modified:
                if isinstance(last_modified, str):
                    from dateutil import parser
                    last_modified = parser.parse(last_modified)

            if last_modified and last_modified >= since:
                objects.append(obj)

        return objects

    def _get_target_objects(self) -> Dict[str, Dict]:
        target_objects = {}
        for obj in self.target_client.list_objects_all(self.target_bucket, self.target_prefix):
            key_without_prefix = obj["Key"][len(self.target_prefix):] if self.target_prefix else obj["Key"]
            target_objects[key_without_prefix] = obj
        return target_objects

    def _should_sync(self, source_obj: Dict, target_objects: Dict[str, Dict]) -> bool:
        source_key = source_obj["Key"]
        source_key_without_prefix = source_key[len(self.source_prefix):] if self.source_prefix else source_key

        if source_key_without_prefix not in target_objects:
            return True

        source_etag = source_obj.get("ETag", "").strip('"')
        target_obj = target_objects[source_key_without_prefix]
        target_etag = target_obj.get("ETag", "").strip('"')

        if source_etag != target_etag:
            return True

        source_size = source_obj.get("Size", 0)
        target_size = target_obj.get("Size", 0)
        if source_size != target_size:
            return True

        return False

    def _migrate_object(self, obj: Dict):
        source_key = obj["Key"]
        target_key = self.target_prefix + source_key[len(self.source_prefix):] if self.source_prefix else self.target_prefix + source_key

        if not self._should_include(target_key):
            return {"success": True, "skipped": True, "key": source_key, "reason": "filtered"}

        response = self.source_client.get_object(self.source_bucket, source_key)
        body = response["Body"].read()

        metadata = {}
        content_type = None
        cache_control = None

        if self.preserve_metadata:
            info = self.source_client.head_object(self.source_bucket, source_key)
            metadata = info.get("Metadata", {})
            content_type = info.get("ContentType")
            cache_control = info.get("CacheControl")

        storage_cls = self.storage_class or obj.get("StorageClass", "STANDARD")

        self.target_client.put_object(
            bucket=self.target_bucket,
            key=target_key,
            body=body,
            metadata=metadata,
            content_type=content_type,
            cache_control=cache_control,
            storage_class=storage_cls
        )

        if self.preserve_acl:
            try:
                self.acl_handler.copy(self.source_bucket, source_key, self.target_bucket, target_key)
            except Exception:
                pass

        return {"success": True, "key": source_key, "target_key": target_key}

    def _sync_object(self, obj: Dict):
        result = self._migrate_object(obj)
        if result.get("success") and not result.get("skipped"):
            self.uploaded += 1
        elif result.get("skipped"):
            self.skipped += 1

    def _sync_delete(self, target_objects: Dict[str, Dict], source_objects: List[Dict]):
        source_keys = set()
        for obj in source_objects:
            key_without_prefix = obj["Key"][len(self.source_prefix):] if self.source_prefix else obj["Key"]
            source_keys.add(key_without_prefix)

        for target_key, target_obj in target_objects.items():
            if target_key not in source_keys:
                try:
                    self.target_client.delete_object(self.target_bucket, target_key)
                    self.deleted += 1
                except Exception as e:
                    self.failed += 1

    def run(self, progress_callback: Optional[Callable] = None, resume: bool = False) -> Dict:
        self.start_time = datetime.now()
        self.status = "running"

        checkpoint = self._load_checkpoint() if resume else None
        processed_keys = set(checkpoint.get("processed_keys", [])) if checkpoint else set()

        since_time = self.since
        if since_time is None and self.since_last_sync:
            since_time = self._load_last_sync_time()

        source_objects = list(self.source_client.list_objects_all(self.source_bucket, self.source_prefix))
        target_objects = self._get_target_objects()

        objects_to_sync = []
        for obj in source_objects:
            source_key = obj["Key"]

            if source_key in processed_keys:
                self.skipped += 1
                continue

            if since_time:
                last_modified = obj.get("LastModified")
                if last_modified:
                    if isinstance(last_modified, str):
                        from dateutil import parser
                        last_modified = parser.parse(last_modified)

                    if last_modified < since_time:
                        self.skipped += 1
                        continue

            if self._should_sync(obj, target_objects):
                if self._should_include(obj["Key"]):
                    objects_to_sync.append(obj)

        self.total_objects = len(objects_to_sync)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._migrate_object, obj): obj for obj in objects_to_sync}

            for future in as_completed(futures):
                result = future.result()
                self.processed_objects += 1

                if result.get("success"):
                    if result.get("skipped"):
                        self.skipped += 1
                    else:
                        self.uploaded += 1
                else:
                    self.failed += 1
                    self.failed_objects += 1
                    self.failed_list.append(result)

                if progress_callback:
                    progress_callback({
                        "processed": self.processed_objects,
                        "total": self.total_objects,
                        "uploaded": self.uploaded,
                        "deleted": self.deleted,
                        "skipped": self.skipped,
                        "failed": self.failed
                    })

                self._save_checkpoint()

        if self.delete:
            self._sync_delete(target_objects, source_objects)

        self.status = "completed" if self.failed_objects == 0 else "completed_with_errors"
        self.end_time = datetime.now()
        self._save_state()

        return self.get_summary()

    def get_summary(self) -> Dict:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "sync_id": self.sync_id,
            "status": self.status,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "total_objects": self.total_objects,
            "processed_objects": self.processed_objects,
            "uploaded": self.uploaded,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "failed_list": self.failed_list[:100]
        }

    def cancel(self):
        self.status = "cancelled"
        self.end_time = datetime.now()
        self._save_state()


def create_sync(
    source_config_name: str,
    source_bucket: str,
    target_config_name: str,
    target_bucket: str,
    source_prefix: str = "",
    target_prefix: str = "",
    since: Optional[datetime] = None,
    since_last_sync: bool = False,
    delete: bool = False,
    threads: int = 10,
    part_size: int = 8,
    storage_class: Optional[str] = None,
    preserve_metadata: bool = True,
    preserve_acl: bool = True,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    profile: Optional[str] = None
) -> SyncTask:
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

    sync_id = f"sync-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    since_time = since
    if since_last_sync and since_time is None:
        state_dir = Path.home() / ".skycli" / "sync-state"
        if state_dir.exists():
            for state_file in state_dir.glob("*.json"):
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("source_bucket") == source_bucket and data.get("target_bucket") == target_bucket:
                        last_sync = data.get("last_sync_time")
                        if last_sync:
                            since_time = datetime.fromisoformat(last_sync)

    return SyncTask(
        sync_id=sync_id,
        source_client=source_client,
        target_client=target_client,
        source_bucket=source_bucket,
        target_bucket=target_bucket,
        source_prefix=source_prefix,
        target_prefix=target_prefix,
        since=since_time,
        since_last_sync=since_last_sync,
        delete=delete,
        threads=threads,
        part_size=part_size,
        storage_class=storage_class,
        preserve_metadata=preserve_metadata,
        preserve_acl=preserve_acl,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns
    )


def get_sync(sync_id: str) -> Optional[Dict]:
    checkpoint_file = Path.home() / ".skycli" / "checkpoints" / f"{sync_id}.json"
    state_file = Path.home() / ".skycli" / "sync-state" / f"{sync_id}.json"

    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            return json.load(f)

    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


def get_sync_history(limit: int = 10) -> List[Dict]:
    history = []
    sync_dir = Path.home() / ".skycli" / "sync-state"

    if sync_dir.exists():
        for state_file in sync_dir.glob("*.json"):
            with open(state_file, "r", encoding="utf-8") as f:
                history.append(json.load(f))

    history.sort(key=lambda x: x.get("last_sync_time", ""), reverse=True)
    return history[:limit]
