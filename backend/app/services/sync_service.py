"""Service đồng bộ dữ liệu từ nguồn (HIS SQL Server / file) vào DB trung gian.

Bọc DataPipeline để dashboard gọi qua API:
  - run_sync(): kéo dữ liệu MỚI (khám bệnh + tồn kho) → STAGING → CLEAN → MART.
  - get_status(): trạng thái lần đồng bộ gần nhất + số liệu hiện có.

Cấu hình qua biến môi trường (không hard-code):
  PIPELINE_SOURCE        = file | sqlserver          (mặc định file)
  PIPELINE_DATA_DIR      = thư mục file export        (nguồn file)
  PIPELINE_ICD_DIR       = thư mục TM_ICD*.xlsx
  PIPELINE_SQLSERVER_CONN= chuỗi kết nối HIS          (nguồn sqlserver)
Pipeline ghi vào DB theo PIPELINE_DB_URL, mặc định = DATABASE_URL của app
(để mart nằm CHUNG DB với ứng dụng).
"""
from __future__ import annotations
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_pipeline.icd_hierarchy import IcdHierarchy
from app.data_pipeline.connectors import FileConnector, SqlServerConnector
from app.data_pipeline.pipeline import DataPipeline


def _build_pipeline() -> DataPipeline:
    icd_dir = os.environ.get("PIPELINE_ICD_DIR", "../data")
    hier = IcdHierarchy.from_files(f"{icd_dir}/TM_ICD.xlsx",
                                   f"{icd_dir}/TM_ICD_CHUONG.xlsx")
    source = os.environ.get("PIPELINE_SOURCE", "file")
    if source == "sqlserver":
        conn = os.environ.get("PIPELINE_SQLSERVER_CONN")
        if not conn:
            raise RuntimeError("Thiếu PIPELINE_SQLSERVER_CONN cho nguồn HIS.")
        connector = SqlServerConnector(conn)
    else:
        connector = FileConnector(os.environ.get("PIPELINE_DATA_DIR", "../data"))
    return DataPipeline(connector, hier)


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    def run_sync(self, full: bool = False) -> dict:
        """Chạy một lần đồng bộ. incremental theo watermark (mặc định)."""
        result = _build_pipeline().run(incremental=not full)
        result["mode"] = "full" if full else "incremental"
        return result

    def get_status(self) -> dict:
        """Trạng thái đồng bộ + số liệu hiện có (an toàn nếu bảng chưa tồn tại)."""
        out = {"last_sync": None, "disease_cases": 0, "inventory_items": 0,
               "latest_period": None, "history": []}

        def q1(sql):
            try:
                return self.db.execute(text(sql)).fetchone()
            except Exception:
                return None

        row = q1("SELECT source, last_period, rows_ingested, rows_rejected, status, "
                 "run_at FROM sync_state WHERE status='ok' ORDER BY id DESC LIMIT 1")
        if row:
            out["last_sync"] = {"source": row[0], "last_period": row[1],
                                "rows_ingested": row[2], "rows_rejected": row[3],
                                "status": row[4], "run_at": str(row[5])}
        c = q1("SELECT COUNT(*), COALESCE(SUM(cases),0), MAX(period) FROM fact_disease_case")
        if c:
            out["disease_cases"] = int(c[1] or 0)
            out["latest_period"] = c[2]
        i = q1("SELECT COUNT(*) FROM mart_inventory")
        if i:
            out["inventory_items"] = int(i[0] or 0)
        hist = None
        try:
            hist = self.db.execute(text(
                "SELECT source, last_period, rows_ingested, status, run_at "
                "FROM sync_state ORDER BY id DESC LIMIT 5")).fetchall()
        except Exception:
            hist = []
        out["history"] = [{"source": r[0], "last_period": r[1], "rows_ingested": r[2],
                           "status": r[3], "run_at": str(r[4])} for r in (hist or [])]
        return out
