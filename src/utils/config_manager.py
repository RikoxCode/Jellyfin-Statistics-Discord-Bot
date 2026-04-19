import json
import os
import shutil
from pathlib import Path

import yaml

BUNDLED_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
RUNTIME_CONFIG_DIR = Path(os.getenv("APP_CONFIG_DIR", str(BUNDLED_CONFIG_DIR))).resolve()
FUNCTION_CONFIG_PATH = RUNTIME_CONFIG_DIR / "functions.yml"
APP_CONFIG_PATH = RUNTIME_CONFIG_DIR / "config.yml"
CHANNELS_CONFIG_PATH = RUNTIME_CONFIG_DIR / "channels.json"


def ensure_runtime_config():
    RUNTIME_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    for file_name in ("config.yml", "functions.yml"):
        source_path = BUNDLED_CONFIG_DIR / file_name
        target_path = RUNTIME_CONFIG_DIR / file_name
        if not target_path.exists() and source_path.exists():
            shutil.copy2(source_path, target_path)

    if not CHANNELS_CONFIG_PATH.exists():
        with open(CHANNELS_CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump({"guilds": {}}, file, indent=2, ensure_ascii=False)


ensure_runtime_config()


class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        if not self.config_path.is_absolute():
            self.config_path = (RUNTIME_CONFIG_DIR / self.config_path.name).resolve()
        self.config = self.load_config()

    def get(self, key, default=None):
        if not key:
            return self.config

        current = self.config
        for part in str(key).split("."):
            if not isinstance(current, dict):
                return default

            if part in current:
                current = current[part]
                continue

            if part == "category" and "catagory" in current:
                current = current["catagory"]
                continue

            return default

        return current

    def load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def reload(self):
        self.config = self.load_config()
        return self.config


class FunctionConfigManager(ConfigManager):
    def __init__(self, config_path=FUNCTION_CONFIG_PATH):
        super().__init__(config_path)


class AppConfigManager(ConfigManager):
    def __init__(self, config_path=APP_CONFIG_PATH):
        super().__init__(config_path)