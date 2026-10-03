from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url)


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()


@contextmanager
def open_session() -> Generator[Session]:
    with Session(get_engine()) as session:
        yield session


def get_session() -> Generator[Session]:
    with open_session() as session:
        yield session
