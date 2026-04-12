import pytest
from s3_manager.skyclient import SkyClient
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_REGION


@pytest.fixture
def client(test_config, moto_mock):
    """根据配置创建 SkyClient 实例"""
    return SkyClient(
        endpoint=test_config["endpoint"],
        access_key=test_config["access_key"],
        secret_key=test_config["secret_key"],
        region=test_config["region"],
        use_path_style=test_config["use_path_style"],
        verify_ssl=test_config["verify_ssl"]
    )


@pytest.fixture
def client_with_bucket(client, test_buckets):
    """创建带测试桶的客户端"""
    bucket1 = test_buckets["bucket1"]
    bucket2 = test_buckets["bucket2"]
    
    # 创建桶，create_bucket 方法会自动处理 region
    if not client.bucket_exists(bucket1):
        client.create_bucket(bucket1)
    if not client.bucket_exists(bucket2):
        client.create_bucket(bucket2)
    return client


class TestSkyClient:
    def test_client_creation(self, client, test_config):
        assert client.endpoint == test_config["endpoint"]
        assert client.access_key == test_config["access_key"]
        assert client.region == test_config["region"]

    def test_test_connection(self, client):
        result = client.test_connection()
        assert result.get("success") == True
        assert result.get("bucket_count") >= 0

    def test_list_buckets(self, client):
        buckets = client.list_buckets()
        assert isinstance(buckets, list)
        for bucket in buckets:
            assert "Name" in bucket
            assert "CreationDate" in bucket

    def test_create_and_delete_bucket(self, client):
        test_bucket = "test-create-delete-bucket"
        try:
            client.create_bucket(test_bucket)
            assert client.bucket_exists(test_bucket)

            buckets = client.list_buckets()
            bucket_names = [b["Name"] for b in buckets]
            assert test_bucket in bucket_names
        finally:
            if client.bucket_exists(test_bucket):
                client.delete_bucket(test_bucket)

    def test_bucket_exists(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        assert client_with_bucket.bucket_exists(bucket1) == True
        assert client_with_bucket.bucket_exists("non-existent-bucket-xyz") == False

    def test_get_bucket_location(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        location = client_with_bucket.get_bucket_location(bucket1)
        assert location is not None

    def test_get_bucket_versioning(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        status = client_with_bucket.get_bucket_versioning(bucket1)
        assert status in ["Enabled", "Suspended", None]

    def test_put_and_get_object(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_object.txt"
        content = b"Hello, SkyCLI Test!"

        result = client_with_bucket.put_object(
            bucket=bucket1,
            key=key,
            body=content,
            content_type="text/plain"
        )
        assert "ETag" in result

        response = client_with_bucket.get_object(bucket1, key)
        body = response["Body"].read()
        assert body == content

    def test_head_object(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_head.txt"
        content = b"Test head object"
        metadata = {"project": "skycli", "env": "test"}

        client_with_bucket.put_object(
            bucket=bucket1,
            key=key,
            body=content,
            metadata=metadata,
            content_type="text/plain"
        )

        info = client_with_bucket.head_object(bucket1, key)
        assert info["ContentLength"] == len(content)
        assert info["ContentType"] == "text/plain"
        assert info["Metadata"].get("project") == "skycli"

    def test_delete_object(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_delete.txt"
        content = b"To be deleted"

        client_with_bucket.put_object(bucket1, key, content)
        client_with_bucket.delete_object(bucket1, key)

        with pytest.raises(Exception):
            client_with_bucket.head_object(bucket1, key)

    def test_list_objects(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        result = client_with_bucket.list_objects(bucket1)
        assert "objects" in result
        assert "is_truncated" in result
        assert isinstance(result["objects"], list)

    def test_list_objects_with_prefix(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        prefix = "test_prefix/"
        key1 = prefix + "file1.txt"
        key2 = prefix + "file2.txt"

        client_with_bucket.put_object(bucket1, key1, b"content1")
        client_with_bucket.put_object(bucket1, key2, b"content2")

        result = client_with_bucket.list_objects(bucket1, prefix=prefix)
        assert len(result["objects"]) >= 2

        keys = [obj["Key"] for obj in result["objects"]]
        assert key1 in keys or any(key1 in k for k in keys)
        assert key2 in keys or any(key2 in k for k in keys)

    def test_copy_object(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        source_key = "copy_source.txt"
        target_key = "copy_target.txt"
        content = b"Content to be copied"

        client_with_bucket.put_object(bucket1, source_key, content)

        result = client_with_bucket.copy_object(
            source_bucket=bucket1,
            source_key=source_key,
            target_bucket=bucket1,
            target_key=target_key
        )
        assert "ETag" in result

        target_info = client_with_bucket.head_object(bucket1, target_key)
        assert target_info["ContentLength"] == len(content)

    def test_object_acl(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_acl.txt"
        client_with_bucket.put_object(bucket1, key, b"ACL test")

        acl = client_with_bucket.get_object_acl(bucket1, key)
        assert "Owner" in acl
        assert "Grants" in acl
        assert isinstance(acl["Grants"], list)

    def test_generate_presigned_url(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_presign.txt"
        client_with_bucket.put_object(bucket1, key, b"Presign test")

        url = client_with_bucket.generate_presigned_url(bucket1, key, expires_in=3600)
        assert isinstance(url, str)
        assert key in url

    def test_upload_download_file(self, client_with_bucket, tmp_path, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_file_upload.txt"
        test_file = tmp_path / "upload_test.txt"
        test_content = b"File upload test content"
        test_file.write_bytes(test_content)

        client_with_bucket.upload_file(bucket1, key, str(test_file))

        download_file = tmp_path / "download_test.txt"
        client_with_bucket.download_file(bucket1, key, str(download_file))

        assert download_file.read_bytes() == test_content


class TestSkyClientMetadata:
    def test_put_object_with_metadata(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        key = "test_metadata.txt"
        content = b"Metadata test"
        metadata = {
            "custom-key": "custom-value",
            "another-key": "another-value"
        }

        client_with_bucket.put_object(
            bucket=bucket1,
            key=key,
            body=content,
            metadata=metadata,
            cache_control="no-cache"
        )

        info = client_with_bucket.head_object(bucket1, key)
        assert info["Metadata"].get("custom-key") == "custom-value"
        assert info["Metadata"].get("another-key") == "another-value"
        assert info["CacheControl"] == "no-cache"

    def test_copy_object_with_metadata(self, client_with_bucket, test_buckets):
        bucket1 = test_buckets["bucket1"]
        source_key = "source_with_metadata.txt"
        target_key = "target_with_metadata.txt"
        content = b"Copy with metadata"
        metadata = {"copy-test": "true"}

        client_with_bucket.put_object(
            bucket=bucket1,
            key=source_key,
            body=content,
            metadata=metadata
        )

        client_with_bucket.copy_object(
            source_bucket=bucket1,
            source_key=source_key,
            target_bucket=bucket1,
            target_key=target_key,
            metadata_directive="REPLACE",
            metadata={"new-key": "new-value"}
        )

        target_info = client_with_bucket.head_object(bucket1, target_key)
        assert target_info["Metadata"].get("new-key") == "new-value"
