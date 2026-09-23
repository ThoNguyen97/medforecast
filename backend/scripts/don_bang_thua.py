# -*- coding: utf-8 -*-
"""Dọn 12 bảng SQLite không còn thuộc DSS 3 tầng (kiểm toán lược đồ 23/09/2026).

    python scripts/don_bang_thua.py [--db backend/data/medforecast.db] [--dry-run]

Nhóm bỏ:
  mua sắm / "đường thứ ba"  : supply_requirements, supply_recommendations, procurement_plans
  định mức nhập tay 3 mức    : severity_rates, disease_supply_norms, conversion_ratios,
                               case_supply_usage
  cảnh báo lưu bảng (cũ)     : alerts  (Dashboard v2 tính động từ dss_alerts)
  tầng pipeline không ai đọc : stg_case_supply, stg_inventory, fact_supply_usage,
                               fact_inventory_snapshot

An toàn:
  * Sao lưu file DB trước (data/saoluu_<ts>_truoc_don_bang_medforecast.db).
  * Tất cả bảng bỏ chỉ có FK trỏ RA (medical_supplies / users / disease_cases /
    disease_forecasts) — không bảng giữ lại nào trỏ vào chúng; 4 view local chỉ
    đọc fact_usage_total, fact_cases_by_care_level, system_config.
  * Model ORM tương ứng đã gỡ khỏi app/models/__init__.py, nên create_all() lúc
    khởi động sẽ KHÔNG tạo lại các bảng này.
  * Chạy lại vô hại (DROP TABLE IF EXISTS).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BANG_BO = [
    "supply_requirements", "supply_recommendations", "procurement_plans",
    "severity_rates", "disease_supply_norms", "conversion_ratios", "case_supply_usage",
    "alerts",
    "stg_case_supply", "stg_inventory", "fact_supply_usage", "fact_inventory_snapshot",
]
VIEW_KIEM = ["v_supply_active", "v_supply_focus", "v_supply_daily_demand", "v_care_level_share"]
BANG_LOI = ["fact_usage_total", "fact_cases_by_care_level", "fact_usage_by_care_level",
            "fact_inventory_lot", "mart_monthly_cases_by_block", "fact_disease_case",
            "medical_supplies", "inventory", "disease_cases", "disease_forecasts",
            "system_config", "users"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data" / "medforecast.db"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--khong-sao-luu", action="store_true")
    a = ap.parse_args()
    db_path = Path(a.db)
    if not db_path.exists():
        print(f"Không thấy DB: {db_path}"); return 2

    con = sqlite3.connect(db_path)
    ton_tai = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    se_bo = [t for t in BANG_BO if t in ton_tai]
    print(f"DB: {db_path}")
    for t in se_bo:
        n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  bỏ  {t:<26} {n:>8} dòng")
    for t in BANG_BO:
        if t not in ton_tai:
            print(f"  (đã không còn) {t}")
    if a.dry_run:
        print("--dry-run: không đổi gì."); return 0

    if not a.khong_sao_luu:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bk = db_path.parent / f"saoluu_{ts}_truoc_don_bang_{db_path.name}"
        con.close()
        shutil.copy2(db_path, bk)
        print(f"Đã sao lưu: {bk}")
        con = sqlite3.connect(db_path)

    con.execute("PRAGMA foreign_keys=OFF")
    for t in se_bo:
        con.execute(f'DROP TABLE IF EXISTS "{t}"')
    con.commit()

    # Kiểm: view còn chạy, bảng lõi còn nguyên, integrity ok
    loi = []
    for v in VIEW_KIEM:
        try:
            con.execute(f"SELECT * FROM {v} LIMIT 1").fetchall()
        except sqlite3.Error as e:
            loi.append(f"view {v}: {e}")
    con_lai = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in BANG_LOI:
        if t not in con_lai:
            loi.append(f"thiếu bảng lõi {t}")
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    if ic != "ok":
        loi.append(f"integrity_check: {ic}")
    if loi:
        print("LỖI:\n  " + "\n  ".join(loi)); return 1

    con.execute("VACUUM")
    con.close()
    print(f"Đã bỏ {len(se_bo)} bảng, còn {len(con_lai)} bảng; 4 view OK; integrity ok; VACUUM xong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
