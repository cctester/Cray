"""
Configuration management for Cray.
"""

import os
import json
from pathlib import Path
from typing import Literal, Optional, Any, Dict
from dataclasses import dataclass, field, asdict


@dataclass
class StorageConfig:
    """Storage configuration."""
    backend: Literal["json", "sqlite", "postgres"] = "json"
    data_dir: str = "~/.cray/data"
    db_path: str = "~/.cray/cray.db"
    postgres_url: str = ""


@dataclass
class Config:
    """Cray configuration."""
    storage: StorageConfig = field(default_factory=StorageConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file or environment."""
        config = cls()

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
                if "storage" in data:
                    config.storage = StorageConfig(**data["storage"])
        else:
            config.storage.backend = os.environ.get("CRAY_STORAGE_BACKEND", "json")
            config.storage.data_dir = os.environ.get("CRAY_DATA_DIR", "~/.cray/data")
            config.storage.db_path = os.environ.get("CRAY_DB_PATH", "~/.cray/cray.db")
            config.storage.postgres_url = os.environ.get("CRAY_POSTGRES_URL", "")

        config.storage.data_dir = str(Path(config.storage.data_dir).expanduser())
        config.storage.db_path = str(Path(config.storage.db_path).expanduser())

        return config

    def save(self, config_path: str) -> None:
        """Save configuration to file."""
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)


_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load(config_path)
    return _config


def reset_config() -> None:
    """Reset global config (for testing)."""
    global _config
    _config = None
