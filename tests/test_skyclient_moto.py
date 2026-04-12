"""
SkyClient Moto 测试
使用 Moto 5 的 mock_aws 装饰器进行 S3 操作测试
"""
import pytest
from moto import mock_aws
import boto3
from s3_manager.skyclient import SkyClient


class TestSkyClientWithMoto:
    """SkyClient 基础功能测试（使用 Moto）"""
    
    @pytest.fixture(autouse=True)
    def setup_mock(self):
        """自动为每个测试方法设置 mock 环境"""
        self.mock = mock_aws()
        self.mock.start()
        yield
        self.mock.stop()
    
    @pytest.fixture
    def boto3_client(self):
        """创建原生 boto3 客户端用于验证"""
        return boto3.client('s3', region_name='us-east-1')
    
    @pytest.fixture
    def sky_client(self):
        """创建 SkyClient 实例"""
        return SkyClient(
            endpoint="https://s3.amazonaws.com",
            access_key="testing",
            secret_key="testing",
            region="us-east-1",
            use_path_style=False,
            verify_ssl=True
        )
    
    def test_client_creation(self, sky_client):
        """测试客户端创建"""
        assert sky_client.endpoint == "https://s3.amazonaws.com"
        assert sky_client.access_key == "testing"
        assert sky_client.region == "us-east-1"
    
    def test_test_connection(self, sky_client):
        """测试连接检测"""
        result = sky_client.test_connection()
        assert result.get("success") == True
        assert result.get("bucket_count") >= 0
    
    def test_create_bucket(self, sky_client, boto3_client):
        """测试创建存储桶"""
        bucket_name = "test-bucket"
        
        # 创建桶
        sky_client.create_bucket(bucket_name)
        
        # 验证桶存在
        assert sky_client.bucket_exists(bucket_name)
        
        # 使用原生 boto3 验证
        response = boto3_client.list_buckets()
        bucket_names = [b['Name'] for b in response['Buckets']]
        assert bucket_name in bucket_names
    
    def test_delete_bucket(self, sky_client, boto3_client):
        """测试删除存储桶"""
        bucket_name = "test-delete-bucket"
        
        # 创建并删除桶
        boto3_client.create_bucket(Bucket=bucket_name)
        assert sky_client.bucket_exists(bucket_name)
        
        sky_client.delete_bucket(bucket_name)
        assert not sky_client.bucket_exists(bucket_name)
    
    def test_list_buckets(self, sky_client, boto3_client):
        """测试列出存储桶"""
        # 创建多个桶
        for i in range(3):
            boto3_client.create_bucket(Bucket=f"test-bucket-{i}")
        
        buckets = sky_client.list_buckets()
        assert len(buckets) >= 3
        
        bucket_names = [b['Name'] for b in buckets]
        for i in range(3):
            assert f"test-bucket-{i}" in bucket_names
    
    def test_put_and_get_object(self, sky_client, boto3_client):
        """测试对象上传下载"""
        bucket = "test-bucket"
        key = "test-key.txt"
        content = b"Hello, Moto!"
        
        # 创建桶
        boto3_client.create_bucket(Bucket=bucket)
        
        # 上传对象
        result = sky_client.put_object(
            bucket=bucket,
            key=key,
            body=content,
            content_type="text/plain"
        )
        assert "ETag" in result
        
        # 下载对象
        response = sky_client.get_object(bucket, key)
        assert response['Body'].read() == content
    
    def test_head_object(self, sky_client, boto3_client):
        """测试获取对象元数据"""
        bucket = "test-bucket"
        key = "test-head.txt"
        content = b"Test content"
        metadata = {"project": "skycli", "env": "test"}
        
        # 创建桶并上传对象
        boto3_client.create_bucket(Bucket=bucket)
        boto3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            Metadata=metadata
        )
        
        # 获取对象信息
        info = sky_client.head_object(bucket, key)
        assert info['ContentLength'] == len(content)
        assert info['Metadata'].get('project') == 'skycli'
    
    def test_delete_object(self, sky_client, boto3_client):
        """测试删除对象"""
        bucket = "test-bucket"
        key = "test-delete.txt"
        
        # 创建桶并上传对象
        boto3_client.create_bucket(Bucket=bucket)
        boto3_client.put_object(Bucket=bucket, Key=key, Body=b"test")
        
        # 删除对象
        sky_client.delete_object(bucket, key)
        
        # 验证对象不存在
        objects = list(sky_client.list_objects_all(bucket))
        assert len(objects) == 0
    
    def test_copy_object(self, sky_client, boto3_client):
        """测试复制对象"""
        bucket = "test-bucket"
        source_key = "source.txt"
        target_key = "target.txt"
        content = b"Copy test"
        
        # 创建桶并上传源对象
        boto3_client.create_bucket(Bucket=bucket)
        boto3_client.put_object(Bucket=bucket, Key=source_key, Body=content)
        
        # 复制对象
        sky_client.copy_object(bucket, source_key, bucket, target_key)
        
        # 验证目标对象存在
        response = sky_client.get_object(bucket, target_key)
        assert response['Body'].read() == content
    
    def test_list_objects(self, sky_client, boto3_client):
        """测试列出对象"""
        bucket = "test-bucket"
        boto3_client.create_bucket(Bucket=bucket)
        
        # 上传多个对象
        for i in range(5):
            boto3_client.put_object(
                Bucket=bucket,
                Key=f"object-{i}.txt",
                Body=f"content-{i}".encode()
            )
        
        # 列出对象
        result = sky_client.list_objects(bucket)
        # list_objects 返回字典，包含 'objects' 键
        assert isinstance(result, dict)
        assert 'objects' in result
        assert len(result['objects']) >= 5
        
        keys = [obj['Key'] for obj in result['objects']]
        for i in range(5):
            assert f"object-{i}.txt" in keys
    
    def test_bucket_versioning(self, sky_client, boto3_client):
        """测试存储桶版本控制"""
        bucket = "test-versioning-bucket"
        
        # 创建桶
        boto3_client.create_bucket(Bucket=bucket)
        
        # 获取版本控制状态（初始应为禁用）
        status = sky_client.get_bucket_versioning(bucket)
        assert status in ["Enabled", "Suspended", None]
    
    def test_bucket_location(self, sky_client, boto3_client):
        """测试获取存储桶位置"""
        bucket = "test-location-bucket"
        
        # 创建桶
        boto3_client.create_bucket(Bucket=bucket)
        
        # 获取位置信息
        location = sky_client.get_bucket_location(bucket)
        assert location is not None
