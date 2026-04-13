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
        verify_ssl=test_config["verify_ssl"],
        signature_version=test_config["signature_version"]
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

    def test_signature_version(self, test_config):
        """测试签名版本配置"""
        client = SkyClient(
            endpoint=test_config["endpoint"],
            access_key=test_config["access_key"],
            secret_key=test_config["secret_key"],
            region=test_config["region"],
            signature_version="s3v4"
        )
        assert client.signature_version == "s3v4"

        client_s3 = SkyClient(
            endpoint=test_config["endpoint"],
            access_key=test_config["access_key"],
            secret_key=test_config["secret_key"],
            region=test_config["region"],
            signature_version="s3"
        )
        assert client_s3.signature_version == "s3"

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


class TestSkyClientMultipartUpload:
    """测试 Multipart Upload API"""

    def test_create_multipart_upload(self, client_with_bucket, test_buckets):
        """测试创建分段上传"""
        bucket = test_buckets["bucket1"]
        key = "test_multipart.txt"

        result = client_with_bucket.create_multipart_upload(
            bucket=bucket,
            key=key,
            content_type="text/plain",
            storage_class="STANDARD"
        )

        assert "UploadId" in result
        assert result["Bucket"] == bucket
        assert result["Key"] == key

        client_with_bucket.abort_multipart_upload(bucket, key, result["UploadId"])

    def test_upload_part(self, client_with_bucket, test_buckets):
        """测试上传分片"""
        bucket = test_buckets["bucket1"]
        key = "test_part.txt"

        init_result = client_with_bucket.create_multipart_upload(bucket=bucket, key=key)
        upload_id = init_result["UploadId"]

        part_data = b"Part 1 content data"
        part_result = client_with_bucket.upload_part(
            bucket=bucket,
            key=key,
            upload_id=upload_id,
            part_number=1,
            data=part_data
        )

        assert "ETag" in part_result
        assert part_result["PartNumber"] == 1

        client_with_bucket.abort_multipart_upload(bucket, key, upload_id)

    def test_complete_multipart_upload(self, client_with_bucket, test_buckets):
        """测试完成分段上传"""
        bucket = test_buckets["bucket1"]
        key = "test_complete.txt"

        init_result = client_with_bucket.create_multipart_upload(bucket=bucket, key=key)
        upload_id = init_result["UploadId"]

        parts = []
        for i in range(1, 4):
            part_data = b"A" * (6 * 1024 * 1024)
            part_result = client_with_bucket.upload_part(
                bucket=bucket,
                key=key,
                upload_id=upload_id,
                part_number=i,
                data=part_data
            )
            parts.append({"PartNumber": i, "ETag": part_result["ETag"]})

        complete_result = client_with_bucket.complete_multipart_upload(
            bucket=bucket,
            key=key,
            upload_id=upload_id,
            parts=parts
        )

        assert "ETag" in complete_result
        assert complete_result["Key"] == key

    def test_abort_multipart_upload(self, client_with_bucket, test_buckets):
        """测试中止分段上传"""
        bucket = test_buckets["bucket1"]
        key = "test_abort.txt"

        init_result = client_with_bucket.create_multipart_upload(bucket=bucket, key=key)
        upload_id = init_result["UploadId"]

        result = client_with_bucket.abort_multipart_upload(bucket, key, upload_id)
        assert result == True

    def test_list_parts(self, client_with_bucket, test_buckets):
        """测试列出已上传的分片"""
        bucket = test_buckets["bucket1"]
        key = "test_list_parts.txt"

        init_result = client_with_bucket.create_multipart_upload(bucket=bucket, key=key)
        upload_id = init_result["UploadId"]

        for i in range(1, 3):
            part_data = b"B" * (6 * 1024 * 1024)
            client_with_bucket.upload_part(
                bucket=bucket,
                key=key,
                upload_id=upload_id,
                part_number=i,
                data=part_data
            )

        parts = client_with_bucket.list_parts(bucket, key, upload_id)
        assert len(parts) == 2

        client_with_bucket.abort_multipart_upload(bucket, key, upload_id)

    def test_list_multipart_uploads(self, client_with_bucket, test_buckets):
        """测试列出未完成的分段上传"""
        bucket = test_buckets["bucket1"]

        for i in range(1, 3):
            key = f"test_list_uploads_{i}.txt"
            client_with_bucket.create_multipart_upload(bucket=bucket, key=key)

        uploads = client_with_bucket.list_multipart_uploads(bucket)
        assert len(uploads) >= 2

        for upload in uploads:
            client_with_bucket.abort_multipart_upload(bucket, upload["Key"], upload["UploadId"])

    def test_multipart_upload_file_small(self, client_with_bucket, test_buckets, tmp_path):
        """测试小文件使用普通上传"""
        bucket = test_buckets["bucket1"]
        key = "test_small_upload.txt"
        test_file = tmp_path / "small_upload.txt"
        test_file.write_bytes(b"Small file content")

        result = client_with_bucket.multipart_upload_file(
            bucket=bucket,
            key=key,
            file_path=str(test_file),
            part_size=10 * 1024 * 1024
        )

        assert result["success"] == True

    def test_multipart_upload_file_large(self, client_with_bucket, test_buckets, tmp_path):
        """测试大文件使用分段上传"""
        bucket = test_buckets["bucket1"]
        key = "test_large_upload.txt"
        test_file = tmp_path / "large_upload.txt"

        content = b"X" * (10 * 1024 * 1024)
        test_file.write_bytes(content)

        result = client_with_bucket.multipart_upload_file(
            bucket=bucket,
            key=key,
            file_path=str(test_file),
            part_size=5 * 1024 * 1024,
            storage_class="STANDARD"
        )

        assert "Parts" in result
        assert result["Parts"] == 2

    def test_multipart_upload_with_sse(self, client_with_bucket, test_buckets):
        """测试带 SSE 的分段上传"""
        bucket = test_buckets["bucket1"]
        key = "test_sse_upload.txt"

        result = client_with_bucket.create_multipart_upload(
            bucket=bucket,
            key=key,
            storage_class="STANDARD",
            sse={"Algorithm": "AES256"}
        )

        assert "UploadId" in result

        client_with_bucket.abort_multipart_upload(bucket, key, result["UploadId"])

    def test_multipart_upload_file_with_progress_callback(self, client_with_bucket, test_buckets, tmp_path):
        """测试带进度回调的分片上传"""
        bucket = test_buckets["bucket1"]
        key = "test_progress_upload.txt"
        test_file = tmp_path / "progress_upload.txt"

        content = b"X" * (10 * 1024 * 1024)
        test_file.write_bytes(content)

        progress_data = []

        def progress_callback(uploaded, total):
            progress_data.append((uploaded, total))

        result = client_with_bucket.multipart_upload_file(
            bucket=bucket,
            key=key,
            file_path=str(test_file),
            part_size=5 * 1024 * 1024,
            progress_callback=progress_callback
        )

        assert "Parts" in result
        assert len(progress_data) > 0
        assert progress_data[-1][1] == 10 * 1024 * 1024

    def test_multipart_upload_with_metadata(self, client_with_bucket, test_buckets):
        """测试带元数据的分片上传"""
        bucket = test_buckets["bucket1"]
        key = "test_metadata_multipart.txt"

        result = client_with_bucket.create_multipart_upload(
            bucket=bucket,
            key=key,
            metadata={"test-key": "test-value"},
            content_type="application/octet-stream"
        )

        assert "UploadId" in result

        client_with_bucket.abort_multipart_upload(bucket, key, result["UploadId"])


