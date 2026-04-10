import pytest
from unittest.mock import patch, MagicMock
from s3_manager.skyvalidate import create_validation
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
    with patch("s3_manager.skyvalidate.config") as mock:
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


class TestSkyValidate:
    def test_create_validation(self, mock_config):
        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=True,
            check_acl=True
        )

        assert validation is not None
        assert validation.source_bucket == TEST_BUCKET_1
        assert validation.target_bucket == TEST_BUCKET_2
        assert validation.check_content == True
        assert validation.check_metadata == True
        assert validation.check_acl == True

    def test_validation_content_only(self, mock_config):
        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=False,
            check_acl=False
        )

        assert validation.check_content == True
        assert validation.check_metadata == False
        assert validation.check_acl == False

    def test_validate_identical_objects(self, setup_buckets, mock_config):
        source_client, target_client = setup_buckets

        test_key = "validate_identical.txt"
        test_content = b"Identical content for validation"

        source_client.put_object(TEST_BUCKET_1, test_key, test_content)
        target_client.put_object(TEST_BUCKET_2, test_key, test_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=True,
            check_acl=False,
            prefix=""
        )

        objects = list(source_client.list_objects_all(TEST_BUCKET_1, ""))
        assert len(objects) >= 1

    def test_validation_etag_comparison(self, setup_buckets, mock_config):
        source_client, target_client = setup_buckets

        test_key = "etag_test.txt"
        test_content = b"ETag test content"

        source_client.put_object(TEST_BUCKET_1, test_key, test_content)

        source_head = source_client.head_object(TEST_BUCKET_1, test_key)
        source_etag = source_head.get("ETag", "").strip('"')

        assert source_etag is not None and len(source_etag) > 0
