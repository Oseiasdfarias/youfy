from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import Settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(Settings().database_url, future=True, pool_pre_ping=True)

@contextmanager
def session_scope() -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(), future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
