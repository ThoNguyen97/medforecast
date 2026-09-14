#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xoá sạch DỮ LIỆU của app để nạp lại từ đầu bằng nguồn HIS.

    cd backend
    venv\\Scripts\\python scripts\\xoa_va_nap_lai.py

⚠ TẮT BACKEND TRƯỚC KHI CHẠY — SQLite khoá file, chạy song song sẽ lỗi
  "database is locked" hoặc tệ hơn là ghi dở dang.

XOÁ GÌ, GIỮ GÌ — và vì sao
Xoá "hết DB" theo nghĩa đen sẽ mất luôn tài khoản đăng nhập, cấu hình kết nối
HIS vừa lưu, định mức thuốc và tỷ lệ nặng/nhẹ nhập tay — những thứ KHÔNG nạp
lại được từ HIS. Vì vậy script chỉ xoá phần dữ liệu mà lần Đồng bộ tới dựng
lại được, cộng với các bảng dẫn xuất từ dữ liệu đó:

  XOÁ (dựng lại được từ HIS):
    disease_cases, case_supply_usage, medical_supplies, inventory
    stg_* , dim_* , fact_* , mart_* , sync_state   (tầng pipeline + watermark)
  XOÁ (dẫn xuất — sẽ tính lại sau khi có dữ liệu mới):
    disease_forecasts, supply_requirements, supply_recommendations,
    alerts, system_logs
  GIỮ:
    users                — tài khoản đăng nhập
    system_config        — trong đó có cấu hình kết nối HIS (mật khẩu mã hoá)
    severity_rates       — tỷ lệ nặng/nhẹ nhập tay
    disease_supply_norms — định mức bệnh–vật tư nhập tay
    conversion_ratios    — hệ số quy đổi
    audit_logs           — vết thao tác, giữ để truy xuất
    environmental_data   — THỜI TIẾT lấy từ Open-Meteo, không phải từ HIS;
                           xoá đi thì dự báo mất biến thời tiết cho tới khi
                           gọi lại API. Muốn xoá luôn: --xoa-thoi-tiet

Xoá xong: bật backend → Quản trị kiểm tra kết nối HIS → Dịch tễ → Đồng bộ HIS.
sync_state đã trống nên lần đồng bộ đó tự kéo TOÀN BỘ lịch sử, và cầu nối
trong SyncService đổ tiếp sang disease_cases / medical_supplies / inventory.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

XOA_DU_LIEU = [
    # nghiệp vụ — dựng lại từ HIS qua cầu nối trong SyncService
    "disease_cases", "case_supply_usage", "inventory", "medical_supplies",
    # dẫn xuất — tính lại sau khi có dữ liệu mới
    "disease_forecasts", "supply_requirements", "supply_recommendations",
    "alerts", "system_logs",
    # tầng pipeline — lần đồng bộ tới dựng lại toàn bộ
    "stg_case_supply", "stg_inventory",
    "dim_icd", "dim_region", "dim_supply",
    "fact_disease_case", "fact_supply_usage", "fact_inventory_snapshot",
    "mart_icd_share_in_block", "mart_inventory",
    "mart_monthly_cases_by_block", "mart_monthly_weather",
    "sync_state",
]
GIU = ["users", "system_config", "severity_rates", "disease_supply_norms",
       "conversion_ratios", "audit_logs", "environmental_data"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/medforecast.db",
                    help="đường dẫn file SQLite của app")
    ap.add_argument("--xoa-thoi-tiet", action="store_true",
                    help="xoá luôn environmental_data (thời tiết Open-Meteo)")
    ap.add_argument("--khong-hoi", action="store_true",
                    help="bỏ bước xác nhận (dùng trong script)")
    args = ap.parse_args()

    duong_dan = Path(args.db)
    if not duong_dan.exists():
        print(f"DỪNG: không thấy {duong_dan}. Chạy từ thư mục backend/.")
        return 1

    xoa = list(XOA_DU_LIEU)
    giu = list(GIU)
    if args.xoa_thoi_tiet:
        xoa.append("environmental_data")
        giu.remove("environmental_data")

    print(f"File DB      : {duong_dan}  ({duong_dan.stat().st_size/1e6:.1f} MB)")
    print(f"Sẽ XOÁ dữ liệu {len(xoa)} bảng, GIỮ {len(giu)} bảng: {', '.join(giu)}")
    if not args.khong_hoi:
        tra_loi = input("Gõ CHÍNH XÁC 'xoa' rồi Enter để tiếp tục: ").strip()
        if tra_loi != "xoa":
            print("Đã huỷ, không đụng gì.")
            return 1

    # --- 1. Sao lưu nguyên file — đường lui duy nhất -------------------------
    ban_sao = duong_dan.with_name(
        f"saoluu_{datetime.now():%Y%m%d_%H%M%S}_{duong_dan.name}")
    shutil.copy2(duong_dan, ban_sao)
    print(f"→ Đã sao lưu: {ban_sao}")

    # --- 2. Xoá ---------------------------------------------------------------
    con = sqlite3.connect(duong_dan)
    try:
        con.execute("PRAGMA foreign_keys = OFF")   # xoá theo lô, khỏi lụy thứ tự FK
        ton_tai = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        with con:
            for bang in xoa:
                if bang not in ton_tai:
                    print(f"  (bỏ qua — không có bảng {bang})")
                    continue
                n = con.execute(f"DELETE FROM '{bang}'").rowcount
                print(f"  đã xoá {n:>7,} dòng  {bang}")
        # AUTOINCREMENT về 0 cho sạch (bảng sqlite_sequence có thể không tồn tại)
        try:
            with con:
                con.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" %
                            ",".join("?" * len(xoa)), xoa)
        except sqlite3.OperationalError:
            pass
        con.execute("VACUUM")
    finally:
        con.close()

    print(f"\nXong. File còn {duong_dan.stat().st_size/1e6:.1f} MB.")

    # --- 3. File mart cũ của lần chạy CLI (nếu có) ---------------------------
    mart_cu = duong_dan.with_name("medforecast_dw.db")
    if mart_cu.exists():
        print(f"\nLƯU Ý: còn file {mart_cu} — mart CŨ của lần chạy pipeline bằng "
              f"dòng lệnh trước đây.\nApp không đọc nó khi PIPELINE_DB_URL trỏ về "
              f"DB chính, nhưng để tránh nhầm thì xoá tay:\n    del {mart_cu}")

    print("\nBước tiếp theo:")
    print("  1. Bật backend:  venv\\Scripts\\activate && uvicorn app.main:app --reload --port 8000")
    print("  2. Quản trị → Kết nối HIS → Kiểm tra kết nối (cấu hình vẫn còn nguyên)")
    print("  3. Dịch tễ → Đồng bộ HIS — watermark đã trống nên tự kéo toàn bộ lịch sử")
    return 0


if __name__ == "__main__":
    sys.exit(main())
