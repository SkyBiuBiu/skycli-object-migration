import pytest
import sys
import io
from unittest.mock import patch, MagicMock
from s3_manager.skycli import main
from .conftest import TEST_ENDPOINT, TEST_ACCESS_KEY, TEST_SECRET_KEY


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

    def test_cli_migrate_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "migrate", "--help"]
                main()
            assert pytest_wrapped_e.value.code == 0

    def test_cli_sync_help(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                sys.argv = ["skycli", "sync", "--help"]
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
            assert "added successfully" in output.lower()

    @patch("s3_manager.skycli.config")
    def test_config_list(self, mock_config):
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
            assert "successful" in output.lower() or "✓" in output

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
