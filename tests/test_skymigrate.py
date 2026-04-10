import pytest
from unittest.mock import patch, MagicMock
from s3_manager.skymigrate import create_migration, MigrationTask
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
    with patch("s3_manager.skymigrate.config") as mock:
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


class TestSkyMigrate:
    def test_create_migration(self, mock_config):
        migration = create_migration(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            profile="test"
        )

        assert migration is not None
        assert migration.source_bucket == TEST_BUCKET_1
        assert migration.target_bucket == TEST_BUCKET_2
        assert migration.status == "pending"

    def test_migration_preview(self, setup_buckets):
        source_client, target_client = setup_buckets

        test_key = "preview_test.txt"
        source_client.put_object(TEST_BUCKET_1, test_key, b"Preview test content")

        objects = list(source_client.list_objects_all(TEST_BUCKET_1, ""))
        assert len(objects) >= 1

        keys = [obj["Key"] for obj in objects]
        assert test_key in keys

    def test_migration_single_object(self, setup_buckets):
        source_client, target_client = setup_buckets

        test_key = "migrate_single.txt"
        test_content = b"Migration test content"
        source_client.put_object(TEST_BUCKET_1, test_key, test_content)

        objects = list(source_client.list_objects_all(TEST_BUCKET_1, ""))
        assert len(objects) >= 1

    def test_exclude_patterns(self, mock_config):
        task = create_migration(
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
        task = create_migration(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            exclude_patterns=[],
            include_patterns=["*.jpg", "*.png"]
        )

        assert task._should_include("photo.jpg") == True
        assert task._should_include("image.png") == True
        assert task._should_include("document.pdf") == False
        assert task._should_include("video.mp4") == False
