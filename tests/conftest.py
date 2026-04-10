import pytest
import os


TEST_ENDPOINT = "http://192.168.100.128:9000"
TEST_ACCESS_KEY = "admin"
TEST_SECRET_KEY = "Tell12#$%^"
TEST_BUCKET_1 = "demo"
TEST_BUCKET_2 = "test2"
TEST_REGION = "us-east-1"


@pytest.fixture
def test_config():
    return {
        "endpoint": TEST_ENDPOINT,
        "access_key": TEST_ACCESS_KEY,
        "secret_key": TEST_SECRET_KEY,
        "region": TEST_REGION,
        "use_path_style": True,
        "verify_ssl": False
    }


@pytest.fixture
def test_buckets():
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
