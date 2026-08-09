"""Tạo file CSV gọn (aggregate) từ bộ data bệnh viện thật để user tự import qua UI.

Output format khớp template của endpoint /disease-cases/import-csv:
    month, disease_name, region, district_ward, cases

- Chỉ 4 bệnh đích J20/J06/J02/J01 (Primary diagnosis).
- 1 ca = 1 visit (SoTiepNhan) có bệnh đích là chẩn đoán Primary.
- Aggregate theo (month, icd, province, ward) → đếm visit distinct.
- month dạng MM/YYYY; disease_name dùng mã ICD (import-csv map được).

Cách chạy:
    cd backend
    venv/bin/python scripts/build_import_csv.py \
        --files ../data_HM_2023.csv ../data_HM_2024_1.csv ... \
        --out ../test_data/disease_cases_import.csv \
        [--no-ward]      # bỏ cột district_ward cho file gọn hơn
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

TARGET_ICDS = {"J20", "J06", "J02", "J01"}
CSV_FIELD_LIMIT = 10_000_000


def build(files: list, out_path: str, with_ward: bool, max_rows: Optional[int]) -> None:
    csv.field_size_limit(CSV_FIELD_LIMIT)

    # key = (month_str, icd, province, ward) → số visit
    agg: Dict[Tuple, int] = defaultdict(int)
    total_visits = 0
    target_visits = 0

    def process_visit(rows: list) -> None:
        nonlocal total_visits, target_visits
        if not rows:
            return
        total_visits += 1
        primary = {
            r["Final_ICD10_Code"]
            for r in rows
            if r.get("DiagnosisType") == "Primary"
            and r["Final_ICD10_Code"] in TARGET_ICDS
        }
        if not primary:
            return
        target_visits += 1
        head = rows[0]
        admit = head.get("AdmissionDate", "")
        try:
            dt = datetime.strptime(admit[:10], "%Y-%m-%d")
        except ValueError:
            return
        month_str = f"{dt.month:02d}/{dt.year}"
        province = (head.get("District") or "").strip() or "Không xác định"
        ward = (head.get("Ward") or "").strip() if with_ward else ""
        for icd in primary:
            agg[(month_str, icd, province, ward)] += 1

    for path in files:
        if not os.path.exists(path):
            print(f"[skip] not found: {path}")
            continue
        print(f"[read] {path}")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cur_visit = None
            visit_rows: list = []
            for n, row in enumerate(reader, start=1):
                if max_rows and n > max_rows:
                    break
                stn = row.get("SoTiepNhan")
                if stn != cur_visit:
                    process_visit(visit_rows)
                    visit_rows = []
                    cur_visit = stn
                visit_rows.append(row)
            process_visit(visit_rows)

    # Ghi file output, sort theo (year, month, province, icd)
    def sort_key(item):
        (month_str, icd, province, ward), _ = item
        mm, yyyy = month_str.split("/")
        return (int(yyyy), int(mm), province, ward, icd)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        if with_ward:
            fieldnames = ["month", "disease_name", "region", "district_ward", "cases"]
        else:
            fieldnames = ["month", "disease_name", "region", "cases"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        rows_written = 0
        for (month_str, icd, province, ward), cases in sorted(agg.items(), key=sort_key):
            rec = {
                "month": month_str,
                "disease_name": icd,  # import-csv map ICD → tên chuẩn
                "region": province,
                "cases": cases,
            }
            if with_ward:
                rec["district_ward"] = ward
            writer.writerow(rec)
            rows_written += 1

    print(
        f"[done] total_visits={total_visits} target_visits={target_visits} "
        f"groups={len(agg)} rows_written={rows_written}"
    )
    print(f"[out]  {out_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--no-ward", action="store_true", help="Bỏ cột district_ward")
    p.add_argument("--max-rows", type=int, default=None)
    args = p.parse_args()
    build(args.files, args.out, with_ward=not args.no_ward, max_rows=args.max_rows)


if __name__ == "__main__":
    main()
