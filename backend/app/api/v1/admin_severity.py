"""Admin API — Quản lý tỷ lệ severity và định mức thuốc/vật tư.

Endpoints để admin:
- Sửa tỷ lệ Nhẹ/TB/Nặng cho từng bệnh (severity_rate)
- Sửa định mức thuốc/vật tư cho từng bệnh × mức độ (disease_supply_norm)
- Suy luận tự động tỷ lệ severity từ dữ liệu lịch sử (mục 5.2)
"""
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.disease_supply_norm import DiseaseSupplyNorm
from app.models.medical_supply import MedicalSupply
from app.models.severity_rate import SeverityRate
from app.models.user import User
from app.services.severity_inference_service import SeverityInferenceService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic schemas ────────────────────────────────────────────────────────

class SeverityRateOut(BaseModel):
    id: int
    icd_code: str
    disease_name: str
    mild_rate: float
    moderate_rate: float
    severe_rate: float
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class SeverityRateUpdate(BaseModel):
    mild_rate: float = Field(..., ge=0, le=100)
    moderate_rate: float = Field(..., ge=0, le=100)
    severe_rate: float = Field(..., ge=0, le=100)
    note: Optional[str] = None

    @field_validator("severe_rate")
    @classmethod
    def _check_total_100(cls, v, info):
        mild = info.data.get("mild_rate", 0)
        moderate = info.data.get("moderate_rate", 0)
        total = mild + moderate + v
        if abs(total - 100) > 0.01:
            raise ValueError(
                f"Tổng tỷ lệ phải = 100% (hiện {mild} + {moderate} + {v} = {total})"
            )
        return v


class DiseaseSupplyNormOut(BaseModel):
    id: int
    icd_code: str
    disease_name: str
    severity: str
    supply_id: int
    supply_code: Optional[str] = None
    drug_code: Optional[str] = None
    ten_hoat_chat: Optional[str] = None
    unit: Optional[str] = None
    group_name: Optional[str] = None
    quantity_per_case: int

    model_config = {"from_attributes": True}


class DiseaseSupplyNormUpsert(BaseModel):
    icd_code: str = Field(..., description="J20, J06, J02, J01")
    severity: str = Field(..., description="mild, moderate, severe")
    supply_id: int
    quantity_per_case: int = Field(..., ge=0)


class BulkNormUpsert(BaseModel):
    norms: List[DiseaseSupplyNormUpsert]


# ── Severity Rate endpoints ─────────────────────────────────────────────────

@router.get("/severity-rates", response_model=List[SeverityRateOut])
def list_severity_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Lấy tỷ lệ Nhẹ/TB/Nặng cho 4 bệnh."""
    rows = db.query(SeverityRate).order_by(SeverityRate.icd_code).all()
    return [
        {
            "id": r.id,
            "icd_code": r.icd_code,
            "disease_name": r.disease_name,
            "mild_rate": float(r.mild_rate),
            "moderate_rate": float(r.moderate_rate),
            "severe_rate": float(r.severe_rate),
            "note": r.note,
        }
        for r in rows
    ]


@router.put("/severity-rates/{icd_code}", response_model=SeverityRateOut)
def update_severity_rate(
    icd_code: str,
    payload: SeverityRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Cập nhật tỷ lệ Nhẹ/TB/Nặng cho 1 bệnh.

    Tổng tỷ lệ phải = 100%.
    """
    rate = (
        db.query(SeverityRate)
        .filter(SeverityRate.icd_code == icd_code)
        .first()
    )
    if not rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bệnh {icd_code}",
        )

    rate.mild_rate = payload.mild_rate
    rate.moderate_rate = payload.moderate_rate
    rate.severe_rate = payload.severe_rate
    rate.note = payload.note
    rate.updated_by = current_user.username

    db.commit()
    db.refresh(rate)

    logger.info(
        "User %s updated severity rate for %s: %s/%s/%s",
        current_user.username, icd_code,
        payload.mild_rate, payload.moderate_rate, payload.severe_rate,
    )

    return {
        "id": rate.id,
        "icd_code": rate.icd_code,
        "disease_name": rate.disease_name,
        "mild_rate": float(rate.mild_rate),
        "moderate_rate": float(rate.moderate_rate),
        "severe_rate": float(rate.severe_rate),
        "note": rate.note,
    }


# ── Disease Supply Norm endpoints ───────────────────────────────────────────

