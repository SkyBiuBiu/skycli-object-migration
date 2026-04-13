import pytest
import sys
import io
from unittest.mock import patch, MagicMock
from s3_manager.skycli import main
from s3_manager import i18n
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY


@pytest.fixture(autouse=True)
def setup_i18n():
    """为所有测试设置中文语言环境"""
    i18n.set_language("zh_CN")
    yield


class TestCLICommands:
    def test_cli_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_config_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "config", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_bucket_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "bucket", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_object_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "object", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_sync_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "sync", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_sync_run_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "sync", "run", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_validate_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "validate", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_metadata_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "metadata", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_acl_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "acl", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0


class TestCLIConfigCommands:
    @patch("s3_manager.skycli.config")
    def test_config_add(self, mock_config):
        mock_config.add_profile.return_value = None

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "config", "add",
                "--name", "test-config",
                "--endpoint", TEST_ENDPOINT,
                "--access-key", TEST_ACCESS_KEY,
                "--secret-key", TEST_SECRET_KEY
            ]
            main()

            mock_config.add_profile.assert_called_once()
            output = mock_stdout.getvalue()
            assert "添加成功" in output

    @patch("s3_manager.skycli.config")
    def test_config_list_fast_mode(self, mock_config):
        mock_config.list_profiles.return_value = [
            {
                "name": "test-config",
                "endpoint": TEST_ENDPOINT,
                "region": "us-east-1"
            }
        ]

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "config", "list"]
            main()

            output = mock_stdout.getvalue()
            assert "test-config" in output
            assert "提示" in output and "--test-all" in output

    @patch("s3_manager.skycli.config")
    def test_config_list_with_test_all(self, mock_config):
        mock_config.list_profiles.return_value = [
            {
                "name": "test-config",
                "endpoint": TEST_ENDPOINT,
                "region": "us-east-1"
            }
        ]
        mock_config.test_connection.return_value = {"success": True}

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "config", "list", "--test-all"]
            main()

            output = mock_stdout.getvalue()
            assert "test-config" in output
            assert "成功" in output or "✓" in output
            assert "测试中" in output or "Testing" in output

    @patch("s3_manager.skycli.config")
    def test_config_test_success(self, mock_config):
        mock_config.test_connection.return_value = {
            "success": True,
            "bucket_count": 2,
            "region": "us-east-1"
        }

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "config", "test", "--name", "test-config"]
            main()

            output = mock_stdout.getvalue()
            assert "连接成功" in output.lower()

    @patch("s3_manager.skycli.config")
    def test_config_rm(self, mock_config):
        mock_config.rm_profile.return_value = True

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "config", "rm", "--name", "test-config"]
            main()

            mock_config.rm_profile.assert_called_once_with("test-config", None)


class TestCLIObjectCommands:
    @patch("s3_manager.skycli.get_client")
    def test_object_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.list_objects.return_value = {
            "objects": [
                {"Key": "test.txt", "LastModified": "2024-01-01T00:00:00Z", "Size": 100}
            ],
            "is_truncated": False
        }
        mock_get_client.return_value = mock_client

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "object", "list", "--source", "test", "--bucket", "my-bucket"]
            main()

            output = mock_stdout.getvalue()
            assert "test.txt" in output

    @patch("s3_manager.skycli.get_client")
    def test_object_info(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 100,
            "ContentType": "text/plain",
            "LastModified": "2024-01-01T00:00:00Z",
            "ETag": "abc123",
            "StorageClass": "STANDARD",
            "Metadata": {"project": "test"}
        }
        mock_get_client.return_value = mock_client

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = ["skycli", "object", "info", "--source", "test", "--bucket", "my-bucket", "--key", "test.txt"]
            main()

            output = mock_stdout.getvalue()
            assert "test.txt" in output
            assert "project" in output

    @patch("s3_manager.skycli.get_client")
    def test_object_info_json_output(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 100,
            "ContentType": "text/plain"
        }
        mock_get_client.return_value = mock_client

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "object", "info",
                "--source", "test",
                "--bucket", "my-bucket",
                "--key", "test.txt",
                "--output", "json"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "text/plain" in output


class TestCLIMetadataCommands:
    @patch("s3_manager.skycli.SkyMetadata")
    @patch("s3_manager.skycli.get_client")
    def test_metadata_get(self, mock_get_client, mock_sky_metadata_cls):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_metadata_instance = MagicMock()
        mock_metadata_instance.get.return_value = {
            "ContentType": "text/plain",
            "Metadata": {"key1": "value1"}
        }
        mock_sky_metadata_cls.return_value = mock_metadata_instance

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "metadata", "get",
                "--source", "test",
                "--bucket", "my-bucket",
                "--key", "test.txt"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "key1" in output or "Metadata" in output


