"""Export disease_cases + case_supply_usage hiện có trong DB ra file CSV import.

Dùng khi đã có data trong DB (vd đã import trước đó) và muốn tạo lại file CSV
đầy đủ cột (gồm supply_code, supply_name...) để import lại / chia sẻ.

Output format khớp endpoint /disease-cases/import-csv:
    month, disease_name, region, district_ward, cases,
    supply_code, supply_name, supply_quantity, supply_unit, supply_category, note

Cách chạy:
    cd backend
    venv/bin/python scripts/export_cases_to_csv.py --out ../test_data/disease_cases_history_ward.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.disease_case import DiseaseCase  # noqa: E402
from app.models.case_supply_usage import CaseSupplyUsage  # noqa: E402
from app.models.medical_supply import MedicalSupply  # noqa: E402

ICD_TO_NAME = {
    "J20": "Viêm phế quản cấp",
    "J06": "Nhiễm trùng đường hô hấp trên cấp",
    "J02": "Viêm họng cấp",
    "J01": "Viêm xoang cấp",
}


def export(out_path: str, region_filter: str | None) -> None:
    db = SessionLocal()
    try:
        q = db.query(DiseaseCase)
        if region_filter:
            q = q.filter(DiseaseCase.location == region_filter)
        cases = q.order_by(
            DiseaseCase.recorded_at, DiseaseCase.icd_code, DiseaseCase.district_ward
        ).all()

        # Preload supply map
        supplies = {s.id: s for s in db.query(MedicalSupply).all()}

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        fieldnames = ["month", "disease_name", "region", "district_ward", "cases",
                      "supply_code", "supply_name", "supply_quantity",
                      "supply_unit", "supply_category", "note"]

        rows_written = 0
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for c in cases:
                month_str = f"{c.recorded_at.month:02d}/{c.recorded_at.year}"
                disease_label = ICD_TO_NAME.get(c.icd_code, c.disease_name or c.icd_code)
                usages = (
                    db.query(CaseSupplyUsage)
                    .filter(CaseSupplyUsage.case_id == c.id)
                    .all()
                )
                if not usages:
                    # Ca không có chi tiết thuốc → 1 dòng trống supply
                    w.writerow({
                        "month": month_str,
                        "disease_name": c.icd_code,
                        "region": c.location,
                        "district_ward": c.district_ward or "",
                        "cases": c.case_count,
                        "supply_code": "", "supply_name": "",
                        "supply_quantity": "", "supply_unit": "",
                        "supply_category": "", "note": "",
                    })
                    rows_written += 1
                    continue
                for u in usages:
                    s = supplies.get(u.supply_id)
                    w.writerow({
                        "month": month_str,
                        "disease_name": c.icd_code,
                        "region": c.location,
                        "district_ward": c.district_ward or "",
                        "cases": c.case_count,
                        "supply_code": s.supply_code if s else "",
                        "supply_name": s.ten_hoat_chat if s else "",
                        "supply_quantity": u.quantity,
                        "supply_unit": s.unit if s else "",
                        "supply_category": s.group_name if s else "",
                        "note": "",
                    })
                    rows_written += 1

        print(f"[done] {len(cases)} ca, {rows_written} dòng → {os.path.abspath(out_path)}")
        _ = disease_label  # silence
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--region", default=None)
    args = p.parse_args()
    export(args.out, args.region)


if __name__ == "__main__":
    main()
