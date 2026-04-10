import pytest
from s3_manager.skymetadata import SkyMetadata
from s3_manager.skyclient import SkyClient
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_REGION, TEST_BUCKET_1


@pytest.fixture
def metadata_handler():
    client = SkyClient(
        endpoint=TEST_ENDPOINT,
        access_key=TEST_ACCESS_KEY,
        secret_key=TEST_SECRET_KEY,
        region=TEST_REGION,
        use_path_style=True,
        verify_ssl=False
    )
    return SkyMetadata(client)


@pytest.fixture
def client():
    client = SkyClient(
        endpoint=TEST_ENDPOINT,
        access_key=TEST_ACCESS_KEY,
        secret_key=TEST_SECRET_KEY,
        region=TEST_REGION,
        use_path_style=True,
        verify_ssl=False
    )
    if not client.bucket_exists(TEST_BUCKET_1):
        client.create_bucket(TEST_BUCKET_1)
    return client


class TestSkyMetadata:
    def test_get_metadata(self, metadata_handler, client):
        key = "meta_get_test.txt"
        content = b"Test content"
        metadata = {"key1": "value1", "key2": "value2"}

        client.put_object(TEST_BUCKET_1, key, content, metadata=metadata)

        result = metadata_handler.get(TEST_BUCKET_1, key)
        assert "Metadata" in result
        assert result["Metadata"].get("key1") == "value1"
        assert result["Metadata"].get("key2") == "value2"

    def test_set_metadata_replace(self, metadata_handler, client):
        key = "meta_set_test.txt"
        content = b"Test content"

        client.put_object(TEST_BUCKET_1, key, content, metadata={"old": "value"})

        metadata_handler.set(
            bucket=TEST_BUCKET_1,
            key=key,
            metadata={"new": "value", "added": "field"},
            operation="REPLACE"
        )

        result = metadata_handler.get(TEST_BUCKET_1, key)
        assert result["Metadata"].get("new") == "value"
        assert result["Metadata"].get("added") == "field"
        assert result["Metadata"].get("old") is None

    def test_set_metadata_copy(self, metadata_handler, client):
        key = "meta_copy_test.txt"
        content = b"Test content"

        client.put_object(TEST_BUCKET_1, key, content, metadata={"original": "keep"})

        metadata_handler.set(
            bucket=TEST_BUCKET_1,
            key=key,
            metadata={"added": "new-field"},
            operation="COPY"
        )

        result = metadata_handler.get(TEST_BUCKET_1, key)
        assert result["Metadata"].get("original") == "keep"
        assert result["Metadata"].get("added") == "new-field"

    def test_compare_metadata_match(self, metadata_handler, client):
        key = "meta_compare_match.txt"
        content = b"Test content"
        metadata = {"key": "value", "another": "data"}

        client.put_object(TEST_BUCKET_1, key, content, metadata=metadata)

        meta1 = metadata_handler.get(TEST_BUCKET_1, key)
        meta2 = metadata_handler.get(TEST_BUCKET_1, key)

        result = metadata_handler.compare(meta1, meta2)
        assert result["match"] == True

    def test_compare_metadata_mismatch(self, metadata_handler, client):
        key1 = "meta_compare_1.txt"
        key2 = "meta_compare_2.txt"

        client.put_object(TEST_BUCKET_1, key1, b"content1", metadata={"key": "value1"})
        client.put_object(TEST_BUCKET_1, key2, b"content2", metadata={"key": "value2"})

        meta1 = metadata_handler.get(TEST_BUCKET_1, key1)
        meta2 = metadata_handler.get(TEST_BUCKET_1, key2)

        result = metadata_handler.compare(meta1, meta2)
        assert result["match"] == False
        assert "Metadata" in result["differences"]

    def test_list_for_prefix(self, metadata_handler, client):
        prefix = "test_prefix_meta/"
        key1 = prefix + "file1.txt"
        key2 = prefix + "file2.txt"

        client.put_object(TEST_BUCKET_1, key1, b"content1", metadata={"meta": "value1"})
        client.put_object(TEST_BUCKET_1, key2, b"content2", metadata={"meta": "value2"})

        results = metadata_handler.list_for_prefix(TEST_BUCKET_1, prefix)
        assert len(results) >= 2
