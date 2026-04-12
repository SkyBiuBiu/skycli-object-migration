import pytest
import os
from pathlib import Path

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


TEST_ENDPOINT = os.environ.get("SKYCLI_TEST_ENDPOINT", "http://localhost:9000")
TEST_ACCESS_KEY = os.environ.get("SKYCLI_TEST_ACCESS_KEY", "test")
TEST_SECRET_KEY = os.environ.get("SKYCLI_TEST_SECRET_KEY", "test")
TEST_BUCKET_1 = os.environ.get("SKYCLI_TEST_BUCKET_1", "test-bucket-1")
TEST_BUCKET_2 = os.environ.get("SKYCLI_TEST_BUCKET_2", "test-bucket-2")
TEST_REGION = os.environ.get("SKYCLI_TEST_REGION", "us-east-1")


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
