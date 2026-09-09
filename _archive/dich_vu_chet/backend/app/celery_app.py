"""Celery application configuration."""
import os
from celery import Celery
from celery.schedules import crontab

# Use settings from config if available, otherwise fall back to env vars.
# We read from the environment directly here to avoid circular imports at
# module load time; the config module also reads from the same env vars.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Create Celery app
celery_app = Celery(
    "medical_supply_forecasting",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.forecast_tasks",
        "app.tasks.severity_inference_task",
    ],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,        # 5 minutes hard limit per task
    task_soft_time_limit=240,   # 4 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Result expiry — keep task results for 24 hours
    result_expires=86400,
)

# Route forecast tasks to a dedicated queue so other tasks stay responsive
celery_app.conf.task_routes = {
    "app.tasks.forecast_tasks.generate_forecast_async": {"queue": "forecasts"},
    "recompute_severity_rates": {"queue": "severity"},
}

# ── Periodic schedule (Celery beat) ───────────────────────────────────────────
# Áp dụng mục 5.2: định kỳ chạy lại quy tắc phân loại Nhẹ/TB/Nặng để cập nhật
# severity_rate. Chạy hằng đêm 02:30 UTC (~09:30 GMT+7) — giờ ít traffic.
celery_app.conf.beat_schedule = {
    "recompute-severity-rates-nightly": {
        "task": "recompute_severity_rates",
        "schedule": crontab(hour=2, minute=30),
        # force=False: chỉ phân loại ca chưa có severity, không ghi đè ca cũ
        "kwargs": {
            "force": False,
            "trigger": "scheduled",
            "updated_by": "system_scheduler",
        },
    },
}
