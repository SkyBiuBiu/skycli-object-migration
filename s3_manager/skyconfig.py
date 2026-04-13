import os
import yaml
import threading
from pathlib import Path
from typing import Optional, Dict, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_instance):
        self.config_instance = config_instance

    def on_modified(self, event):
        if event.src_path == str(self.config_instance.config_file):
            self.config_instance._load_config()


class SkyConfig:
    DEFAULT_CONFIG_DIR = Path.home() / ".skycli"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

    def __init__(self):
        self.config_dir = self.DEFAULT_CONFIG_DIR
        self.config_file = self.DEFAULT_CONFIG_FILE
        self.profiles: Dict[str, Dict] = {}
        self.default_profile: Optional[str] = None
        self._config_lock = threading.RLock()
        self._observer = None
        self._ensure_config_dir()
        self._load_config()
        self._start_watching()

    def _ensure_config_dir(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def _start_watching(self):
        """Start file system observer to monitor config file changes.

        Uses watchdog to watch for modifications to the config file
        and automatically reloads configuration when changes are detected.
        """
        try:
            event_handler = ConfigFileHandler(self)
            self._observer = Observer()
            self._observer.schedule(event_handler, str(self.config_dir), recursive=False)
            self._observer.start()
        except Exception:
            pass

    def _stop_watching(self):
        """Stop the file system observer.

        Should be called during cleanup or when configuration watching
        is no longer needed.
        """
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def _load_config(self):
        """Load configuration from YAML file.

        Thread-safe method that acquires a lock before reading
        the config file and parsing YAML content.
        """
        with self._config_lock:
            if not self.config_file.exists():
                return

            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}

                self.profiles = config.get("profiles", {})
                self.default_profile = config.get("default")
            except Exception:
                pass

    def _save_config(self):
        """Save configuration to YAML file.

        Thread-safe method that acquires a lock before writing
        the current configuration state to the config file.
        """
        with self._config_lock:
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
        signature_version: str = "s3v4",
        profile: Optional[str] = None
    ):
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("Endpoint must start with http:// or https://")
        
        endpoint = endpoint.rstrip("/")
        
        with self._config_lock:
            profile_key = profile or "default"

            if profile_key not in self.profiles:
                self.profiles[profile_key] = {}

            self.profiles[profile_key][name] = {
                "endpoint": endpoint,
                "access_key": access_key,
                "secret_key": secret_key,
                "region": region,
                "use_path_style": use_path_style,
                "verify_ssl": verify_ssl,
                "signature_version": signature_version
            }

            if self.default_profile is None:
                self.default_profile = profile_key

            self._save_config()

    def get_profile(self, name: str, profile: Optional[str] = None, reload: bool = True) -> Optional[Dict]:
        if reload:
            self._load_config()
        
        with self._config_lock:
            profile_key = profile or self.default_profile or "default"
            return self.profiles.get(profile_key, {}).get(name)

    def list_profiles(self, profile: Optional[str] = None, reload: bool = True) -> List[Dict]:
        if reload:
            self._load_config()
        
        with self._config_lock:
            profile_key = profile or self.default_profile or "default"
            profiles_data = self.profiles.get(profile_key, {})
            return [
                {"name": name, **config}
                for name, config in profiles_data.items()
            ]

    def rm_profile(self, name: str, profile: Optional[str] = None) -> bool:
        with self._config_lock:
            self._load_config()
            profile_key = profile or self.default_profile or "default"

            if profile_key in self.profiles and name in self.profiles[profile_key]:
                del self.profiles[profile_key][name]
                self._save_config()
                return True
            return False

    def update_profile(
        self,
        name: str,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        use_path_style: Optional[bool] = None,
        verify_ssl: Optional[bool] = None,
        profile: Optional[str] = None
    ) -> bool:
        with self._config_lock:
            self._load_config()
            profile_key = profile or self.default_profile or "default"

            if profile_key not in self.profiles or name not in self.profiles[profile_key]:
                return False

            if endpoint is not None:
                if not endpoint.startswith(("http://", "https://")):
                    raise ValueError("Endpoint must start with http:// or https://")
                self.profiles[profile_key][name]["endpoint"] = endpoint.rstrip("/")
            
            if access_key is not None:
                self.profiles[profile_key][name]["access_key"] = access_key
            
            if secret_key is not None:
                self.profiles[profile_key][name]["secret_key"] = secret_key
            
            if region is not None:
                self.profiles[profile_key][name]["region"] = region
            
            if use_path_style is not None:
                self.profiles[profile_key][name]["use_path_style"] = use_path_style
            
            if verify_ssl is not None:
                self.profiles[profile_key][name]["verify_ssl"] = verify_ssl

            self._save_config()
            return True

    def set_default_profile(self, profile: str) -> bool:
        with self._config_lock:
            self._load_config()
            
            if profile not in self.profiles:
                return False
            
            self.default_profile = profile
            self._save_config()
            return True

    def test_connection(self, name: str, profile: Optional[str] = None) -> Dict:
        config = self.get_profile(name, profile)
        if not config:
            return {"success": False, "error": "Profile not found"}

        from .skyclient import SkyClient

        client = SkyClient(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            region=config.get("region", "us-east-1"),
            use_path_style=config.get("use_path_style", False),
            verify_ssl=config.get("verify_ssl", True),
            signature_version=config.get("signature_version", "s3v4")
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

    def clear_all(self):
        with self._config_lock:
            self.profiles = {}
            self.default_profile = None
            self._save_config()


config = SkyConfig()
