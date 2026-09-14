"""Tạo file CSV ĐẦY ĐỦ LỊCH SỬ (2023-2026) + chi tiết thuốc, để import test.

Khác với gen_full_import_csv (chỉ 2026), file này:
- Lấy SỐ CA THẬT từ data_HM_*.csv cho toàn bộ 2023-2026 (theo tháng × bệnh × tỉnh)
- Gắn chi tiết thuốc/vật tư theo định mức trung bình mỗi ca (để có case_supply_usage)
- Đủ lịch sử dài → model forecast học được xu hướng + mùa vụ

Format khớp endpoint /disease-cases/import-csv:
    month, disease_name, region, district_ward, cases,
    supply_name, supply_quantity, supply_unit, supply_category, note

Cách chạy:
    cd backend
    venv/bin/python scripts/gen_full_history_csv.py \
        --files ../data_HM_2023.csv ../data_HM_2024_1.csv ... \
        --out ../test_data/disease_cases_history_full.csv \
        [--region "Thành phố Hồ Chí Minh"]   # lọc 1 tỉnh cho gọn (khuyên dùng)
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

TARGET_ICDS = {"J20", "J06", "J02", "J01"}
ICD_TO_NAME = {
    "J20": "Viêm phế quản cấp",
    "J06": "Nhiễm trùng đường hô hấp trên cấp",
    "J02": "Viêm họng cấp",
    "J01": "Viêm xoang cấp",
}
CSV_FIELD_LIMIT = 10_000_000

# Thuốc theo bệnh: (supply_code, supply_name, unit, category, qty_per_case_avg)
SUPPLIES_BY_ICD = {
    "J20": [
        ("VT001", "Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("VT003", "N-acetylcysteine", "Gói", "Thuốc long đờm", 6),
        ("VT009", "Salbutamol + ipratropium", "Lọ", "Thuốc khí dung/giãn phế quản", 2),
        ("VT010", "Budesonid", "Ống", "Corticoid khí dung", 2),
        ("VT005", "Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
        ("VT002", "Natri clorid", "Chai", "Dung dịch/dịch truyền", 1),
    ],
    "J06": [
        ("VT001", "Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("VT004", "Fexofenadin", "Viên", "Kháng histamin", 6),
        ("VT003", "N-acetylcysteine", "Gói", "Thuốc long đờm", 4),
        ("VT012", "Vitamin C", "Viên", "Thuốc hỗ trợ", 7),
        ("VT005", "Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
    ],
    "J02": [
        ("VT001", "Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("VT004", "Fexofenadin", "Viên", "Kháng histamin", 5),
        ("VT012", "Vitamin C", "Viên", "Thuốc hỗ trợ", 7),
        ("VT005", "Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
    ],
    "J01": [
        ("VT001", "Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("VT004", "Fexofenadin", "Viên", "Kháng histamin", 6),
        ("VT003", "N-acetylcysteine", "Gói", "Thuốc long đờm", 4),
        ("VT005", "Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 5),
    ],
}


def build(files: list, out_path: str, region_filter: Optional[str],
          with_ward: bool = False) -> None:
    csv.field_size_limit(CSV_FIELD_LIMIT)

    # key = (year, month, icd, province, ward) → set of SoTiepNhan (đếm visit distinct)
    visits: Dict[Tuple, set] = defaultdict(set)

    def process_visit(rows: list) -> None:
        if not rows:
            return
        primary = {
            r["Final_ICD10_Code"]
            for r in rows
            if r.get("DiagnosisType") == "Primary"
            and r["Final_ICD10_Code"] in TARGET_ICDS
        }
        if not primary:
            return
        head = rows[0]
        admit = head.get("AdmissionDate", "")
        try:
            dt = datetime.strptime(admit[:10], "%Y-%m-%d")
        except ValueError:
            return
        province = (head.get("District") or "").strip() or "Không xác định"
        if region_filter and province != region_filter:
            return
        ward = (head.get("Ward") or "").strip() if with_ward else ""
        stn = head.get("SoTiepNhan")
        for icd in primary:
            visits[(dt.year, dt.month, icd, province, ward)].add(stn)

    for path in files:
        if not os.path.exists(path):
            print(f"[skip] {path}")
            continue
        print(f"[read] {path}")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cur = None
            buf: list = []
            for row in reader:
                stn = row.get("SoTiepNhan")
                if stn != cur:
                    process_visit(buf)
                    buf = []
                    cur = stn
                buf.append(row)
            process_visit(buf)

    # Build output rows
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fieldnames = ["month", "disease_name", "region", "district_ward", "cases",
                  "supply_code", "supply_name", "supply_quantity", "supply_unit",
                  "supply_category", "note"]

    out_rows = []
    for (year, month, icd, province, ward), stns in sorted(visits.items()):
        cases = len(stns)
        if cases == 0:
            continue
        month_str = f"{month:02d}/{year}"
        for (code, name, unit, category, qpc) in SUPPLIES_BY_ICD[icd]:
            out_rows.append({
                "month": month_str,
                "disease_name": icd,
                "region": province,
                "district_ward": ward,
                "cases": cases,
                "supply_code": code,
                "supply_name": name,
                "supply_quantity": cases * qpc,
                "supply_unit": unit,
                "supply_category": category,
                "note": "",
            })

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    n_cases = len({
        (r["month"], r["disease_name"], r["region"], r["district_ward"])
        for r in out_rows
    })
    print(f"[done] {len(out_rows)} rows, {n_cases} ca bệnh (tháng×bệnh×tỉnh×phường)")
    print(f"[out]  {os.path.abspath(out_path)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--region", default=None, help="Lọc 1 tỉnh/thành (vd 'Thành phố Hồ Chí Minh')")
    p.add_argument("--with-ward", action="store_true", help="Điền cột district_ward (Phường) từ data thật")
    args = p.parse_args()
    build(args.files, args.out, args.region, with_ward=args.with_ward)


if __name__ == "__main__":
    main()
