"""Database configuration and session management."""
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _ensure_db_dir() -> None:
    """Create the directory that will hold the SQLite file if it doesn't exist."""
    url = settings.DATABASE_URL
    # sqlite:///./data/medforecast.db  →  ./data/medforecast.db
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_db_dir()

# check_same_thread=False chỉ dành cho SQLite + FastAPI; Postgres/MySQL không nhận
# tham số này nên phải đặt connect_args theo loại DB.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,  # tự phát hiện kết nối chết (Postgres/VPS)
    echo=settings.DEBUG,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


def get_db() -> Generator:
    """FastAPI dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
