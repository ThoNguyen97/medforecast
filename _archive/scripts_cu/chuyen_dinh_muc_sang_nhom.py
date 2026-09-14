#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuyển tỷ lệ nặng/nhẹ + định mức bệnh–vật tư từ mức MÃ sang mức NHÓM ICD.

    cd backend
    venv\\Scripts\\python scripts\\chuyen_dinh_muc_sang_nhom.py
    (TẮT backend trước — SQLite khoá file)

VÌ SAO PHẢI CHUYỂN
Chuỗi cảnh báo/đề xuất nhập chạy theo danh sách trong severity_rates. Danh sách
đó đang là 4 MÃ CŨ (J01, J02, J06, J20) — nên J18 (bệnh lớn nhất, ~30% số ca)
và toàn nhóm J09-J18 KHÔNG sinh nhu cầu vật tư nào. Hệ thống giờ dự báo theo
NHÓM, định mức cũng phải theo nhóm thì chuỗi mới khớp đầu-cuối.

CÁCH SINH SỐ — không bịa số y khoa:
  • Tỷ lệ nặng/nhẹ nhóm  = trung bình CÓ TRỌNG SỐ của các mã cũ trong nhóm,
    trọng số = số ca thực tế 2019–2026 của từng mã. Nhóm không có mã cũ nào
    (J09-J18) → ghi bản NHÁP có ghi chú rõ, chờ Khoa Dược hiệu chỉnh trên
    Quản trị → "Tỷ lệ Nhẹ/TB/Nặng".
  • Định mức nhóm         = trung bình có trọng số định mức các mã cũ (cùng
    trọng số ca). J09-J18 không có định mức cũ → sinh NHÁP TỪ TIÊU HAO THỰC TẾ:
    lượng dùng ÷ số ca đo từ chính dữ liệu HIS (top vật tư dùng nhiều nhất),
    gán như nhau cho cả 3 mức độ — vì tỷ lệ 3 mức cộng bằng 100% nên tổng nhu
    cầu = số ca × định mức, không phụ thuộc cách chia. Ghi chú "NHÁP" ngay
    trong tên để admin biết phải rà.
  • XOÁ 4 dòng severity mức mã sau khi tạo mức nhóm — để nguyên thì vòng tính
    tháng chạy CẢ mã lẫn nhóm và nhu cầu bị ĐÚP. Định mức mức mã giữ lại
    (không được duyệt tới nữa, nhưng còn để tham khảo/khôi phục).

Script tự SAO LƯU file DB trước khi sửa. Chạy lại lần nữa: tự bỏ qua nhóm đã có.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

NHOM = {
    "J00-J06": "Nhiễm khuẩn cấp đường hô hấp trên",
    "J09-J18": "Cúm và viêm phổi",
    "J20-J22": "Nhiễm khuẩn cấp đường hô hấp dưới khác",
}
# Bản nháp cho nhóm không có dữ liệu phân độ — PHẢI được Khoa Dược hiệu chỉnh
NHAP_TY_LE = (30.0, 45.0, 25.0)     # nhẹ / trung bình / nặng
SO_VAT_TU_NHAP = 15                  # top N vật tư khi sinh định mức từ tiêu hao
NGUOI_TAO = "script_chuyen_nhom"


