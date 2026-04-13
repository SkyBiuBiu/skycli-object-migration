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

    def test_validation_missing_target_object(self, setup_buckets, mock_config):
        """测试目标对象缺失的验证场景"""
        source_client, target_client = setup_buckets

        test_key = "missing_target.txt"
        test_content = b"Content without target"

        # 只在源桶上传对象
        source_client.put_object(TEST_BUCKET_1, test_key, test_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=True,
            check_acl=False
        )

        # 执行验证
        report = validation.run()
        assert report is not None
        
        # 从 failed_objects 中查找
        failed = report.get("failed_objects", [])
        assert len(failed) > 0
        
        test_result = None
        for result in failed:
            if result.get("key") == test_key:
                test_result = result
                break
        
        assert test_result is not None
        assert test_result.get("success") == False

    def test_validation_content_mismatch(self, setup_buckets, mock_config):
        """测试内容不匹配的验证场景"""
        source_client, target_client = setup_buckets

        test_key = "content_mismatch.txt"
        source_content = b"Source content"
        target_content = b"Different target content"

        source_client.put_object(TEST_BUCKET_1, test_key, source_content)
        target_client.put_object(TEST_BUCKET_2, test_key, target_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=False,
            check_acl=False
        )

        report = validation.run()
        assert report is not None
        
        failed = report.get("failed_objects", [])
        assert len(failed) > 0
        
        test_result = None
        for result in failed:
            if result.get("key") == test_key:
                test_result = result
                break
        
        assert test_result is not None
        assert test_result.get("success") == False
        assert test_result.get("content_ok") == False

    def test_validation_metadata_mismatch(self, setup_buckets, mock_config):
        """测试元数据不匹配的验证场景"""
        source_client, target_client = setup_buckets

        test_key = "metadata_mismatch.txt"
        test_content = b"Metadata test content"

        # 上传源对象带自定义元数据
        source_client.put_object(
            TEST_BUCKET_1, 
            test_key, 
            test_content,
            metadata={"custom-key": "source-value"}
        )
        
        # 上传目标对象带不同元数据
        target_client.put_object(
            TEST_BUCKET_2, 
            test_key, 
            test_content,
            metadata={"custom-key": "target-value"}
        )

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=False,
            check_metadata=True,
            check_acl=False
        )

        report = validation.run()
        assert report is not None
        
        failed = report.get("failed_objects", [])
        assert len(failed) > 0
        
        test_result = None
        for result in failed:
            if result.get("key") == test_key:
                test_result = result
                break
        
        assert test_result is not None
        assert test_result.get("success") == False

    def test_validation_with_prefix(self, setup_buckets, mock_config):
        """测试带前缀的验证"""
        source_client, target_client = setup_buckets

        prefix = "validation_prefix/"
        test_keys = [f"{prefix}file1.txt", f"{prefix}file2.txt", f"other/file3.txt"]
        test_content = b"Prefixed content"

        for key in test_keys:
            source_client.put_object(TEST_BUCKET_1, key, test_content)
            target_client.put_object(TEST_BUCKET_2, key, test_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            prefix=prefix
        )

        report = validation.run()
        assert report is not None
        
        # 验证摘要信息
        summary = report.get("summary", {})
        total = summary.get("total_objects", 0)
        assert total == 2  # 只有 2 个带前缀的对象

    def test_validation_get_report(self, setup_buckets, mock_config):
        """测试验证报告生成"""
        source_client, target_client = setup_buckets

        test_key = "report_test.txt"
        test_content = b"Report test content"

        source_client.put_object(TEST_BUCKET_1, test_key, test_content)
        target_client.put_object(TEST_BUCKET_2, test_key, test_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True
        )

        report = validation.run()
        
        assert report is not None
        assert "validation_id" in report
        assert "status" in report
        assert "summary" in report
        assert report["status"] == "completed"

    def test_validation_all_checks_pass(self, setup_buckets, mock_config):
        """测试所有检查都通过的场景"""
        source_client, target_client = setup_buckets

        test_key = "all_pass.txt"
        test_content = b"Perfect match"

        source_client.put_object(TEST_BUCKET_1, test_key, test_content)
        target_client.put_object(TEST_BUCKET_2, test_key, test_content)

        validation = create_validation(
            source_config_name="test-source",
            source_bucket=TEST_BUCKET_1,
            target_config_name="test-target",
            target_bucket=TEST_BUCKET_2,
            check_content=True,
            check_metadata=True,
            check_acl=False
        )

        report = validation.run()
        assert report is not None
        
        # 验证所有对象都通过
        summary = report.get("summary", {})
        assert summary.get("content_passed", 0) >= 1
        assert summary.get("metadata_passed", 0) >= 1
        assert summary.get("failed", 0) == 0
