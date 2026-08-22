"""CLI chạy đồng bộ một lần.

Ví dụ (dev, nguồn file, DB SQLite):
  PIPELINE_DB_URL=sqlite:///./data/medforecast_dw.db \
  python -m app.data_pipeline.run --source file \
      --data-dir ../data --icd-dir ../data

Triển khai (nguồn HIS SQL Server, DB Postgres):
  PIPELINE_DB_URL=postgresql+psycopg2://user:pass@host/medforecast \
  python -m app.data_pipeline.run --source sqlserver \
      --conn "mssql+pyodbc://user:pass@host/HIS?driver=ODBC+Driver+17+for+SQL+Server" \
      --icd-dir ../data
"""
from __future__ import annotations

import argparse
import json
import logging

from .connectors import FileConnector, SqlServerConnector
from .icd_hierarchy import IcdHierarchy


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="MedForecast data pipeline")
    ap.add_argument("--source", choices=["file", "sqlserver"], default="file")
    ap.add_argument("--data-dir", default="../data", help="thư mục file export (source=file)")
    ap.add_argument("--icd-dir", default="../data", help="thư mục chứa TM_ICD*.xlsx")
    ap.add_argument("--conn", help="chuỗi kết nối SQL Server (source=sqlserver)")
    ap.add_argument("--full", action="store_true", help="nạp lại toàn bộ (bỏ qua watermark)")
    ap.add_argument("--target-only", action="store_true", help="chỉ giữ 3 nhóm hô hấp đích")
    args = ap.parse_args()

    # Không bắt buộc có TM_ICD*.xlsx: nguồn STA đã kèm sẵn cột disease_group.
    hier = IcdHierarchy.from_dir_optional(args.icd_dir)

    if args.source == "file":
        connector = FileConnector(args.data_dir)
    else:
        if not args.conn:
            ap.error("--conn là bắt buộc khi --source sqlserver")
        connector = SqlServerConnector(args.conn)

    from .pipeline import DataPipeline
    pipe = DataPipeline(connector, hier, target_only=args.target_only)
    result = pipe.run(incremental=not args.full)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
