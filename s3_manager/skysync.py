"""
S3 Sync Module - Optimized for large files and massive small files
"""
import uuid
import json
import fnmatch
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from .skyclient import SkyClient
from .skyconfig import config
from .skymetadata import SkyMetadata
from .skyacl import SkyACL

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """同步任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    CANCELLED = "cancelled"


# 常量定义
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MiB - 触发分段上传的文件大小阈值
CHECKPOINT_BATCH_SIZE = 100  # 每 N 个对象批量保存一次 checkpoint，减少磁盘 I/O


@dataclass
class SyncResult:
    """单个对象同步结果"""
    success: bool
    key: str
    target_key: Optional[str] = None
    skipped: bool = False
    error: Optional[str] = None
    reason: Optional[str] = None
    size: int = 0


@dataclass
class SyncProgress:
    """同步进度信息"""
    processed: int = 0
    total: int = 0
    uploaded: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class SyncTask:
    """S3 对象同步任务"""
    
    # ===== 配置参数 (Configuration) =====
    sync_id: str
    source_client: SkyClient
    target_client: SkyClient
    source_bucket: str
    target_bucket: str
    source_prefix: str = ""
    target_prefix: str = ""
    since: Optional[datetime] = None
    since_last_sync: bool = False
    delete: bool = False
    threads: int = 10
    part_size: int = 8
    storage_class: Optional[str] = None
    preserve_metadata: bool = True
    preserve_acl: bool = True
    exclude_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    
    # ===== 运行时状态 (Runtime State) =====
    status: SyncStatus = field(default=SyncStatus.PENDING, init=False)
    start_time: Optional[datetime] = field(default=None, init=False)
    end_time: Optional[datetime] = field(default=None, init=False)
    
    # ===== 统计信息 (Statistics) =====
    total_objects: int = field(default=0, init=False)
    processed_objects: int = field(default=0, init=False)
    uploaded: int = field(default=0, init=False)
    deleted: int = field(default=0, init=False)
    skipped: int = field(default=0, init=False)
    failed: int = field(default=0, init=False)
    total_bytes: int = field(default=0, init=False)
    transferred_bytes: int = field(default=0, init=False)
    failed_list: List[Dict] = field(default_factory=list, init=False)
    
    # ===== 内部状态 (Internal State) =====
    _checkpoint_cache: set = field(default_factory=set, init=False, repr=False)
    _checkpoint_dirty: bool = field(default=False, init=False, repr=False)
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保 exclude_patterns 和 include_patterns 是列表
        if self.exclude_patterns is None:
            self.exclude_patterns = []
        if self.include_patterns is None:
            self.include_patterns = []
        
        # 初始化辅助处理器
        self.metadata_handler = SkyMetadata(self.source_client)
        self.acl_handler = SkyACL(self.source_client)
        self.target_metadata_handler = SkyMetadata(self.target_client)
        self.target_acl_handler = SkyACL(self.target_client)
        
        # 初始化文件路径
        self.state_file = Path.home() / ".skycli" / "sync-state" / f"{self.sync_id}.json"
        self.checkpoint_file = Path.home() / ".skycli" / "checkpoints" / f"{self.sync_id}.json"

        self._checkpoint_cache = set()
        self._checkpoint_dirty = False

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

    def _save_checkpoint(self, force: bool = False):
        if not self._checkpoint_dirty and not force:
            return

        if len(self._checkpoint_cache) == 0 and not force:
            return

        checkpoint_dir = self.checkpoint_file.parent
        if not checkpoint_dir.exists():
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_data = {
            "sync_id": self.sync_id,
            "source_bucket": self.source_bucket,
            "target_bucket": self.target_bucket,
            "source_prefix": self.source_prefix,
            "target_prefix": self.target_prefix,
            "processed_keys": list(self._checkpoint_cache),
            "status": self.status.value,
            "total_objects": self.total_objects,
            "processed·_objects": self.processed_objects,
            "uploaded": self.uploaded,
            "deleted": self.deleted,
            "failed": self.failed,
            "skipped": self.skipped
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        self._checkpoint_dirty = False

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
            "status": self.status.value
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

    def _get_optimal_threads(self, object_size: int) -> int:
        if object_size > LARGE_FILE_THRESHOLD:
            return max(2, self.threads // 4)
        else:
            return self.threads

    def _prefetch_metadata(self, objects: List[Dict]) -> Dict[str, Dict]:
        metadata_cache = {}
        for obj in objects:
            key = obj["Key"]
            size = obj.get("Size", 0)

            if size > LARGE_FILE_THRESHOLD and self.preserve_metadata:
                try:
                    info = self.source_client.head_object(self.source_bucket, key)
                    metadata_cache[key] = {
                        "metadata": info.get("Metadata", {}),
                        "content_type": info.get("ContentType"),
                        "cache_control": info.get("CacheControl")
                    }
                except Exception as e:
                    logger.warning(f"Failed to prefetch metadata for {key}: {e}")

        return metadata_cache

    def _migrate_small_object(self, obj: Dict, metadata_cache: Optional[Dict[str, Dict]] = None) -> SyncResult:
        source_key = obj["Key"]
        target_key = self.target_prefix + source_key[len(self.source_prefix):] if self.source_prefix else self.target_prefix + source_key

        if not self._should_include(target_key):
            return SyncResult(success=True, key=source_key, skipped=True, reason="filtered")

        metadata = {}
        content_type = None
        cache_control = None

        if metadata_cache and source_key in metadata_cache:
            cached = metadata_cache[source_key]
            metadata = cached.get("metadata", {})
            content_type = cached.get("content_type")
            cache_control = cached.get("cache_control")
        elif self.preserve_metadata:
            try:
                info = self.source_client.head_object(self.source_bucket, source_key)
                metadata = info.get("Metadata", {})
                content_type = info.get("ContentType")
                cache_control = info.get("CacheControl")
            except Exception as e:
                logger.warning(f"Failed to get metadata for {source_key}: {e}")

        storage_cls = self.storage_class or obj.get("StorageClass", "STANDARD")

        try:
            response = self.source_client.get_object(self.source_bucket, source_key)
            body = response["Body"].read()

            self.target_client.put_object(
                bucket=self.target_bucket,
                key=target_key,
                body=body,
                metadata=metadata,
                content_type=content_type,
                cache_control=cache_control,
                storage_class=storage_cls
            )
        except Exception as e:
            return SyncResult(success=False, key=source_key, error=str(e))

        if self.preserve_acl:
            try:
                self.acl_handler.copy(self.source_bucket, source_key, self.target_bucket, target_key)
            except Exception as e:
                if "NotImplemented" not in str(e) and "MinIO" not in str(e):
                    logger.warning(f"Failed to copy ACL for {source_key}: {e}")

        return SyncResult(success=True, key=source_key, target_key=target_key)

    def _migrate_large_object(self, obj: Dict, metadata_cache: Optional[Dict[str, Dict]] = None) -> SyncResult:
        source_key = obj["Key"]
        target_key = self.target_prefix + source_key[len(self.source_prefix):] if self.source_prefix else self.target_prefix + source_key

        if not self._should_include(target_key):
            return SyncResult(success=True, key=source_key, skipped=True, reason="filtered")

        metadata = {}
        content_type = None
        cache_control = None
        size = obj.get("Size", 0)

        if metadata_cache and source_key in metadata_cache:
            cached = metadata_cache[source_key]
            metadata = cached.get("metadata", {})
            content_type = cached.get("content_type")
            cache_control = cached.get("cache_control")
        elif self.preserve_metadata:
            try:
                info = self.source_client.head_object(self.source_bucket, source_key)
                metadata = info.get("Metadata", {})
                content_type = info.get("ContentType")
                cache_control = info.get("CacheControl")
            except Exception as e:
                logger.warning(f"Failed to get metadata for {source_key}: {e}")

        storage_cls = self.storage_class or obj.get("StorageClass", "STANDARD")

        tmp_path = None
        try:
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"skycli_sync_{uuid.uuid4().hex}")

            self.source_client.download_file(self.source_bucket, source_key, tmp_path)

            self.target_client.upload_file(
                bucket=self.target_bucket,
                key=target_key,
                file_path=tmp_path,
                metadata=metadata if metadata else None,
                content_type=content_type,
                storage_class=storage_cls
            )

        except Exception as e:
            return SyncResult(success=False, key=source_key, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        if self.preserve_acl:
            try:
                self.acl_handler.copy(self.source_bucket, source_key, self.target_bucket, target_key)
            except Exception as e:
                if "NotImplemented" not in str(e) and "MinIO" not in str(e):
                    logger.warning(f"Failed to copy ACL for {source_key}: {e}")

        return SyncResult(success=True, key=source_key, target_key=target_key)

    def _migrate_object(self, obj: Dict, metadata_cache: Optional[Dict[str, Dict]] = None) -> SyncResult:
        size = obj.get("Size", 0)

        if size > LARGE_FILE_THRESHOLD:
            result = self._migrate_large_object(obj, metadata_cache)
        else:
            result = self._migrate_small_object(obj, metadata_cache)

        if not hasattr(result, 'size') or result.size == 0:
            result.size = size
        return result

    def _sync_object(self, obj: Dict, metadata_cache: Optional[Dict[str, Dict]] = None):
        result = self._migrate_object(obj, metadata_cache)
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
        self.status = SyncStatus.RUNNING

        checkpoint = self._load_checkpoint() if resume else None
        if checkpoint:
            self._checkpoint_cache = set(checkpoint.get("processed_keys", []))

        since_time = self.since
        if since_time is None and self.since_last_sync:
            since_time = self._load_last_sync_time()

        logger.info(f"Listing source objects from {self.source_bucket}/{self.source_prefix}")
        source_objects = list(self.source_client.list_objects_all(self.source_bucket, self.source_prefix))

        logger.info(f"Listing target objects from {self.target_bucket}/{self.target_prefix}")
        target_objects = self._get_target_objects()

        objects_to_sync = []
        for obj in source_objects:
            source_key = obj["Key"]
            self.total_bytes += obj.get("Size", 0)

            if source_key in self._checkpoint_cache:
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
        logger.info(f"Total objects to sync: {self.total_objects}")

        metadata_cache = self._prefetch_metadata(objects_to_sync)

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(self._migrate_object, obj, metadata_cache): obj
                for obj in objects_to_sync
            }

            for future in as_completed(futures):
                result: SyncResult = future.result()
                source_key = result.key

                self.processed_objects += 1
                self._checkpoint_cache.add(source_key)
                self._checkpoint_dirty = True

                if result.success:
                    if result.skipped:
                        self.skipped += 1
                    else:
                        self.uploaded += 1
                        self.transferred_bytes += result.size
                else:
                    self.failed += 1
                    self.failed_list.append({
                        "key": result.key,
                        "error": result.error
                    })

                if progress_callback:
                    progress_callback({
                        "processed": self.processed_objects,
                        "total": self.total_objects,
                        "uploaded": self.uploaded,
                        "deleted": self.deleted,
                        "skipped": self.skipped,
                        "failed": self.failed
                    })

                if self.processed_objects % CHECKPOINT_BATCH_SIZE == 0:
                    self._save_checkpoint()

        self._save_checkpoint(force=True)

        if self.delete:
            self._sync_delete(target_objects, source_objects)

        self.status = SyncStatus.COMPLETED if self.failed == 0 else SyncStatus.COMPLETED_WITH_ERRORS
        self.end_time = datetime.now()
        self._save_state()

        return self.get_summary()

    def get_summary(self) -> Dict:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "sync_id": self.sync_id,
            "status": self.status.value,
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
            "total_bytes": self.total_bytes,
            "transferred_bytes": self.transferred_bytes,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "failed_list": self.failed_list[:100]
        }

    def cancel(self):
        self.status = SyncStatus.CANCELLED
        self.end_time = datetime.now()
        self._save_checkpoint(force=True)
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
    state_dir = Path.home() / ".skycli" / "sync-state"
    if not state_dir.exists():
        return []

    history = []
    for state_file in state_dir.glob("*.json"):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                history.append(data)
        except Exception:
            continue

    history.sort(key=lambda x: x.get("last_sync_time", ""), reverse=True)
    return history[:limit]
