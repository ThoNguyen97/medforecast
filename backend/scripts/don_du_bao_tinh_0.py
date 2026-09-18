"""Dọn các bản dự báo THEO TỈNH không có căn cứ trong `disease_forecasts`.

Trước 17/09/2026, "Ghi nhận dự báo" ở mục Toàn quốc ghi kèm một bản cho MỌI
tỉnh có ca của nhóm bệnh — kể cả tỉnh chuỗi quá ngắn (ensemble không chạy) và
không có ca cùng kỳ 5 năm trước (heuristic = 0). Kết quả là các dòng
`predicted_cases = 0, baseline_cases = 0` không phải đầu ra mô hình, chỉ sinh
dòng "0 ca" ở Lịch sử và "0/0" ở bảng Dữ liệu ca bệnh gần đây.

Từ 17/09 backend không ghi những dòng đó nữa (`forecast_analysis._khong_co_can_cu`).
Script này xoá phần đã lỡ ghi. Bản Toàn quốc (`location IS NULL`) KHÔNG đụng.

Chạy từ backend/:  python scripts/don_du_bao_tinh_0.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

DIEU_KIEN = """
    location IS NOT NULL
    AND predicted_cases = 0
    AND COALESCE(baseline_cases, 0) = 0
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="chỉ liệt kê, không xoá")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text(f"""
            SELECT id, forecast_month, icd_code, location, created_at
            FROM disease_forecasts WHERE {DIEU_KIEN}
            ORDER BY forecast_month, icd_code, location""")).fetchall()
        if not rows:
            print("Không có dòng nào cần dọn.")
            return 0
        print(f"{len(rows)} dòng dự báo tỉnh không có căn cứ (0 ca, nền 0):")
        for r in rows:
            print(f"  #{r[0]:<4} {str(r[1])[:7]}  {r[2]:<8} {r[3]}")
        if args.dry_run:
            print("--dry-run: không xoá.")
            return 0

        ids = [r[0] for r in rows]
        # supply_requirements trỏ tới forecast_id — gỡ trước cho khỏi treo FK.
        ds_id = ",".join(str(i) for i in ids)  # id nội bộ, không phải input người dùng
        n_sr = db.execute(
            text(f"DELETE FROM supply_requirements WHERE forecast_id IN ({ds_id})")
        ).rowcount
        n_fc = db.execute(
            text(f"DELETE FROM disease_forecasts WHERE id IN ({ds_id})")
        ).rowcount
        db.commit()
        print(f"Đã xoá {n_fc} dòng disease_forecasts (+{n_sr} supply_requirements liên kết).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
