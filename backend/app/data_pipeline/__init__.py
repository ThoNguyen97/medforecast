"""
data_pipeline — Tầng dữ liệu trung gian cho MedForecast.

Luồng: Nguồn (HIS SQL Server / file export) → STAGING → CLEAN (dim/fact) → MART.
MART phục vụ cả huấn luyện mô hình lẫn báo cáo tồn kho.

Thiết kế DB-agnostic: chạy SQLite khi làm đồ án, đổi sang PostgreSQL khi triển khai
chỉ bằng cách đổi biến môi trường PIPELINE_DB_URL (hoặc DATABASE_URL).
"""

from .icd_hierarchy import IcdHierarchy, TARGET_BLOCKS
from .connectors import SourceConnector, FileConnector, SqlServerConnector
from .pipeline import DataPipeline

__all__ = [
    "IcdHierarchy",
    "TARGET_BLOCKS",
    "SourceConnector",
    "FileConnector",
    "SqlServerConnector",
    "DataPipeline",
]
