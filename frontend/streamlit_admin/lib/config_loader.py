from __future__ import annotations

import os
from pathlib import Path

from app.core.config import AppConfig, load_config

DEFAULT_CONFIG_ENV = "PKB_CONFIG"


def resolve_config_path() -> Path | None:
    override = os.environ.get(DEFAULT_CONFIG_ENV, "").strip()
    if override:
        return Path(override)
    return None


def load_app_config(config_path: Path | None = None) -> AppConfig:
    """Load AppConfig via backend loader; honors PKB_CONFIG env override."""
    path = config_path or resolve_config_path()
    return load_config(path)
