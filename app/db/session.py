import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _normalize_database_url(url: str) -> str:
    cleaned = (url or "").strip()
    lower = cleaned.lower()
    if lower.startswith("postgresql+psycopg://"):
        return cleaned
    if lower.startswith("postgres://"):
        return f"postgresql+psycopg://{cleaned[len('postgres://'):]}"
    if lower.startswith("postgresql://"):
        return f"postgresql+psycopg://{cleaned[len('postgresql://'):]}"
    raise RuntimeError("DATABASE_URL must use Postgres (postgres:// or postgresql://)")


class _LazyEngine:
    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: Engine | None = None

    def get(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(_normalize_database_url(self._url))
        return self._engine

    def __getattr__(self, item: str) -> Any:
        return getattr(self.get(), item)


engine = _LazyEngine(DATABASE_URL)
_session_factory = sessionmaker(autocommit=False, autoflush=False)


def SessionLocal():
    return _session_factory(bind=engine.get())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
