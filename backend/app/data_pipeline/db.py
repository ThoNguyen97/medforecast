"""Engine/session cho DB trung gian.

Tách khỏi app.database để pipeline chạy độc lập (CLI, cron) và dễ test.
Ưu tiên PIPELINE_DB_URL, sau đó DATABASE_URL, cuối cùng SQLite mặc định.

Ví dụ Postgres (triển khai):  postgresql+psycopg2://user:pass@host:5432/medforecast
Ví dụ SQLite  (đồ án/dev):    sqlite:///./data/medforecast_dw.db
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def get_db_url() -> str:
    url = (
        os.environ.get("PIPELINE_DB_URL")
        or os.environ.get("DATABASE_URL")
        or "sqlite:///./data/medforecast_dw.db"
    )
    return url


def make_engine(url: str | None = None):
    url = url or get_db_url()
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path not in (":memory:", ""):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres / others
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Tạo toàn bộ bảng của pipeline nếu chưa có."""
    from . import models  # noqa: F401  (đăng ký bảng vào metadata)
    Base.metadata.create_all(bind=engine)
