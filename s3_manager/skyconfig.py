import os
import yaml
from pathlib import Path
from typing import Optional, Dict, List


class SkyConfig:
    DEFAULT_CONFIG_DIR = Path.home() / ".skycli"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

    def __init__(self):
        self.config_dir = self.DEFAULT_CONFIG_DIR
        self.config_file = self.DEFAULT_CONFIG_FILE
        self.profiles: Dict[str, Dict] = {}
        self.default_profile: Optional[str] = None
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        if not self.config_file.exists():
            return

        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        self.profiles = config.get("profiles", {})
        self.default_profile = config.get("default")

    def _save_config(self):
        config = {
            "profiles": self.profiles,
            "default": self.default_profile
        }

        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def add_profile(
        self,
        name: str,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_path_style: bool = False,
        verify_ssl: bool = True,
        profile: Optional[str] = None
    ):
        profile_key = profile or "default"

        if profile_key not in self.profiles:
            self.profiles[profile_key] = {}

        self.profiles[profile_key][name] = {
            "endpoint": endpoint,
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region,
            "use_path_style": use_path_style,
            "verify_ssl": verify_ssl
        }

        if self.default_profile is None:
            self.default_profile = profile_key

        self._save_config()

    def get_profile(self, name: str, profile: Optional[str] = None) -> Optional[Dict]:
        self._load_config()
        profile_key = profile or self.default_profile or "default"
        return self.profiles.get(profile_key, {}).get(name)

    def list_profiles(self, profile: Optional[str] = None) -> List[Dict]:
        self._load_config()
        profile_key = profile or self.default_profile or "default"
        profiles_data = self.profiles.get(profile_key, {})
        return [
            {"name": name, **config}
            for name, config in profiles_data.items()
        ]

    def rm_profile(self, name: str, profile: Optional[str] = None):
        self._load_config()
        profile_key = profile or self.default_profile or "default"

        if profile_key in self.profiles and name in self.profiles[profile_key]:
            del self.profiles[profile_key][name]
            self._save_config()
            return True
        return False

    def test_connection(self, name: str, profile: Optional[str] = None) -> Dict:
        from .skyclient import SkyClient

        config = self.get_profile(name, profile)
        if not config:
            return {"success": False, "error": "Profile not found"}

        client = SkyClient(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            region=config.get("region", "us-east-1"),
            use_path_style=config.get("use_path_style", False),
            verify_ssl=config.get("verify_ssl", True)
        )

        return client.test_connection()

    def export_config(self, name: str, file_path: str, profile: Optional[str] = None):
        config = self.get_profile(name, profile)
        if not config:
            raise ValueError(f"Profile '{name}' not found")

        config_copy = {"name": name, **config}
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(config_copy, f, default_flow_style=False, allow_unicode=True)

    def import_config(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        name = config_data.pop("name")
        profile = config_data.pop("profile", None)

        self.add_profile(
            name=name,
            profile=profile,
            **config_data
        )


config = SkyConfig()
