"""Lập lịch chạy job đồng bộ định kỳ (near-realtime) bằng APScheduler.

Dùng cho triển khai: chạy nền trong tiến trình backend hoặc như một service riêng.
Mặc định chạy mỗi ngày 02:00. Đổi qua biến môi trường PIPELINE_CRON (định dạng cron).

Chạy độc lập:
    PIPELINE_DB_URL=postgresql+psycopg2://... \
    python -m app.data_pipeline.scheduler
"""
from __future__ import annotations

import logging
import os

from .connectors import FileConnector, SqlServerConnector
from .icd_hierarchy import IcdHierarchy
from .pipeline import DataPipeline

logger = logging.getLogger(__name__)


def build_pipeline() -> DataPipeline:
    icd_dir = os.environ.get("PIPELINE_ICD_DIR", "../data")
    hier = IcdHierarchy.from_files(f"{icd_dir}/TM_ICD.xlsx", f"{icd_dir}/TM_ICD_CHUONG.xlsx")
    source = os.environ.get("PIPELINE_SOURCE", "file")
    if source == "sqlserver":
        conn = os.environ["PIPELINE_SQLSERVER_CONN"]
        connector = SqlServerConnector(conn)
    else:
        connector = FileConnector(os.environ.get("PIPELINE_DATA_DIR", "../data"))
    return DataPipeline(connector, hier)


def run_once():
    """Một lần đồng bộ (gọi được từ scheduler hoặc thủ công)."""
    result = build_pipeline().run(incremental=True)
    logger.info("Sync done: %s", result)
    return result


def start_scheduler():
    """Khởi động lịch nền. Cần: pip install apscheduler."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    cron = os.environ.get("PIPELINE_CRON", "0 2 * * *")  # 02:00 mỗi ngày
    sched = BlockingScheduler(timezone=os.environ.get("TZ", "Asia/Ho_Chi_Minh"))
    sched.add_job(run_once, CronTrigger.from_crontab(cron), id="medforecast_sync",
                  max_instances=1, coalesce=True)
    logger.info("Scheduler started, cron=%s", cron)
    run_once()  # chạy ngay 1 lần khi khởi động
    sched.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    start_scheduler()
# eof