def nhom_cua(ma: str) -> str | None:
    try:
        n = int(ma.replace("J", "").replace("j", "")[:2])
    except ValueError:
        return None
    if 0 <= n <= 6:
        return "J00-J06"
    if 9 <= n <= 18:
        return "J09-J18"
    if 20 <= n <= 22:
        return "J20-J22"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/medforecast.db")
    ap.add_argument("--khong-hoi", action="store_true")
    args = ap.parse_args()
    duong_dan = Path(args.db)
    if not duong_dan.exists():
        print(f"DỪNG: không thấy {duong_dan}. Chạy từ thư mục backend/.")
        return 1

    if not args.khong_hoi:
        print("Chuyển tỷ lệ nặng/nhẹ + định mức sang mức NHÓM (xoá 4 dòng "
              "severity mức mã).")
        if input("Gõ 'chuyen' để tiếp tục: ").strip() != "chuyen":
            print("Đã huỷ.")
            return 1

    ban_sao = duong_dan.with_name(
        f"saoluu_{datetime.now():%Y%m%d_%H%M%S}_{duong_dan.name}")
    shutil.copy2(duong_dan, ban_sao)
    print(f"→ Đã sao lưu: {ban_sao}")

    con = sqlite3.connect(duong_dan)
    con.row_factory = sqlite3.Row
    try:
        # ── Trọng số = số ca thực tế từng mã ─────────────────────────────────
        trong_so = {r["icd_code"]: r["n"] for r in con.execute(
            "SELECT icd_code, SUM(case_count) n FROM disease_cases GROUP BY icd_code")}

        da_co = {r["icd_code"] for r in con.execute("SELECT icd_code FROM severity_rates")}
        sev_cu = {r["icd_code"]: r for r in con.execute("SELECT * FROM severity_rates")}

        # ── 1. severity_rates mức nhóm ───────────────────────────────────────
        for khoa, ten in NHOM.items():
            if khoa in da_co:
                print(f"  (bỏ qua — severity nhóm {khoa} đã tồn tại)")
                continue
            thanh_vien = [(m, r) for m, r in sev_cu.items() if nhom_cua(m) == khoa]
            if thanh_vien:
                w = [max(1, trong_so.get(m, 1)) for m, _ in thanh_vien]
                tw = sum(w)
                mild = sum(float(r["mild_rate"]) * wi for (_, r), wi in zip(thanh_vien, w)) / tw
                mod = sum(float(r["moderate_rate"]) * wi for (_, r), wi in zip(thanh_vien, w)) / tw
                sev = 100.0 - mild - mod                     # ép tổng đúng 100
                note = (f"Gộp có trọng số từ {', '.join(m for m, _ in thanh_vien)} "
                        f"theo số ca thực tế 2019–2026.")
            else:
                mild, mod, sev = NHAP_TY_LE
                note = ("NHÁP — nhóm chưa có dữ liệu phân độ; Khoa Dược hiệu chỉnh "
                        "tại Quản trị → Tỷ lệ Nhẹ/TB/Nặng trước khi dùng chính thức.")
            con.execute(
                "INSERT INTO severity_rates (icd_code, disease_name, mild_rate, "
                "moderate_rate, severe_rate, note, updated_by, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (khoa, ten, round(mild, 2), round(mod, 2), round(sev, 2), note, NGUOI_TAO))
            print(f"  + severity {khoa}: nhẹ {mild:.1f} / TB {mod:.1f} / nặng {sev:.1f}"
                  f"  ({'gộp từ mã cũ' if thanh_vien else 'NHÁP'})")

        # ── 2. disease_supply_norms mức nhóm ────────────────────────────────
        norm_cu = list(con.execute("SELECT * FROM disease_supply_norms"))
        nhom_da_co_norm = {r["icd_code"] for r in norm_cu if r["icd_code"] in NHOM}

        for khoa, ten in NHOM.items():
            if khoa in nhom_da_co_norm:
                print(f"  (bỏ qua — định mức nhóm {khoa} đã tồn tại)")
                continue
            thanh_vien_norms = [r for r in norm_cu if nhom_cua(r["icd_code"]) == khoa]
            so_dong = 0
            if thanh_vien_norms:
                # (supply_id, severity) → Σ(trọng số mã × định mức mã) / Σ trọng số nhóm
                ma_trong_nhom = sorted({r["icd_code"] for r in thanh_vien_norms})
                tw = sum(max(1, trong_so.get(m, 1)) for m in ma_trong_nhom)
                gop: dict = {}
                for r in thanh_vien_norms:
                    k = (r["supply_id"], r["severity"])
                    gop[k] = gop.get(k, 0.0) + \
                        max(1, trong_so.get(r["icd_code"], 1)) * float(r["quantity_per_case"])
                for (sid, muc), tong in gop.items():
                    qty = round(tong / tw)
                    if qty <= 0:
                        continue
                    con.execute(
                        "INSERT INTO disease_supply_norms (icd_code, disease_name, "
                        "severity, supply_id, quantity_per_case, updated_by, "
                        "created_at, updated_at) "
                        "VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
                        (khoa, ten, muc, sid, qty, NGUOI_TAO))
                    so_dong += 1
                print(f"  + định mức {khoa}: {so_dong} dòng (gộp trọng số từ "
                      f"{', '.join(ma_trong_nhom)})")
            else:
                # NHÁP từ tiêu hao thực tế: lượng dùng ÷ số ca, top N vật tư
                tong_ca = con.execute(
                    "SELECT COALESCE(SUM(case_count),0) FROM disease_cases "
                    "WHERE disease_group = ?", (khoa,)).fetchone()[0]
                if not tong_ca:
                    print(f"  ! {khoa}: không có ca nào — bỏ qua")
                    continue
                rows = list(con.execute(
                    """SELECT ms.id AS sid, ms.ten_hoat_chat, SUM(f.quantity) AS tong
                       FROM fact_supply_usage f
                       JOIN medical_supplies ms ON ms.supply_code = f.supply_code
                       WHERE f.block_code = ?
                       GROUP BY ms.id ORDER BY tong DESC LIMIT ?""",
                    (khoa, SO_VAT_TU_NHAP)))
                for r in rows:
                    qty = max(1, round(float(r["tong"]) / float(tong_ca)))
                    for muc in ("mild", "moderate", "severe"):
                        con.execute(
                            "INSERT INTO disease_supply_norms (icd_code, disease_name, "
                            "severity, supply_id, quantity_per_case, updated_by, "
                            "created_at, updated_at) "
                            "VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
                            (khoa, ten + " [ĐỊNH MỨC NHÁP TỪ TIÊU HAO]", muc,
                             r["sid"], qty, NGUOI_TAO))
                        so_dong += 1
                print(f"  + định mức {khoa}: {so_dong} dòng NHÁP từ tiêu hao thực tế "
                      f"({len(rows)} vật tư × 3 mức, = lượng dùng ÷ {tong_ca:,} ca)")

        # ── 3. Xoá severity mức MÃ (chống đúp nhu cầu) ──────────────────────
        ma_cu = [m for m in sev_cu if m not in NHOM and nhom_cua(m)]
        if ma_cu:
            con.executemany("DELETE FROM severity_rates WHERE icd_code = ?",
                            [(m,) for m in ma_cu])
            print(f"  − đã xoá severity mức mã: {', '.join(sorted(ma_cu))} "
                  "(tránh tính nhu cầu hai lần; bản sao lưu còn nguyên)")

        con.commit()
        print("\nXong. Kiểm tra:")
        for r in con.execute(
                "SELECT icd_code, mild_rate, moderate_rate, severe_rate "
                "FROM severity_rates ORDER BY icd_code"):
            n = con.execute("SELECT COUNT(*) FROM disease_supply_norms WHERE icd_code=?",
                            (r["icd_code"],)).fetchone()[0]
            print(f"  {r['icd_code']:9} {float(r['mild_rate']):5.1f}/"
                  f"{float(r['moderate_rate']):5.1f}/{float(r['severe_rate']):5.1f}"
                  f"  — {n} dòng định mức")
        print("\nBước tiếp: bật backend → trang Cảnh báo/Đề xuất nhập kho phải ra "
              "nhu cầu cho CẢ BA nhóm, kể cả J09-J18.")
        print("Khoa Dược rà lại các dòng có chữ NHÁP tại Quản trị trước khi dùng "
              "chính thức.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
