"""Cấu hình logging: console và tệp xoay vòng (backend/logs/medforecast.log)."""
import logging
import logging.handlers
from pathlib import Path

# Neo thư mục log theo vị trí file, không phụ thuộc thư mục làm việc.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent  # .../backend/
LOGS_DIR = _BACKEND_ROOT / "logs"


def setup_logging(log_level: str = "INFO") -> None:
    """Cấu hình logging toàn ứng dụng với handler console và tệp xoay vòng."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Tránh nhân đôi handler khi gọi lại
    if root_logger.handlers:
        root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # Tệp xoay vòng: 10 MB mỗi tệp, giữ 5 bản
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "medforecast.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(log_format))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # echo=True đặt mức trên logger con Engine nên phải hạ riêng
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    # watchfiles ghi INFO vào tệp log trong thư mục đang theo dõi gây reload liên tục
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured — log files at: %s", LOGS_DIR)
