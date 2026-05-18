import json
import os
import sys
from pathlib import Path

# Funciona tanto em script Python quanto em executavel PyInstaller (.exe)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

CONFIG_FILE = BASE_DIR / "config" / "settings.json"

DEFAULTS = {
    "scan_timeout": 2,
    "scan_threads": 50,
    "auto_scan": False,
    "auto_scan_interval": 300,
    "default_ssh_port": 22,
    "default_api_port": 8728,
    "theme": "dark",
    "log_level": "INFO",
    "db_path": str(BASE_DIR / "config" / "netdiscovery.db"),
    "log_path": str(BASE_DIR / "logs" / "netdiscovery.log"),
    "backups_path": str(BASE_DIR / "config" / "backups"),
    "scan_range": "",
    "default_mikrotik_user": "admin",
    "default_ubnt_user": "ubnt",
    "ping_timeout_ms": 500,
    "github_repo": "wesleyfilho/FieldTool_Build",
}


class Config:
    _instance = None
    _data: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._data = {**DEFAULTS, **json.load(f)}
            except Exception:
                self._data = dict(DEFAULTS)
        else:
            self._data = dict(DEFAULTS)
            self._save()

    def _save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def get_all(self) -> dict:
        return dict(self._data)

    def update(self, data: dict):
        self._data.update(data)
        self._save()


config = Config()
