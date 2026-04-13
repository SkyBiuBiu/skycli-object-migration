import pytest
import os
from pathlib import Path

# 环境变量控制
USE_MOTO = os.getenv("SKYCLI_USE_MOTO", "true").lower() == "true"

# 加载 .env 文件
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


# 真实 S3 测试配置
TEST_ENDPOINT = os.environ.get("SKYCLI_TEST_ENDPOINT", "http://localhost:9000")
TEST_ACCESS_KEY = os.environ.get("SKYCLI_TEST_ACCESS_KEY", "test")
TEST_SECRET_KEY = os.environ.get("SKYCLI_TEST_SECRET_KEY", "test")
TEST_BUCKET_1 = os.environ.get("SKYCLI_TEST_BUCKET_1", "test-bucket-1")
TEST_BUCKET_2 = os.environ.get("SKYCLI_TEST_BUCKET_2", "test-bucket-2")
TEST_REGION = os.environ.get("SKYCLI_TEST_REGION", "us-west-2")
TEST_SIGNATURE_VERSION = os.environ.get("AWS_SIGNATURE_VERSION", "s3v4")


@pytest.fixture(scope="function")
def use_moto():
    """返回是否使用 moto 的标记"""
    return USE_MOTO


@pytest.fixture(scope="function")
def moto_mock():
    """Moto S3 mock 上下文管理器"""
    from moto import mock_aws
    mock = mock_aws()
    mock.start()
    yield mock
    mock.stop()


@pytest.fixture
def test_config(use_moto):
    """测试配置，根据是否使用 moto 返回不同配置"""
    if use_moto:
        return {
            "endpoint": "https://s3.amazonaws.com",
            "access_key": "testing",
            "secret_key": "testing",
            "region": TEST_REGION,
            "use_path_style": False,
            "verify_ssl": True,
            "signature_version": TEST_SIGNATURE_VERSION
        }
    else:
        return {
            "endpoint": TEST_ENDPOINT,
            "access_key": TEST_ACCESS_KEY,
            "secret_key": TEST_SECRET_KEY,
            "region": TEST_REGION,
            "use_path_style": True,
            "verify_ssl": False,
            "signature_version": TEST_SIGNATURE_VERSION
        }


@pytest.fixture
def test_buckets(use_moto):
    """测试桶配置"""
    if use_moto:
        return {
            "bucket1": "test-bucket-1",
            "bucket2": "test-bucket-2"
        }
    else:
        return {
            "bucket1": TEST_BUCKET_1,
            "bucket2": TEST_BUCKET_2
        }


@pytest.fixture
def temp_file(tmp_path):
    def _create_temp_file(content=b"test data", suffix=".txt"):
        file = tmp_path / f"test_file{suffix}"
        file.write_bytes(content)
        return str(file)
    return _create_temp_file
