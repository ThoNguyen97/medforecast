"""Severity Inference Service.

Áp dụng logic mục 5.2: Suy luận tỷ lệ Nhẹ/TB/Nặng từ dữ liệu lịch sử.

Quy tắc phân loại:
- Nhẹ: LengthOfStay = 0; SubICD_Count thấp; chủ yếu thuốc uống thông thường;
       ít hoặc không có vật tư can thiệp.
- Trung bình: LengthOfStay 1-3 ngày; có khí dung, kháng sinh, corticoid hoặc
              một số vật tư y tế.
- Nặng: LengthOfStay >= 4 ngày; SubICD_Count cao; có kháng sinh tiêm, dịch truyền,
        bơm tiêm, kim tiêm, dây truyền dịch hoặc nhiều y lệnh vật tư.

Output:
- Cập nhật `severity` của từng DiseaseCase
- Cập nhật `severity_rate` của từng bệnh dựa trên tỷ lệ thực tế
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case_supply_usage import CaseSupplyUsage
from app.models.disease_case import DiseaseCase
from app.models.medical_supply import MedicalSupply
from app.models.severity_rate import SeverityRate

logger = logging.getLogger(__name__)


# Ngưỡng phân loại
SUB_ICD_THRESHOLD = 2  # SubICD_Count < 2 → "thấp", >= 4 → "cao"

# Các nhóm thuốc/vật tư đặc trưng cho từng mức độ
INTERVENTION_GROUPS = {
    "moderate": [
        "Thuốc khí dung/giãn phế quản",
        "Corticoid khí dung",
        "Kháng sinh uống",
        "Kháng viêm corticosteroid",
    ],
    "severe": [
        "Kháng sinh tiêm",
        "Dung dịch/dịch truyền",
        "Vật tư y tế",  # bơm tiêm, kim tiêm, dây truyền dịch
    ],
}


class SeverityInferenceService:
    """Suy luận mức độ Nhẹ/TB/Nặng từ dữ liệu lịch sử."""

    def __init__(self, db: Session):
        self.db = db
        self._supply_group_cache: Optional[Dict[int, str]] = None

    def _load_supply_groups(self) -> Dict[int, str]:
        """Cache map supply_id → group_name."""
        if self._supply_group_cache is None:
            rows = self.db.query(MedicalSupply.id, MedicalSupply.group_name).all()
            self._supply_group_cache = {sid: gn or "" for sid, gn in rows}
        return self._supply_group_cache

    def _get_case_supplies(self, case_id: int) -> List[str]:
        """Lấy danh sách group_name của các thuốc/vật tư đã dùng cho ca này."""
        rows = (
            self.db.query(CaseSupplyUsage.supply_id, CaseSupplyUsage.quantity)
            .filter(CaseSupplyUsage.case_id == case_id)
            .filter(CaseSupplyUsage.quantity > 0)
            .all()
        )
        groups = self._load_supply_groups()
        return [groups[sid] for sid, _ in rows if sid in groups]

    def classify_case(self, case: DiseaseCase) -> str:
        """Phân loại 1 ca bệnh thành mild/moderate/severe theo mục 5.2.

        Returns:
            'mild' | 'moderate' | 'severe'
        """
        los = case.length_of_stay or 0
        sub_count = case.sub_icd_count or 0
        case_supplies = self._get_case_supplies(case.id)
        case_groups = set(case_supplies)

        has_severe_intervention = any(
            g in case_groups for g in INTERVENTION_GROUPS["severe"]
        )
        has_moderate_intervention = any(
            g in case_groups for g in INTERVENTION_GROUPS["moderate"]
        )

        # Quy tắc 5.2

        # Nặng: LOS >= 4 OR có can thiệp nặng OR sub_icd cao
        if los >= 4:
            return "severe"
        if has_severe_intervention:
            return "severe"
        if sub_count >= SUB_ICD_THRESHOLD * 2:  # 4+
            return "severe"

        # Trung bình: LOS 1-3 OR có can thiệp TB OR sub_icd thấp
        if 1 <= los <= 3:
            return "moderate"
        if has_moderate_intervention:
            return "moderate"
        if sub_count >= SUB_ICD_THRESHOLD:
            return "moderate"

        # Còn lại: Nhẹ
        return "mild"

    def classify_all_cases(
        self,
        icd_code: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, int]:
        """Phân loại lại tất cả ca bệnh.

        Args:
            icd_code: Nếu chỉ định, chỉ phân loại ca của bệnh này
            force: True = ghi đè severity cũ; False = chỉ điền nếu chưa có

        Returns:
            Số ca được phân loại theo mức độ
        """
        q = self.db.query(DiseaseCase)
        if icd_code:
            q = q.filter(DiseaseCase.icd_code == icd_code)
        if not force:
            q = q.filter(DiseaseCase.severity.is_(None))

        cases = q.all()

        counts = {"mild": 0, "moderate": 0, "severe": 0, "total": 0}
        for case in cases:
            new_severity = self.classify_case(case)
            case.severity = new_severity
            counts[new_severity] += 1
            counts["total"] += 1

        self.db.commit()
        logger.info(
            "Classified %d cases (icd=%s): mild=%d moderate=%d severe=%d",
            counts["total"], icd_code or "all",
            counts["mild"], counts["moderate"], counts["severe"],
        )
        return counts

    def compute_rates_from_history(
        self,
        icd_code: str,
    ) -> Optional[Dict[str, float]]:
        """Tính tỷ lệ Nhẹ/TB/Nặng từ dữ liệu lịch sử của 1 bệnh.

        Returns:
            Dict {mild_rate, moderate_rate, severe_rate, total_cases}
            hoặc None nếu chưa có dữ liệu phân loại.
        """
        rows = (
            self.db.query(
                DiseaseCase.severity,
                func.coalesce(func.sum(DiseaseCase.case_count), 0).label("total"),
            )
            .filter(
                DiseaseCase.icd_code == icd_code,
                DiseaseCase.severity.isnot(None),
            )
            .group_by(DiseaseCase.severity)
            .all()
        )

        sev_totals = {s: int(t) for s, t in rows}
        total = sum(sev_totals.values())
        if total == 0:
            return None

        mild = sev_totals.get("mild", 0)
        moderate = sev_totals.get("moderate", 0)
        severe = sev_totals.get("severe", 0)

        return {
            "mild_rate": round(mild / total * 100, 2),
            "moderate_rate": round(moderate / total * 100, 2),
            "severe_rate": round(severe / total * 100, 2),
            "total_cases": total,
            "mild_cases": mild,
            "moderate_cases": moderate,
            "severe_cases": severe,
        }

    def update_severity_rates_from_history(
        self,
        force: bool = False,
        updated_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Cập nhật `severity_rate` cho tất cả 4 bệnh từ dữ liệu lịch sử.

        Args:
            force: True = phân loại lại tất cả ca trước khi tính
            updated_by: Username người chạy

        Returns:
            Danh sách kết quả update cho từng bệnh
        """
        # Bước 1: phân loại ca
        if force:
            self.classify_all_cases(force=True)
        else:
            # Vẫn classify ca chưa có severity
            self.classify_all_cases(force=False)

        # Bước 2: tính tỷ lệ và cập nhật bảng severity_rate
        rates = self.db.query(SeverityRate).all()
        results = []

        for rate in rates:
            computed = self.compute_rates_from_history(rate.icd_code)
            if not computed:
                results.append({
                    "icd_code": rate.icd_code,
                    "disease_name": rate.disease_name,
                    "status": "skipped",
                    "reason": "Không có ca bệnh đã phân loại.",
                })
                continue

            old = {
                "mild_rate": float(rate.mild_rate),
                "moderate_rate": float(rate.moderate_rate),
                "severe_rate": float(rate.severe_rate),
            }

            rate.mild_rate = computed["mild_rate"]
            rate.moderate_rate = computed["moderate_rate"]
            rate.severe_rate = computed["severe_rate"]
            if updated_by:
                rate.updated_by = updated_by

            results.append({
                "icd_code": rate.icd_code,
                "disease_name": rate.disease_name,
                "status": "updated",
                "total_cases": computed["total_cases"],
                "old": old,
                "new": {
                    "mild_rate": computed["mild_rate"],
                    "moderate_rate": computed["moderate_rate"],
                    "severe_rate": computed["severe_rate"],
                },
                "breakdown": {
                    "mild_cases": computed["mild_cases"],
                    "moderate_cases": computed["moderate_cases"],
                    "severe_cases": computed["severe_cases"],
                },
            })

        self.db.commit()
        logger.info(
            "Updated %d severity rates from history (force=%s)",
            len([r for r in results if r["status"] == "updated"]),
            force,
        )
        return results

    def get_classification_preview(
        self,
        icd_code: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Preview phân loại — không cập nhật DB.

        Trả về phân bố mild/moderate/severe + sample các case để admin review.
        """
        q = self.db.query(DiseaseCase)
        if icd_code:
            q = q.filter(DiseaseCase.icd_code == icd_code)

        cases = q.limit(limit).all()

        breakdown = {"mild": 0, "moderate": 0, "severe": 0}
        samples = []

        for case in cases:
            sev = self.classify_case(case)
            breakdown[sev] += 1
            samples.append({
                "case_id": case.id,
                "icd_code": case.icd_code,
                "disease_name": case.disease_name,
                "case_count": case.case_count,
                "length_of_stay": case.length_of_stay,
                "sub_icd_count": case.sub_icd_count,
                "current_severity": case.severity,
                "predicted_severity": sev,
            })

        return {
            "icd_code": icd_code,
            "total_previewed": len(cases),
            "breakdown": breakdown,
            "samples": samples,
        }
