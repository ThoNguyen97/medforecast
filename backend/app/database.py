"""Khởi tạo engine SQLAlchemy và quản lý phiên CSDL."""
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# .../backend/ — neo theo vị trí file, không theo thư mục làm việc.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _neo_duong_dan_sqlite() -> None:
    """Biến đường dẫn SQLite tương đối thành tuyệt đối theo backend/, tránh lệ thuộc cwd."""
    url = settings.DATABASE_URL
    if not url.startswith("sqlite:///"):
        return
    p = Path(url[len("sqlite:///"):])
    if not p.is_absolute():
        p = (_BACKEND_ROOT / p).resolve()
        settings.DATABASE_URL = f"sqlite:///{p.as_posix()}"
    p.parent.mkdir(parents=True, exist_ok=True)


_neo_duong_dan_sqlite()

# check_same_thread=False chỉ áp dụng cho SQLite; Postgres/MySQL không nhận tham số này.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,  # tự phát hiện kết nối chết (Postgres/VPS)
    echo=settings.SQL_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Lớp cơ sở khai báo cho mọi model SQLAlchemy."""
    pass


def get_db() -> Generator:
    """Dependency FastAPI: cấp một phiên CSDL và đóng sau khi xử lý xong."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