class TestSkyClientBucketOperations:
    """测试桶操作"""

    def test_create_bucket_with_region(self, client, test_buckets):
        """测试创建桶指定 region"""
        bucket = test_buckets["bucket1"]

        if client.bucket_exists(bucket):
            client.delete_bucket(bucket)

        client.create_bucket(bucket, region=TEST_REGION)
        assert client.bucket_exists(bucket)

    def test_delete_bucket(self, client_with_bucket, test_buckets):
        """测试删除桶"""
        bucket = test_buckets["bucket2"]

        if client_with_bucket.bucket_exists(bucket):
            client_with_bucket.delete_bucket(bucket)

        assert not client_with_bucket.bucket_exists(bucket)

    def test_delete_object(self, client_with_bucket, test_buckets):
        """测试删除对象"""
        bucket = test_buckets["bucket1"]
        key = "to_delete.txt"

        client_with_bucket.put_object(bucket, key, b"Delete me")
        assert client_with_bucket.head_object(bucket, key) is not None

        client_with_bucket.delete_object(bucket, key)

        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            client_with_bucket.head_object(bucket, key)

    def test_get_bucket_versioning(self, client_with_bucket, test_buckets):
        """测试获取桶版本控制状态"""
        bucket = test_buckets["bucket1"]

        status = client_with_bucket.get_bucket_versioning(bucket)
        assert status in ["Enabled", "Suspended"]

    def test_enable_bucket_versioning(self, client_with_bucket, test_buckets):
        """测试启用桶版本控制"""
        bucket = test_buckets["bucket1"]

        client_with_bucket.enable_bucket_versioning(bucket)
        status = client_with_bucket.get_bucket_versioning(bucket)
        assert status == "Enabled"

    def test_suspend_bucket_versioning(self, client_with_bucket, test_buckets):
        """测试暂停桶版本控制"""
        bucket = test_buckets["bucket1"]

        client_with_bucket.suspend_bucket_versioning(bucket)
        status = client_with_bucket.get_bucket_versioning(bucket)
        assert status == "Suspended"


