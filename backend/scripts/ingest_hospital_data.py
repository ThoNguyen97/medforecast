"""Ingest bộ dữ liệu bệnh viện thật (data_HM_*.csv) vào DB.

Bộ data mới (32 cột) có thêm:
- LoaiDieuTri: NoiTru / NgoaiTru → phân biệt nhập viện vs khám ngoại trú
- TenPhanCapChamSoc: Cấp I / II / III → phân cấp chăm sóc (dùng suy severity)
- Ward: Xã/Phường → địa lý chi tiết

Phạm vi: chỉ 4 bệnh hô hấp J20/J06/J02/J01 (theo lựa chọn B=1).
Một "ca bệnh" = 1 visit (SoTiepNhan) có 1 trong 4 bệnh là chẩn đoán Primary.

Severity mapping (theo thống nhất phương án A):
    NgoaiTru                 → mild
    NoiTru + Cấp III         → mild
    NoiTru + Cấp II          → moderate
    NoiTru + Cấp I           → severe

File quá lớn (~3.35M dòng) nên dùng streaming theo từng visit (rows đã được
group liên tiếp theo SoTiepNhan trong file).

Cách chạy:
    cd backend
    venv/bin/python scripts/ingest_hospital_data.py \
        --files ../data_HM_2023.csv ../data_HM_2024_1.csv ... \
        --reset          # (tuỳ chọn) xoá disease_cases cũ nguồn hospital_csv trước

Aggregate: gom theo (year-month, icd_code, province, ward, severity) →
- case_count = số visit distinct
- supply usage: tổng TotalQuantityUsed của các DrugCode khớp 15 supply seed,
  chia đều ra mức case (lưu vào case_supply_usage của 1 đại diện case mỗi nhóm).
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

# Cho phép import app.* khi chạy trực tiếp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.disease_case import DiseaseCase  # noqa: E402
from app.models.case_supply_usage import CaseSupplyUsage  # noqa: E402
from app.models.medical_supply import MedicalSupply  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest_hospital")

# 4 bệnh đích
TARGET_ICDS = {"J20", "J06", "J02", "J01"}
ICD_TO_NAME = {
    "J20": "Viêm phế quản cấp",
    "J06": "Nhiễm trùng đường hô hấp trên cấp",
    "J02": "Viêm họng cấp",
    "J01": "Viêm xoang cấp",
}

DATA_SOURCE_TAG = "hospital_csv"

CSV_FIELD_LIMIT = 10_000_000


def _toint(v: Optional[str]) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def map_severity(loai_dieu_tri: str, phan_cap: str) -> str:
    """Map LoaiDieuTri + TenPhanCapChamSoc → mild/moderate/severe."""
    lt = (loai_dieu_tri or "").strip()
    pc = (phan_cap or "").strip()
    if lt == "NgoaiTru":
        return "mild"
    # NoiTru
    if pc == "Cấp I":
        return "severe"
    if pc == "Cấp II":
        return "moderate"
    # Cấp III hoặc không xác định
    return "mild"


class VisitAggregator:
    """Gom dữ liệu theo (month, icd, province, ward, severity).

    Mỗi visit (SoTiepNhan) chỉ tính 1 lần cho bệnh Primary của visit đó.
    """

    def __init__(self, drugcode_to_supply: Dict[str, int]):
        self.drugcode_to_supply = drugcode_to_supply
        # key -> {"cases": int, "supplies": {supply_id: qty}}
        self.agg: Dict[Tuple, Dict] = defaultdict(
            lambda: {"cases": 0, "supplies": defaultdict(int)}
        )
        self.total_visits = 0
        self.target_visits = 0

    def _bucket(self, key: Tuple) -> Dict:
        return self.agg[key]

    def process_visit(self, rows: list) -> None:
        """Xử lý tất cả dòng của 1 visit."""
        if not rows:
            return
        self.total_visits += 1

        # Tìm bệnh Primary thuộc 4 bệnh đích
        primary_icds = {
            r["Final_ICD10_Code"]
            for r in rows
            if r.get("DiagnosisType") == "Primary"
            and r["Final_ICD10_Code"] in TARGET_ICDS
        }
        if not primary_icds:
            return  # visit không có bệnh đích là chẩn đoán chính → bỏ

        self.target_visits += 1

        # Lấy thông tin chung từ dòng đầu
        head = rows[0]
        admit = head.get("AdmissionDate", "")
        try:
            dt = datetime.strptime(admit[:10], "%Y-%m-%d")
        except ValueError:
            return
        month_start = datetime(dt.year, dt.month, 1)
        province = (head.get("District") or "").strip() or "Không xác định"
        ward = (head.get("Ward") or "").strip() or None
        severity = map_severity(
            head.get("LoaiDieuTri", ""), head.get("TenPhanCapChamSoc", "")
        )

        # Mỗi visit có thể có nhiều bệnh Primary đích (hiếm) → tính cho từng bệnh
        for icd in primary_icds:
            key = (month_start, icd, province, ward, severity)
            bucket = self._bucket(key)
            bucket["cases"] += 1

            # Cộng dồn thuốc khớp 15 supply seed
            for r in rows:
                dc = r.get("DrugCode", "")
                sid = self.drugcode_to_supply.get(dc)
                if sid is None:
                    continue
                qty = _toint(r.get("TotalQuantityUsed"))
                if qty > 0:
                    bucket["supplies"][sid] += qty


def load_drugcode_map(db) -> Dict[str, int]:
    """Map DrugCode → supply_id từ 15 medical_supplies đã seed."""
    rows = db.query(MedicalSupply.id, MedicalSupply.drug_code).all()
    return {dc: sid for sid, dc in rows if dc}


def ingest(files: list, reset: bool, max_rows: Optional[int] = None) -> None:
    csv.field_size_limit(CSV_FIELD_LIMIT)
    db = SessionLocal()
    try:
        drugcode_map = load_drugcode_map(db)
        logger.info("Loaded %d drug-code → supply mappings", len(drugcode_map))

        if reset:
            deleted = (
                db.query(DiseaseCase)
                .filter(DiseaseCase.data_source == DATA_SOURCE_TAG)
                .all()
            )
            ids = [d.id for d in deleted]
            if ids:
                db.query(CaseSupplyUsage).filter(
                    CaseSupplyUsage.case_id.in_(ids)
                ).delete(synchronize_session=False)
                db.query(DiseaseCase).filter(
                    DiseaseCase.id.in_(ids)
                ).delete(synchronize_session=False)
                db.commit()
                logger.info("Reset: deleted %d old hospital_csv cases", len(ids))

        aggregator = VisitAggregator(drugcode_map)

        for path in files:
            if not os.path.exists(path):
                logger.warning("File not found, skip: %s", path)
                continue
            logger.info("Processing %s ...", path)
            row_count = 0
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                cur_visit = None
                visit_rows: list = []
                for row in reader:
                    row_count += 1
                    if max_rows and row_count > max_rows:
                        break
                    stn = row.get("SoTiepNhan")
                    if stn != cur_visit:
                        aggregator.process_visit(visit_rows)
                        visit_rows = []
                        cur_visit = stn
                    visit_rows.append(row)
                aggregator.process_visit(visit_rows)  # flush last
            logger.info("  %s: %d rows read", path, row_count)

        logger.info(
            "Aggregation done: total_visits=%d, target_visits=%d, groups=%d",
            aggregator.total_visits,
            aggregator.target_visits,
            len(aggregator.agg),
        )

        # Persist
        created_cases = 0
        created_usages = 0
        for (month_start, icd, province, ward, severity), data in aggregator.agg.items():
            case = DiseaseCase(
                recorded_at=month_start,
                icd_code=icd,
                disease_name=ICD_TO_NAME[icd],
                disease_type="respiratory",
                case_count=data["cases"],
                severity=severity,
                location=province,
                district_ward=ward,
                data_source=DATA_SOURCE_TAG,
            )
            db.add(case)
            db.flush()  # cần case.id
            created_cases += 1

            for sid, qty in data["supplies"].items():
                if qty <= 0:
                    continue
                db.add(CaseSupplyUsage(
                    case_id=case.id,
                    supply_id=sid,
                    quantity=qty,
                ))
                created_usages += 1

            if created_cases % 500 == 0:
                db.commit()
                logger.info("  committed %d cases so far...", created_cases)

        db.commit()
        logger.info(
            "DONE. Created %d disease_cases + %d case_supply_usage rows",
            created_cases, created_usages,
        )

        # Thống kê severity
        from sqlalchemy import func
        sev_stats = (
            db.query(
                DiseaseCase.icd_code,
                DiseaseCase.severity,
                func.sum(DiseaseCase.case_count),
            )
            .filter(DiseaseCase.data_source == DATA_SOURCE_TAG)
            .group_by(DiseaseCase.icd_code, DiseaseCase.severity)
            .all()
        )
        logger.info("Severity distribution (icd, severity, total_cases):")
        for icd, sev, total in sorted(sev_stats):
            logger.info("  %s %-9s %s", icd, sev, int(total))

    except Exception:
        db.rollback()
        logger.exception("Ingest failed")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest hospital CSV data")
    parser.add_argument(
        "--files", nargs="+", required=True, help="Danh sách file CSV cần ingest"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Xoá disease_cases cũ có data_source=hospital_csv trước khi ingest",
    )
    parser.add_argument(
        "--max-rows", type=int, default=None,
        help="Giới hạn số dòng mỗi file (để test nhanh)",
    )
    args = parser.parse_args()
    ingest(args.files, reset=args.reset, max_rows=args.max_rows)


if __name__ == "__main__":
    main()
