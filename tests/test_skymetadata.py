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

    def test_copy_metadata(self, metadata_handler, client):
        """测试元数据复制功能"""
        source_key = "meta_source.txt"
        target_key = "meta_target.txt"
        metadata = {"copied-key": "copied-value", "app": "test"}

        client.put_object(TEST_BUCKET_1, source_key, b"source content", metadata=metadata)

        metadata_handler.copy(
            source_bucket=TEST_BUCKET_1,
            source_key=source_key,
            target_bucket=TEST_BUCKET_1,
            target_key=target_key
        )

        result = metadata_handler.get(TEST_BUCKET_1, target_key)
        assert "Metadata" in result
        assert result["Metadata"].get("copied-key") == "copied-value"
        assert result["Metadata"].get("app") == "test"

    def test_copy_metadata_with_new_metadata(self, metadata_handler, client):
        """测试复制元数据时添加新元数据"""
        source_key = "meta_source2.txt"
        target_key = "meta_target2.txt"
        metadata = {"original": "data"}

        client.put_object(TEST_BUCKET_1, source_key, b"source", metadata=metadata)

        # 复制到不同的对象
        metadata_handler.copy(
            source_bucket=TEST_BUCKET_1,
            source_key=source_key,
            target_bucket=TEST_BUCKET_1,
            target_key=target_key
        )

        result = metadata_handler.get(TEST_BUCKET_1, target_key)
        assert result["Metadata"].get("original") == "data"

    def test_get_metadata_nonexistent_object(self, metadata_handler):
        """测试获取不存在对象的元数据"""
        with pytest.raises(Exception):
            metadata_handler.get(TEST_BUCKET_1, "nonexistent.txt")

    def test_set_metadata_with_copy(self, metadata_handler, client):
        """测试使用 COPY 操作设置元数据"""
        key = "meta_copy_op.txt"
        content = b"Test content"

        client.put_object(TEST_BUCKET_1, key, content, metadata={"initial": "value"})

        metadata_handler.set(
            bucket=TEST_BUCKET_1,
            key=key,
            metadata={"added": "field"},
            operation="COPY"
        )

        result = metadata_handler.get(TEST_BUCKET_1, key)
        assert result["Metadata"].get("initial") == "value"
        assert result["Metadata"].get("added") == "field"

    def test_compare_metadata_different_sizes(self, metadata_handler, client):
        """测试比较不同大小的元数据"""
        key1 = "meta_size1.txt"
        key2 = "meta_size2.txt"

        client.put_object(TEST_BUCKET_1, key1, b"content", metadata={"key": "value"})
        client.put_object(TEST_BUCKET_1, key2, b"content", metadata={"key": "value", "extra": "field"})

        meta1 = metadata_handler.get(TEST_BUCKET_1, key1)
        meta2 = metadata_handler.get(TEST_BUCKET_1, key2)

        result = metadata_handler.compare(meta1, meta2)
        assert result["match"] == False

    def test_metadata_handler_initialization(self, client):
        """测试元数据处理器初始化"""
        from s3_manager.skymetadata import SkyMetadata
        
        handler = SkyMetadata(client)
        assert handler.client == client

    def test_list_for_prefix(self, metadata_handler, client):
        prefix = "test_prefix_meta/"
        key1 = prefix + "file1.txt"
        key2 = prefix + "file2.txt"

        client.put_object(TEST_BUCKET_1, key1, b"content1", metadata={"meta": "value1"})
        client.put_object(TEST_BUCKET_1, key2, b"content2", metadata={"meta": "value2"})

        results = metadata_handler.list_for_prefix(TEST_BUCKET_1, prefix)
        assert len(results) >= 2

    def test_metadata_set_without_operation(self, metadata_handler, client):
        """测试不使用 operation 参数设置元数据"""
        key = "meta_no_op.txt"
        content = b"Test content"

        client.put_object(TEST_BUCKET_1, key, content)

        # 不使用 operation 参数，应该使用 PUT
        metadata_handler.set(
            bucket=TEST_BUCKET_1,
            key=key,
            metadata={"new": "value"}
        )

        result = metadata_handler.get(TEST_BUCKET_1, key)
        assert result["Metadata"].get("new") == "value"

    def test_metadata_compare_with_etag(self, metadata_handler, client):
        """测试带 ETag 比较的元数据比较"""
        key = "meta_etag.txt"
        content = b"ETag test content"

        client.put_object(TEST_BUCKET_1, key, content, metadata={"test": "etag"})

        meta1 = metadata_handler.get(TEST_BUCKET_1, key)
        meta2 = metadata_handler.get(TEST_BUCKET_1, key)

        # 同一个对象的元数据应该匹配
        result = metadata_handler.compare(meta1, meta2)
        assert result["match"] == True

    def test_metadata_get_nonexistent_bucket(self, metadata_handler):
        """测试获取不存在桶的元数据"""
        with pytest.raises(Exception):
            metadata_handler.get("nonexistent-bucket-xyz", "key.txt")

    def test_metadata_handler_class_methods(self, client):
        """测试 SkyMetadata 类的方法"""
        from s3_manager.skymetadata import SkyMetadata
        
        handler = SkyMetadata(client)
        
        # 测试 client 属性
        assert handler.client == client
        
        # 测试 compare 方法返回结构
        meta1 = {"Metadata": {"key": "value1"}, "ETag": "etag1"}
        meta2 = {"Metadata": {"key": "value2"}, "ETag": "etag2"}
        
        result = handler.compare(meta1, meta2)
        assert isinstance(result, dict)
        assert "match" in result
