from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppSettings, get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

_DEFAULT_SOCKET = Path("/var/run/mysqld/mysqld.sock")


def _connect_args(settings: AppSettings) -> dict[str, str]:
    mysql = settings.mysql
    if mysql.host in {"127.0.0.1", "localhost"} and _DEFAULT_SOCKET.is_socket():
        return {"unix_socket": str(_DEFAULT_SOCKET)}
    return {}


def init_engine(settings: AppSettings | None = None) -> Engine:
    global _engine, _SessionLocal
    cfg = settings or get_settings()
    connect_args = _connect_args(cfg)
    # auth_socket root only works for OS root; password users must use TCP/password.
    if cfg.mysql.username == "root" and connect_args.get("unix_socket"):
        connect_args = {}
    _engine = create_engine(
        cfg.mysql.sqlalchemy_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine(settings: AppSettings | None = None):
    global _engine
    if _engine is None:
        init_engine(settings)
    return _engine


@contextmanager
def get_session(settings: AppSettings | None = None) -> Generator[Session, None, None]:
    global _SessionLocal
    if _SessionLocal is None:
        init_engine(settings)
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
