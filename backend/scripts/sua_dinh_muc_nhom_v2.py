#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sửa dữ liệu định mức nhóm — vá 2 di chứng của lần "xoá DB nạp lại từ HIS".

    cd backend
    venv\\Scripts\\python scripts\\sua_dinh_muc_nhom_v2.py
    (TẮT backend trước — SQLite khoá file)

CHUYỆN GÌ ĐÃ XẢY RA
Khi xoá DB nạp lại, bảng medical_supplies bị TẠO MỚI → id đánh số lại từ 1.
Nhưng 60 dòng định mức cũ (J01/J02/J06/J20) vẫn trỏ supply_id 1–60 THEO BẢNG
CŨ. Script chuyển-sang-nhóm chạy SAU đó đã gộp trọng số từ chính 60 dòng này
→ định mức nhóm J00-J06 và J20-J22 trỏ nhầm sang 60 vật tư ĐẦU BẢNG theo thứ
tự chữ cái ("(DLT", "[GNT"…) — vô nghĩa y khoa. Riêng J09-J18 sinh từ tiêu hao
thực tế (fact_supply_usage nối theo supply_code, không theo id) nên VẪN ĐÚNG.
Cộng thêm: 4.680 vật tư mang drug_code='nan' (chuỗi chữ, di chứng pandas NaN)
làm trang Kế hoạch gộp nghìn thuốc làm một dòng.

SCRIPT NÀY LÀM 3 VIỆC — có sao lưu, chạy lại an toàn:
  1. Rửa drug_code/ten_hoat_chat/unit/group_name = 'nan'/'none'… → chuỗi rỗng
     (riêng ten_hoat_chat rỗng thì thay bằng supply_code để còn đọc được).
  2. XOÁ định mức hỏng: mức nhóm J00-J06, J20-J22 (gộp từ id nhầm) + toàn bộ
     mức mã cũ (J01, J02, J06, J20 — cùng gốc id nhầm, giữ chỉ gây hiểu lầm).
  3. SINH LẠI định mức J00-J06, J20-J22 từ TIÊU HAO THỰC TẾ — đúng công thức
     đã dùng cho J09-J18: top 15 vật tư dùng nhiều nhất của nhóm, định mức =
     tổng lượng dùng ÷ tổng số ca của nhóm, gán như nhau cho 3 mức độ (tỷ lệ
     3 mức cộng 100% nên tổng nhu cầu không phụ thuộc cách chia). Tên bệnh
     ghi rõ "[ĐỊNH MỨC NHÁP TỪ TIÊU HAO]" để Khoa Dược biết phải rà.

