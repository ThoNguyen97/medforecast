"""Logging configuration with file rotation."""
import logging
import logging.handlers
from pathlib import Path

# Resolve the logs directory relative to this file's location so it works
# regardless of the working directory the server is started from.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent  # .../backend/
LOGS_DIR = _BACKEND_ROOT / "logs"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide logging with console + rotating file handlers."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on repeated calls (e.g. during tests)
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # Rotating file handler — 10 MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "medforecast.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(log_format))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured — log files at: %s", LOGS_DIR)