class TestSkyClientPresignedUrl:
    """测试预签名 URL"""

    def test_generate_presigned_url_put_object(self, client_with_bucket, test_buckets):
        """测试生成 PUT 预签名 URL"""
        bucket = test_buckets["bucket1"]
        key = "presign_put.txt"

        url = client_with_bucket.generate_presigned_url(bucket, key, expires_in=3600, method="PUT")
        assert isinstance(url, str)
        assert bucket in url
        assert key in url

    def test_generate_presigned_url_get_object(self, client_with_bucket, test_buckets):
        """测试生成 GET 预签名 URL"""
        bucket = test_buckets["bucket1"]
        key = "presign_get.txt"

        client_with_bucket.put_object(bucket, key, b"Presign test")

        url = client_with_bucket.generate_presigned_url(bucket, key, expires_in=7200, method="GET")
        assert isinstance(url, str)
        assert bucket in url
        assert key in url


class TestSkyClientErrorHandling:
    """测试错误处理"""

    def test_upload_file_with_extra_args(self, client_with_bucket, test_buckets, tmp_path):
        """测试带额外参数的 upload_file"""
        bucket = test_buckets["bucket1"]
        key = "test_extra_args.txt"
        test_file = tmp_path / "extra_args.txt"
        test_file.write_bytes(b"Extra args test")

        result = client_with_bucket.upload_file(
            bucket=bucket,
            key=key,
            file_path=str(test_file),
            content_type="text/plain",
            storage_class="STANDARD",
            extra_args={"ContentEncoding": "gzip"}
        )

        assert result["success"] == True

    def test_copy_object_with_all_options(self, client_with_bucket, test_buckets):
        """测试带所有选项的 copy_object"""
        bucket = test_buckets["bucket1"]
        source_key = "source_all.txt"
        target_key = "target_all.txt"

        client_with_bucket.put_object(bucket, source_key, b"Source content")

        result = client_with_bucket.copy_object(
            source_bucket=bucket,
            source_key=source_key,
            target_bucket=bucket,
            target_key=target_key,
            storage_class="GLACIER",
            metadata={"copied": "true"},
            metadata_directive="REPLACE",
            content_type="application/octet-stream"
        )

        assert "ETag" in result

    def test_put_object_acl_with_grants(self, client_with_bucket, test_buckets):
        """测试带授权的 put_object_acl"""
        bucket = test_buckets["bucket1"]
        key = "acl_grants.txt"

        client_with_bucket.put_object(bucket, key, b"ACL test")
        client_with_bucket.put_object_acl(bucket, key, grant_read="uri=http://acs.amazonaws.com/groups/global/AllUsers")
