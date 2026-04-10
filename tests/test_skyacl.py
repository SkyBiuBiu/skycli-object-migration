import pytest
from s3_manager.skyacl import SkyACL
from s3_manager.skyclient import SkyClient
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_REGION, TEST_BUCKET_1


@pytest.fixture
def acl_handler():
    client = SkyClient(
        endpoint=TEST_ENDPOINT,
        access_key=TEST_ACCESS_KEY,
        secret_key=TEST_SECRET_KEY,
        region=TEST_REGION,
        use_path_style=True,
        verify_ssl=False
    )
    return SkyACL(client)


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


class TestSkyACL:
    def test_get_object_acl(self, acl_handler, client):
        key = "acl_get_test.txt"
        client.put_object(TEST_BUCKET_1, key, b"ACL test content")

        acl = acl_handler.get(TEST_BUCKET_1, key)
        assert "Owner" in acl
        assert "Grants" in acl
        assert isinstance(acl["Grants"], list)

    def test_get_bucket_acl(self, acl_handler, client):
        acl = acl_handler.get(TEST_BUCKET_1)
        assert "Owner" in acl
        assert "Grants" in acl

    def test_set_object_acl_canned(self, acl_handler, client):
        key = "acl_set_test.txt"
        client.put_object(TEST_BUCKET_1, key, b"Set ACL test")

        acl_handler.set(TEST_BUCKET_1, key, acl="private")
        acl = acl_handler.get(TEST_BUCKET_1, key)
        assert "Owner" in acl

    @pytest.mark.skip(reason="MinIO does not support full ACL copy operations")
    def test_copy_acl(self, acl_handler, client):
        source_key = "acl_source.txt"
        target_key = "acl_target.txt"
        content = b"ACL copy test"

        client.put_object(TEST_BUCKET_1, source_key, content)
        client.put_object(TEST_BUCKET_1, target_key, content)

        acl_handler.copy(
            source_bucket=TEST_BUCKET_1,
            source_key=source_key,
            target_bucket=TEST_BUCKET_1,
            target_key=target_key
        )

        source_acl = acl_handler.get(TEST_BUCKET_1, source_key)
        target_acl = acl_handler.get(TEST_BUCKET_1, target_key)

        assert source_acl["Owner"]["ID"] == target_acl["Owner"]["ID"]

    def test_compare_acl_same(self, acl_handler, client):
        key1 = "acl_compare_1.txt"
        key2 = "acl_compare_2.txt"

        client.put_object(TEST_BUCKET_1, key1, b"content1")
        client.put_object(TEST_BUCKET_1, key2, b"content2")

        acl1 = acl_handler.get(TEST_BUCKET_1, key1)
        acl2 = acl_handler.get(TEST_BUCKET_1, key2)

        result = acl_handler.compare(acl1, acl2)
        assert result["owner_match"] == True

    def test_format_acl(self, acl_handler, client):
        key = "acl_format_test.txt"
        client.put_object(TEST_BUCKET_1, key, b"Format ACL test")

        acl = acl_handler.get(TEST_BUCKET_1, key)
        formatted = acl_handler.format_acl(acl)

        assert isinstance(formatted, str)
        assert "Owner:" in formatted
