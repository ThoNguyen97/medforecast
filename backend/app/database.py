"""Database configuration and session management."""
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# .../backend/ — neo theo vị trí file, không theo thư mục làm việc.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _neo_duong_dan_sqlite() -> None:
    """Biến đường dẫn SQLite tương đối thành tuyệt đối theo backend/.

    "sqlite:///./data/medforecast.db" được resolve theo THƯ MỤC LÀM VIỆC của
    tiến trình. Chạy uvicorn từ chỗ khác backend/ là âm thầm dùng một file DB
    khác — _ensure_db_dir() còn mkdir hộ nên không có lỗi nào để mà thấy; mọi
    truy vấn vẫn chạy, chỉ là trên dữ liệu khác. Đã mất một buổi vì chuyện này:
    UI đọc một DB, DB Browser mở một DB khác.
    """
    url = settings.DATABASE_URL
    if not url.startswith("sqlite:///"):
        return
    p = Path(url[len("sqlite:///"):])
    if not p.is_absolute():
        p = (_BACKEND_ROOT / p).resolve()
        settings.DATABASE_URL = f"sqlite:///{p.as_posix()}"
    p.parent.mkdir(parents=True, exist_ok=True)


_neo_duong_dan_sqlite()

# check_same_thread=False chỉ dành cho SQLite + FastAPI; Postgres/MySQL không nhận
# tham số này nên phải đặt connect_args theo loại DB.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,  # tự phát hiện kết nối chết (Postgres/VPS)
    echo=settings.SQL_ECHO,
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
