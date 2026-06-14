from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig, MysqlConfig


def build_database_url(mysql: MysqlConfig) -> str:
    return (
        f"mysql+pymysql://{mysql.username}:{mysql.password}"
        f"@{mysql.host}:{mysql.port}/{mysql.database}?charset={mysql.charset}"
    )


def create_db_engine(config: AppConfig) -> Engine:
    return create_engine(
        build_database_url(config.mysql),
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