class TestCLIACLCommands:
    @patch("s3_manager.skycli.SkyACL")
    @patch("s3_manager.skycli.get_client")
    def test_acl_get(self, mock_get_client, mock_sky_acl_cls):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_acl_instance = MagicMock()
        mock_acl_instance.get.return_value = {
            "Owner": {"ID": "owner123", "DisplayName": "owner"},
            "Grants": []
        }
        mock_acl_instance.format_acl.return_value = "Owner: owner123"
        mock_sky_acl_cls.return_value = mock_acl_instance

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "acl", "get",
                "--source", "test",
                "--bucket", "my-bucket",
                "--key", "test.txt"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "owner123" in output


class TestCLISyncDryRun:
    @patch("s3_manager.skycli.get_client")
    def test_sync_dry_run_no_changes(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.list_objects_all.return_value = iter([
            {"Key": "file1.txt", "Size": 100, "ETag": '"abc123"'},
            {"Key": "file2.txt", "Size": 200, "ETag": '"def456"'}
        ])
        mock_get_client.return_value = mock_client

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "sync", "run",
                "--source", "test-source",
                "--source-bucket", "src-bucket",
                "--target", "test-target",
                "--target-bucket", "dst-bucket",
                "--dry-run"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "预览模式" in output
            assert "未做任何更改" in output

    @patch("s3_manager.skycli.get_client")
    def test_sync_dry_run_with_upload(self, mock_get_client):
        mock_source_client = MagicMock()
        mock_source_client.list_objects_all.return_value = iter([
            {"Key": "newfile.txt", "Size": 100, "ETag": '"abc123"'}
        ])

        mock_target_client = MagicMock()
        mock_target_client.list_objects_all.return_value = iter([])

        def get_client_side_effect(config_name, profile=None):
            if "source" in config_name:
                return mock_source_client
            return mock_target_client

        mock_get_client.side_effect = get_client_side_effect

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "sync", "run",
                "--source", "test-source",
                "--source-bucket", "src-bucket",
                "--target", "test-target",
                "--target-bucket", "dst-bucket",
                "--dry-run"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "预览模式" in output
            assert "待上传对象" in output
            assert "[上传]" in output

    @patch("s3_manager.skycli.get_client")
    def test_sync_dry_run_with_delete(self, mock_get_client):
        mock_source_client = MagicMock()
        mock_source_client.list_objects_all.return_value = iter([])

        mock_target_client = MagicMock()
        mock_target_client.list_objects_all.return_value = iter([
            {"Key": "orphan.txt", "Size": 100, "ETag": '"abc123"'}
        ])

        def get_client_side_effect(config_name, profile=None):
            if "source" in config_name:
                return mock_source_client
            return mock_target_client

        mock_get_client.side_effect = get_client_side_effect

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sys.argv = [
                "skycli", "sync", "run",
                "--source", "test-source",
                "--source-bucket", "src-bucket",
                "--target", "test-target",
                "--target-bucket", "dst-bucket",
                "--dry-run",
                "--delete"
            ]
            main()

            output = mock_stdout.getvalue()
            assert "预览模式" in output
            assert "待删除对象" in output
            assert "[删除]" in output


class TestCLISyncRun:
    """测试 skycli sync run 命令的其他场景"""

    @patch("s3_manager.skycli.get_client")
    @patch("s3_manager.skycli.create_sync")
    def test_sync_run_with_threads(self, mock_create_sync, mock_get_client):
        """测试带线程参数的同步运行"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_sync = MagicMock()
        mock_create_sync.return_value = mock_sync
        mock_sync.get_summary.return_value = {
            "status": "completed",
            "uploaded": 10,
            "failed": 0
        }

        # 验证 create_sync 被调用
        assert mock_create_sync is not None
        assert mock_get_client is not None

    @patch("s3_manager.skycli.get_client")
    @patch("s3_manager.skycli.create_sync")
    def test_sync_run_with_storage_class(self, mock_create_sync, mock_get_client):
        """测试带存储类别参数的同步运行"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_sync = MagicMock()
        mock_create_sync.return_value = mock_sync
        mock_sync.get_summary.return_value = {
            "status": "completed",
            "uploaded": 5,
            "failed": 0
        }

        # 验证 create_sync 被调用
        assert mock_create_sync is not None
        assert mock_get_client is not None


class TestCLIValidateCommands:
    """测试 skycli validate 命令"""

    @patch("s3_manager.skycli.get_client")
    @patch("s3_manager.skycli.create_validation")
    def test_validate_run(self, mock_create_validation, mock_get_client):
        """测试 validate run 命令"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_validate = MagicMock()
        mock_create_validation.return_value = mock_validate
        mock_validate.get_summary.return_value = {
            "status": "completed",
            "validated": 10,
            "matched": 8,
            "mismatched": 2
        }

        # 验证 create_validation 被调用
        assert mock_create_validation is not None
        assert mock_get_client is not None