@router.get("/supply-norms", response_model=List[DiseaseSupplyNormOut])
def list_supply_norms(
    icd_code: Optional[str] = Query(None, description="Filter theo bệnh"),
    severity: Optional[str] = Query(None, description="Filter theo mức độ"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Lấy định mức thuốc/vật tư theo bệnh × mức độ."""
    q = (
        db.query(DiseaseSupplyNorm, MedicalSupply)
        .join(MedicalSupply, MedicalSupply.id == DiseaseSupplyNorm.supply_id)
        .order_by(
            DiseaseSupplyNorm.icd_code,
            DiseaseSupplyNorm.severity,
            MedicalSupply.supply_code,
        )
    )
    if icd_code:
        q = q.filter(DiseaseSupplyNorm.icd_code == icd_code)
    if severity:
        q = q.filter(DiseaseSupplyNorm.severity == severity)

    rows = q.all()
    return [
        {
            "id": norm.id,
            "icd_code": norm.icd_code,
            "disease_name": norm.disease_name,
            "severity": norm.severity,
            "supply_id": supply.id,
            "supply_code": supply.supply_code,
            "drug_code": supply.drug_code,
            "ten_hoat_chat": supply.ten_hoat_chat,
            "unit": supply.unit,
            "group_name": supply.group_name,
            "quantity_per_case": norm.quantity_per_case,
        }
        for norm, supply in rows
    ]


@router.get("/supply-norms/by-severity")
def get_norms_by_severity(
    icd_code: Optional[str] = Query(None, description="Lọc theo bệnh"),
    severity: Optional[str] = Query(None, description="Lọc theo mức độ (mild/moderate/severe)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Lấy định mức thuốc vật tư lọc theo cấp độ.
    
    Trả về danh sách định mức với thông tin chi tiết:
    [
        {
            "icd_code": "J20",
            "disease_name": "Viêm phế quản cấp",
            "severity": "mild",
            "supply_id": 1,
            "supply_code": "VT001",
            "ten_hoat_chat": "Paracetamol",
            "unit": "Viên",
            "quantity_per_case": 6
        },
        ...
    ]
    """
    q = db.query(DiseaseSupplyNorm, MedicalSupply).join(
        MedicalSupply, MedicalSupply.id == DiseaseSupplyNorm.supply_id
    )
    
    if icd_code:
        q = q.filter(DiseaseSupplyNorm.icd_code == icd_code)
    if severity:
        if severity not in {"mild", "moderate", "severe"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="severity phải là: mild, moderate, severe"
            )
        q = q.filter(DiseaseSupplyNorm.severity == severity)
    
    q = q.order_by(
        DiseaseSupplyNorm.icd_code,
        DiseaseSupplyNorm.severity,
        MedicalSupply.supply_code
    )
    rows = q.all()
    
    return [
        {
            "icd_code": norm.icd_code,
            "disease_name": norm.disease_name,
            "severity": norm.severity,
            "supply_id": norm.supply_id,
            "supply_code": supply.supply_code,
            "drug_code": supply.drug_code,
            "ten_hoat_chat": supply.ten_hoat_chat,
            "unit": supply.unit,
            "group_name": supply.group_name,
            "quantity_per_case": norm.quantity_per_case,
        }
        for norm, supply in rows
    ]


@router.get("/supply-norms/matrix")
def get_norm_matrix(
    icd_code: str = Query(..., description="Mã ICD bệnh"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Lấy ma trận định mức cho 1 bệnh: mỗi thuốc × 3 mức độ.

    Trả về dạng dễ render trong UI:
    {
        "icd_code": "J20",
        "disease_name": "...",
        "severity_rate": { "mild_rate": 70, "moderate_rate": 25, "severe_rate": 5 },
        "supplies": [
            {
                "supply_id": 1,
                "supply_code": "VT001",
                "drug_code": "...",
                "ten_hoat_chat": "Paracetamol",
                "unit": "Viên",
                "group_name": "Hạ sốt",
                "mild": 6,
                "moderate": 10,
                "severe": 12
            },
            ...
        ]
    }
    """
    severity_rate = (
        db.query(SeverityRate)
        .filter(SeverityRate.icd_code == icd_code)
        .first()
    )
    if not severity_rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bệnh {icd_code}",
        )

    # Lấy tất cả 15 thuốc/vật tư
    all_supplies = db.query(MedicalSupply).order_by(MedicalSupply.supply_code).all()

    # Lấy norms của bệnh này
    norms = (
        db.query(DiseaseSupplyNorm)
        .filter(DiseaseSupplyNorm.icd_code == icd_code)
        .all()
    )
    norm_map: dict[tuple[int, str], int] = {
        (n.supply_id, n.severity): n.quantity_per_case for n in norms
    }

    supplies = []
    for s in all_supplies:
        supplies.append({
            "supply_id": s.id,
            "supply_code": s.supply_code,
            "drug_code": s.drug_code,
            "ten_hoat_chat": s.ten_hoat_chat,
            "unit": s.unit,
            "group_name": s.group_name,
            "mild": norm_map.get((s.id, "mild"), 0),
            "moderate": norm_map.get((s.id, "moderate"), 0),
            "severe": norm_map.get((s.id, "severe"), 0),
        })

    return {
        "icd_code": severity_rate.icd_code,
        "disease_name": severity_rate.disease_name,
        "severity_rate": {
            "mild_rate": float(severity_rate.mild_rate),
            "moderate_rate": float(severity_rate.moderate_rate),
            "severe_rate": float(severity_rate.severe_rate),
        },
        "supplies": supplies,
    }


@router.put("/supply-norms")
def upsert_supply_norm(
    payload: DiseaseSupplyNormUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Tạo mới hoặc cập nhật 1 định mức (icd_code + severity + supply_id)."""
    if payload.severity not in {"mild", "moderate", "severe"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="severity phải là: mild, moderate, severe",
        )

    # Lấy disease_name từ severity_rate
    sr = (
        db.query(SeverityRate)
        .filter(SeverityRate.icd_code == payload.icd_code)
        .first()
    )
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"icd_code {payload.icd_code} không tồn tại trong severity_rate",
        )

    # Kiểm tra supply_id tồn tại
    supply = (
        db.query(MedicalSupply)
        .filter(MedicalSupply.id == payload.supply_id)
        .first()
    )
    if not supply:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"supply_id {payload.supply_id} không tồn tại",
        )

    # Upsert
    existing = (
        db.query(DiseaseSupplyNorm)
        .filter(
            DiseaseSupplyNorm.icd_code == payload.icd_code,
            DiseaseSupplyNorm.severity == payload.severity,
            DiseaseSupplyNorm.supply_id == payload.supply_id,
        )
        .first()
    )
    if existing:
        existing.quantity_per_case = payload.quantity_per_case
        existing.disease_name = sr.disease_name
        existing.updated_by = current_user.username
        norm = existing
        action = "updated"
    else:
        norm = DiseaseSupplyNorm(
            icd_code=payload.icd_code,
            disease_name=sr.disease_name,
            severity=payload.severity,
            supply_id=payload.supply_id,
            quantity_per_case=payload.quantity_per_case,
            updated_by=current_user.username,
        )
        db.add(norm)
        action = "created"

    db.commit()
    db.refresh(norm)

    logger.info(
        "User %s %s norm: %s/%s/supply=%s qty=%s",
        current_user.username, action,
        payload.icd_code, payload.severity, payload.supply_id,
        payload.quantity_per_case,
    )

    return {
        "id": norm.id,
        "icd_code": norm.icd_code,
        "disease_name": norm.disease_name,
        "severity": norm.severity,
        "supply_id": norm.supply_id,
        "supply_code": supply.supply_code,
        "ten_hoat_chat": supply.ten_hoat_chat,
        "quantity_per_case": norm.quantity_per_case,
        "action": action,
    }


@router.put("/supply-norms/bulk")
def bulk_upsert_norms(
    payload: BulkNormUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Cập nhật hàng loạt định mức. Dùng khi admin save toàn bộ ma trận."""
    updated = 0
    created = 0
    errors: list[dict] = []

    # Cache disease_name + supply lookup
    sr_map = {
        sr.icd_code: sr.disease_name
        for sr in db.query(SeverityRate).all()
    }
    supply_ids = {
        s.id for s in db.query(MedicalSupply.id).all()
    }

    for idx, n in enumerate(payload.norms):
        if n.icd_code not in sr_map:
            errors.append({"idx": idx, "reason": f"icd_code {n.icd_code} không tồn tại"})
            continue
        if n.supply_id not in supply_ids:
            errors.append({"idx": idx, "reason": f"supply_id {n.supply_id} không tồn tại"})
            continue
        if n.severity not in {"mild", "moderate", "severe"}:
            errors.append({"idx": idx, "reason": f"severity '{n.severity}' không hợp lệ"})
            continue

        existing = (
            db.query(DiseaseSupplyNorm)
            .filter(
                DiseaseSupplyNorm.icd_code == n.icd_code,
                DiseaseSupplyNorm.severity == n.severity,
                DiseaseSupplyNorm.supply_id == n.supply_id,
            )
            .first()
        )
        if existing:
            existing.quantity_per_case = n.quantity_per_case
            existing.disease_name = sr_map[n.icd_code]
            existing.updated_by = current_user.username
            updated += 1
        else:
            db.add(DiseaseSupplyNorm(
                icd_code=n.icd_code,
                disease_name=sr_map[n.icd_code],
                severity=n.severity,
                supply_id=n.supply_id,
                quantity_per_case=n.quantity_per_case,
                updated_by=current_user.username,
            ))
            created += 1

    db.commit()
    return {
        "created": created,
        "updated": updated,
        "errors": errors,
    }


@router.delete("/supply-norms/{norm_id}")
def delete_norm(
    norm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Xoá 1 định mức."""
    norm = db.query(DiseaseSupplyNorm).filter(DiseaseSupplyNorm.id == norm_id).first()
    if not norm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Norm {norm_id} not found",
        )
    db.delete(norm)
    db.commit()
    return {"id": norm_id, "deleted": True}


@router.get("/supply-norms/summary/all-diseases")
def get_norms_summary_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Tóm tắt định mức cho tất cả 4 bệnh (ma trận tổng quát).
    
    Trả về:
    {
        "diseases": [
            {
                "icd_code": "J20",
                "disease_name": "Viêm phế quản cấp",
                "severity_rate": { "mild_rate": 70, "moderate_rate": 25, "severe_rate": 5 },
                "supply_count": 15,
                "norms_count": { "mild": 15, "moderate": 15, "severe": 15 }
            },
            ...
        ]
    }
    """
    all_diseases = db.query(SeverityRate).order_by(SeverityRate.icd_code).all()
    
    diseases = []
    for disease in all_diseases:
        # Đếm số norms theo severity
        norms_by_severity = {}
        for sev in ["mild", "moderate", "severe"]:
            count = (
                db.query(DiseaseSupplyNorm)
                .filter(
                    DiseaseSupplyNorm.icd_code == disease.icd_code,
                    DiseaseSupplyNorm.severity == sev,
                )
                .count()
            )
            norms_by_severity[sev] = count
        
        # Tổng số norms
        total_norms = (
            db.query(DiseaseSupplyNorm)
            .filter(DiseaseSupplyNorm.icd_code == disease.icd_code)
            .count()
        )
        
        diseases.append({
            "icd_code": disease.icd_code,
            "disease_name": disease.disease_name,
            "severity_rate": {
                "mild_rate": float(disease.mild_rate),
                "moderate_rate": float(disease.moderate_rate),
                "severe_rate": float(disease.severe_rate),
            },
            "total_supplies": 15,  # Số lượng thuốc tối đa
            "total_norms": total_norms,
            "norms_by_severity": norms_by_severity,
        })
    
    return {
        "total_diseases": len(diseases),
        "diseases": diseases,
    }



# ── Severity Inference endpoints (mục 5.2) ──────────────────────────────────

@router.get("/severity-rates/preview")
def preview_severity_classification(
    icd_code: Optional[str] = Query(None, description="Filter theo bệnh"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Preview phân loại Nhẹ/TB/Nặng từ dữ liệu lịch sử (KHÔNG ghi DB).

    Hệ thống sẽ phân loại theo quy tắc mục 5.2:
    - Nhẹ: LengthOfStay = 0, ít can thiệp
    - Trung bình: LengthOfStay 1-3, có khí dung/kháng sinh/corticoid
    - Nặng: LengthOfStay >= 4, có kháng sinh tiêm/dịch truyền/vật tư y tế
    """
    service = SeverityInferenceService(db)
    return service.get_classification_preview(icd_code=icd_code, limit=limit)


@router.post("/severity-rates/recompute")
def recompute_severity_from_history(
    force: bool = Query(
        False,
        description=(
            "True = phân loại lại tất cả ca (ghi đè severity cũ). "
            "False = chỉ phân loại ca chưa có severity."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Tự động cập nhật tỷ lệ Nhẹ/TB/Nặng từ dữ liệu lịch sử (mục 5.2).

    Quy trình:
    1. Phân loại từng ca bệnh dựa trên LengthOfStay, SubICD_Count, supplies đã dùng
    2. Tính tỷ lệ = Số ca mỗi mức / Tổng số ca của bệnh
    3. Ghi đè severity_rate
    """
    service = SeverityInferenceService(db)
    results = service.update_severity_rates_from_history(
        force=force,
        updated_by=current_user.username,
    )
    return {
        "force": force,
        "diseases": results,
        "summary": {
            "total_diseases": len(results),
            "updated": len([r for r in results if r["status"] == "updated"]),
            "skipped": len([r for r in results if r["status"] == "skipped"]),
        },
    }
