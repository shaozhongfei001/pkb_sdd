from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.database import create_db_engine, create_session_factory

from .config_loader import load_app_config


def create_db_resources(
    config_path: Path | None = None,
) -> tuple[AppConfig, Engine, sessionmaker[Session]]:
    """Create engine and session factory; no implicit commit."""
    config = load_app_config(config_path)
    engine = create_db_engine(config)
    factory = create_session_factory(engine)
    return config, engine, factory


def format_db_error(exc: Exception) -> str:
    """Map DB exceptions to operator-readable messages."""
    exc_name = type(exc).__name__
    if exc_name == "OperationalError":
        return "无法连接 MySQL，请检查 config/app.yaml 中的数据库配置。"
    return f"数据库查询失败：{exc}"
