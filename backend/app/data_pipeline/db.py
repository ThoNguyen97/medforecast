"""Engine/session cho DB trung gian, tách khỏi app.database để pipeline chạy độc lập (CLI, cron)."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def get_db_url() -> str:
    """URL DB tầng dữ liệu: PIPELINE_DB_URL, DATABASE_URL, app.config, SQLite mặc định.

    Bậc app.config giữ mart/fact cùng file DB với app khi không có `.env`, nếu không Dashboard không thấy dữ liệu.
    """
    url = os.environ.get("PIPELINE_DB_URL") or os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from app.config import settings
        if settings.DATABASE_URL:
            return settings.DATABASE_URL
    except Exception:                                     # noqa: BLE001
        pass
    return "sqlite:///./data/medforecast_dw.db"


def make_engine(url: str | None = None):
    url = url or get_db_url()
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path not in (":memory:", ""):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Tạo toàn bộ bảng của pipeline nếu chưa có."""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
