import pytest
from unittest.mock import patch, MagicMock
from s3_manager.skysync import create_sync, SyncTask, SyncStatus
from s3_manager.skyclient import SkyClient
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_REGION, TEST_BUCKET_1, TEST_BUCKET_2


@pytest.fixture
def mock_config():
    mock_cfg = {
        "endpoint": TEST_ENDPOINT,
        "access_key": TEST_ACCESS_KEY,
        "secret_key": TEST_SECRET_KEY,
        "region": TEST_REGION,
        "use_path_style": True,
        "verify_ssl": False
    }
    with patch("s3_manager.skysync.config") as mock:
        mock.get_profile.return_value = mock_cfg
        yield mock


@pytest.fixture
def setup_buckets():
    source_client = SkyClient(
        endpoint=TEST_ENDPOINT,
        access_key=TEST_ACCESS_KEY,
        secret_key=TEST_SECRET_KEY,
        region=TEST_REGION,
        use_path_style=True,
        verify_ssl=False
    )

    target_client = SkyClient(
        endpoint=TEST_ENDPOINT,
        access_key=TEST_ACCESS_KEY,
        secret_key=TEST_SECRET_KEY,
        region=TEST_REGION,
        use_path_style=True,
        verify_ssl=False
    )

    for bucket in [TEST_BUCKET_1, TEST_BUCKET_2]:
        if not source_client.bucket_exists(bucket):
            source_client.create_bucket(bucket)

    return source_client, target_client


class TestSkySync:
    def test_create_sync(self, mock_config):
        sync = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            profile="test"
        )

        assert sync is not None
        assert sync.source_bucket == TEST_BUCKET_1
        assert sync.target_bucket == TEST_BUCKET_2
        assert sync.status == SyncStatus.PENDING

    def test_sync_preview(self, setup_buckets):
        source_client, target_client = setup_buckets

        test_key = "preview_test.txt"
        source_client.put_object(TEST_BUCKET_1, test_key, b"Preview test content")

        objects = list(source_client.list_objects_all(TEST_BUCKET_1, ""))
        assert len(objects) >= 1

        keys = [obj["Key"] for obj in objects]
        assert test_key in keys

    def test_sync_single_object(self, setup_buckets):
        source_client, target_client = setup_buckets

        test_key = "sync_single.txt"
        test_content = b"Sync test content"
        source_client.put_object(TEST_BUCKET_1, test_key, test_content)

        objects = list(source_client.list_objects_all(TEST_BUCKET_1, ""))
        assert len(objects) >= 1

    def test_exclude_patterns(self, mock_config):
        task = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            exclude_patterns=["*.tmp", "temp/*"],
            include_patterns=None
        )

        assert task._should_include("test.txt") == True
        assert task._should_include("test.tmp") == False
        assert task._should_include("temp/file.txt") == False
        assert task._should_include("logs/test.txt") == True

    def test_include_patterns(self, mock_config):
        task = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            exclude_patterns=[],
            include_patterns=["*.jpg", "*.png"]
        )

        assert task._should_include("photo.jpg") == True
        assert task._should_include("image.png") == True
        assert task._should_include("document.txt") == False

    def test_sync_with_since(self, mock_config):
        from datetime import datetime, timedelta

        since = datetime.now() - timedelta(days=1)
        sync = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            since=since
        )

        assert sync.since == since
        assert sync.since_last_sync == False

    def test_sync_with_delete(self, mock_config):
        sync = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            delete=True
        )

        assert sync.delete == True

    def test_sync_with_storage_class(self, mock_config):
        sync = create_sync(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            storage_class="GLACIER"
        )

        assert sync.storage_class == "GLACIER"

    def test_sync_task_init(self):
        task = SyncTask(
            sync_id="test-sync-001",
            source_client=MagicMock(),
            target_client=MagicMock(),
            source_bucket=TEST_BUCKET_1,
            target_bucket=TEST_BUCKET_2,
            source_prefix="src/",
            target_prefix="tgt/",
            threads=5,
            part_size=16,
            preserve_metadata=True,
            preserve_acl=True
        )

        assert task.sync_id == "test-sync-001"
        assert task.source_bucket == TEST_BUCKET_1
        assert task.target_bucket == TEST_BUCKET_2
        assert task.source_prefix == "src/"
        assert task.target_prefix == "tgt/"
        assert task.threads == 5
        assert task.part_size == 16
        assert task.preserve_metadata == True
        assert task.preserve_acl == True
        assert task.status == SyncStatus.PENDING

    def test_sync_delete_removes_orphan_objects(self):
        task = SyncTask(
            sync_id="test-sync-001",
            source_client=MagicMock(),
            target_client=MagicMock(),
            source_bucket=TEST_BUCKET_1,
            target_bucket=TEST_BUCKET_2,
            source_prefix="",
            target_prefix="",
            threads=1
        )

        source_objects = [
            {"Key": "file1.txt", "Size": 100},
            {"Key": "file2.txt", "Size": 200}
        ]

        target_objects = {
            "file1.txt": {"Key": "file1.txt", "Size": 100},
            "file2.txt": {"Key": "file2.txt", "Size": 200},
            "orphan.txt": {"Key": "orphan.txt", "Size": 50}
        }

        task._sync_delete(target_objects, source_objects)

        task.target_client.delete_object.assert_called_with(TEST_BUCKET_2, "orphan.txt")
        assert task.deleted == 1

    def test_sync_delete_with_prefix(self):
        task = SyncTask(
            sync_id="test-sync-001",
            source_client=MagicMock(),
            target_client=MagicMock(),
            source_bucket=TEST_BUCKET_1,
            target_bucket=TEST_BUCKET_2,
            source_prefix="src/",
            target_prefix="dst/",
            threads=1
        )

        source_objects = [
            {"Key": "src/file1.txt", "Size": 100}
        ]

        target_objects = {
            "file1.txt": {"Key": "dst/file1.txt", "Size": 100},
            "orphan.txt": {"Key": "dst/orphan.txt", "Size": 50}
        }

        task._sync_delete(target_objects, source_objects)

        task.target_client.delete_object.assert_called_with(TEST_BUCKET_2, "orphan.txt")
        assert task.deleted == 1

    def test_get_summary_returns_string_status(self):
        task = SyncTask(
            sync_id="test-sync-001",
            source_client=MagicMock(),
            target_client=MagicMock(),
            source_bucket=TEST_BUCKET_1,
            target_bucket=TEST_BUCKET_2,
            source_prefix="",
            target_prefix="",
            threads=1
        )

        task.status = SyncStatus.COMPLETED
        summary = task.get_summary()

        assert summary["status"] == "completed"
        assert isinstance(summary["status"], str)
