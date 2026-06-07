from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.core.config import database_url, load_settings
from src.db.models import Base

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = load_settings()
        url = database_url(settings)
        kwargs: dict = {"echo": False, "future": True}
        if _is_sqlite(url):
            # 同步在后台线程写库、主线程读库，必须允许跨线程并避免连接池争用
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 60}
            kwargs["poolclass"] = NullPool
        _engine = create_engine(url, **kwargs)

        if _is_sqlite(url):

            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=60000")
                cursor.close()

        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        get_engine()
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
