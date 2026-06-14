from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "app.yaml"


class StorageConfig(BaseModel):
    source_registry_root: Path
    raw_vault_root: Path
    parsed_root: Path
    curated_root: Path
    quarantine_root: Path
    reports_root: Path


class MysqlConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    database: str = "personal_kb"
    username: str = "root"
    password: str = ""
    charset: str = "utf8mb4"

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )


class RawConfig(BaseModel):
    original_files_readonly: bool = True
    copy_unique_content_to_vault: bool = True


class AppSettings(BaseModel):
    app: dict[str, Any] = Field(default_factory=dict)
    storage: StorageConfig
    mysql: MysqlConfig
    raw: RawConfig = Field(default_factory=RawConfig)

    def ensure_readonly(self) -> None:
        if not self.raw.original_files_readonly:
            raise RuntimeError("original_files_readonly must be true to run inventory scan")


def load_settings(config_path: Path | None = None) -> AppSettings:
    path = config_path or _default_config_path()
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    storage_data = dict(data.get("storage") or {})
    for key, value in storage_data.items():
        if value is not None:
            storage_data[key] = Path(value)

    return AppSettings(
        app=data.get("app") or {},
        storage=StorageConfig(**storage_data),
        mysql=MysqlConfig(**(data.get("mysql") or {})),
        raw=RawConfig(**(data.get("raw") or {})),
    )


@lru_cache(maxsize=1)
def get_settings(config_path: str | None = None) -> AppSettings:
    path = Path(config_path) if config_path else None
    return load_settings(path)
