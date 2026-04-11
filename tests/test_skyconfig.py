import pytest
import yaml
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from s3_manager.skyconfig import SkyConfig


@pytest.fixture
def temp_config_dir(tmp_path):
    config_dir = tmp_path / ".skycli"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    with patch.object(SkyConfig, 'DEFAULT_CONFIG_DIR', config_dir):
        with patch.object(SkyConfig, 'DEFAULT_CONFIG_FILE', config_file):
            config = SkyConfig()
            yield config
            
            config._stop_watching()


class TestSkyConfig:
    def test_add_profile(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        profiles = config.list_profiles()
        assert len(profiles) == 1
        assert profiles[0]["name"] == "test1"
        assert profiles[0]["endpoint"] == "http://localhost:9000"

    def test_add_multiple_profiles(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin1",
            secret_key="password1"
        )
        
        config.add_profile(
            name="test2",
            endpoint="http://localhost:9001",
            access_key="admin2",
            secret_key="password2"
        )
        
        profiles = config.list_profiles()
        assert len(profiles) == 2
        
        names = {p["name"] for p in profiles}
        assert names == {"test1", "test2"}

    def test_get_profile(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        profile = config.get_profile("test1")
        assert profile is not None
        assert profile["endpoint"] == "http://localhost:9000"

    def test_get_profile_not_found(self, temp_config_dir):
        config = temp_config_dir
        profile = config.get_profile("nonexistent")
        assert profile is None

    def test_update_profile(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        result = config.update_profile(
            name="test1",
            endpoint="http://localhost:9001",
            region="us-west-2"
        )
        
        assert result is True
        
        profile = config.get_profile("test1")
        assert profile["endpoint"] == "http://localhost:9001"
        assert profile["region"] == "us-west-2"

    def test_update_profile_not_found(self, temp_config_dir):
        config = temp_config_dir
        result = config.update_profile(
            name="nonexistent",
            endpoint="http://localhost:9000"
        )
        assert result is False

    def test_rm_profile(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        result = config.rm_profile("test1")
        assert result is True
        
        profiles = config.list_profiles()
        assert len(profiles) == 0

    def test_rm_profile_not_found(self, temp_config_dir):
        config = temp_config_dir
        result = config.rm_profile("nonexistent")
        assert result is False

    def test_set_default_profile(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        result = config.set_default_profile("default")
        assert result is True
        assert config.default_profile == "default"

    def test_set_default_profile_not_found(self, temp_config_dir):
        config = temp_config_dir
        result = config.set_default_profile("nonexistent")
        assert result is False

    def test_endpoint_validation(self, temp_config_dir):
        config = temp_config_dir
        
        with pytest.raises(ValueError, match="Endpoint must start with"):
            config.add_profile(
                name="invalid",
                endpoint="localhost:9000",
                access_key="admin",
                secret_key="password"
            )

    def test_endpoint_trailing_slash(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000/",
            access_key="admin",
            secret_key="password"
        )
        
        profile = config.get_profile("test1")
        assert profile["endpoint"] == "http://localhost:9000"

    def test_config_file_sync(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        with open(config.config_file, "r") as f:
            saved_config = yaml.safe_load(f)
        
        assert "test1" in saved_config["profiles"]["default"]

    def test_multiple_profiles(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="aws",
            endpoint="https://s3.amazonaws.com",
            access_key="aws_key",
            secret_key="aws_secret",
            profile="cloud"
        )
        
        config.add_profile(
            name="minio",
            endpoint="http://localhost:9000",
            access_key="minio_key",
            secret_key="minio_secret",
            profile="onprem"
        )
        
        aws_profiles = config.list_profiles(profile="cloud")
        minio_profiles = config.list_profiles(profile="onprem")
        
        assert len(aws_profiles) == 1
        assert len(minio_profiles) == 1
        assert aws_profiles[0]["name"] == "aws"
        assert minio_profiles[0]["name"] == "minio"

    def test_clear_all(self, temp_config_dir):
        config = temp_config_dir
        
        config.add_profile(
            name="test1",
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="password"
        )
        
        config.add_profile(
            name="test2",
            endpoint="http://localhost:9001",
            access_key="admin2",
            secret_key="password2"
        )
        
        config.clear_all()
        
        profiles = config.list_profiles()
        assert len(profiles) == 0
        assert config.default_profile is None

    def test_thread_safety(self, temp_config_dir):
        import threading
        config = temp_config_dir
        
        def add_profile(name):
            config.add_profile(
                name=name,
                endpoint=f"http://localhost:{9000 + int(name[4:])}",
                access_key="admin",
                secret_key="password"
            )
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_profile, args=(f"test{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        profiles = config.list_profiles()
        assert len(profiles) == 5