severity_rates KHÔNG đụng tới — 3 dòng mức nhóm đã đúng từ script trước.
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
SINH_LAI = ("J00-J06", "J20-J22")          # J09-J18 đã đúng, không đụng
XOA_MA_CU = ("J01", "J02", "J06", "J20")   # định mức mức mã — id nhầm sau nạp lại
SO_VAT_TU = 15
NGUOI_TAO = "script_sua_dinh_muc_v2"
GIA_TRI_RONG = ("", "nan", "none", "nat", "null")


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
        print("Sẽ: rửa drug_code 'nan', xoá định mức hỏng (J00-J06, J20-J22, "
              "J01/J02/J06/J20), sinh lại từ tiêu hao thực tế.")
        if input("Gõ 'sua' để tiếp tục: ").strip() != "sua":
            print("Đã huỷ.")
            return 1

    ban_sao = duong_dan.with_name(
        f"saoluu_{datetime.now():%Y%m%d_%H%M%S}_{duong_dan.name}")
    shutil.copy2(duong_dan, ban_sao)
    print(f"→ Đã sao lưu: {ban_sao}")

    con = sqlite3.connect(duong_dan)
    con.row_factory = sqlite3.Row
    try:
        # ── 1. Rửa chuỗi 'nan' trong medical_supplies ───────────────────────
        ds_rong = ",".join("?" * len(GIA_TRI_RONG))
        n1 = con.execute(
            f"UPDATE medical_supplies SET drug_code='' "
            f"WHERE lower(trim(COALESCE(drug_code,''))) IN ({ds_rong}) "
            f"AND COALESCE(drug_code,'') != ''", GIA_TRI_RONG).rowcount
        n2 = con.execute(
            f"UPDATE medical_supplies SET ten_hoat_chat=supply_code "
            f"WHERE lower(trim(COALESCE(ten_hoat_chat,''))) IN ({ds_rong})",
            GIA_TRI_RONG).rowcount
        n3 = 0
        for cot in ("unit", "group_name"):
            n3 += con.execute(
                f"UPDATE medical_supplies SET {cot}='' "
                f"WHERE lower(trim(COALESCE({cot},''))) IN ({ds_rong}) "
                f"AND COALESCE({cot},'') != ''", GIA_TRI_RONG).rowcount
        print(f"1. Rửa 'nan': drug_code {n1} dòng, ten_hoat_chat {n2}, "
              f"unit/group_name {n3}")

        # ── 2. Xoá định mức hỏng ────────────────────────────────────────────
        hong = list(SINH_LAI) + list(XOA_MA_CU)
        ds = ",".join("?" * len(hong))
        nxoa = con.execute(
            f"DELETE FROM disease_supply_norms WHERE icd_code IN ({ds})",
            hong).rowcount
        print(f"2. Xoá {nxoa} dòng định mức hỏng ({', '.join(hong)}) — "
              "bản sao lưu còn nguyên")

        # ── 3. Sinh lại từ tiêu hao thực tế (công thức của J09-J18) ─────────
        for khoa in SINH_LAI:
            ten = NHOM[khoa]
            tong_ca = con.execute(
                "SELECT COALESCE(SUM(case_count),0) FROM disease_cases "
                "WHERE disease_group = ?", (khoa,)).fetchone()[0]
            if not tong_ca:
                print(f"3. ! {khoa}: không có ca nào trong disease_cases — bỏ qua")
                continue
            rows = list(con.execute(
                """SELECT ms.id AS sid, ms.ten_hoat_chat, SUM(f.quantity) AS tong
                   FROM fact_supply_usage f
                   JOIN medical_supplies ms ON ms.supply_code = f.supply_code
                   WHERE f.block_code = ?
                   GROUP BY ms.id ORDER BY tong DESC LIMIT ?""",
                (khoa, SO_VAT_TU)))
            so_dong = 0
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
            print(f"3. + {khoa}: {so_dong} dòng ({len(rows)} vật tư × 3 mức, "
                  f"= lượng dùng ÷ {tong_ca:,} ca)")

        con.commit()

        print("\nKiểm tra sau sửa:")
        for r in con.execute(
                "SELECT n.icd_code, COUNT(*) sl FROM disease_supply_norms n "
                "GROUP BY n.icd_code ORDER BY n.icd_code"):
            vd = con.execute(
                """SELECT ms.ten_hoat_chat FROM disease_supply_norms n
                   JOIN medical_supplies ms ON ms.id = n.supply_id
                   WHERE n.icd_code = ? ORDER BY n.quantity_per_case DESC LIMIT 3""",
                (r["icd_code"],)).fetchall()
            vi_du = ", ".join((v[0] or "").strip() for v in vd)
            print(f"  {r['icd_code']:9} {r['sl']:3} dòng — vd: {vi_du}")
        con_nan = con.execute(
            "SELECT COUNT(*) FROM medical_supplies "
            "WHERE lower(trim(COALESCE(drug_code,''))) IN ('nan','none','nat','null')"
        ).fetchone()[0]
        print(f"  drug_code còn 'nan': {con_nan} (phải = 0)")
        print("\nBước tiếp: bật backend → Kế hoạch nhập kho phải ra đề xuất "
              "cho CẢ BA nhóm với tên thuốc có nghĩa (Amoxicilin, Ambroxol…).")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
