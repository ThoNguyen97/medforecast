"""Supply Recommendations API.

Endpoints để tính nhu cầu thuốc + đề xuất nhập kho theo công thức mục 4-7.
"""
import logging
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.supply_recommendation import SupplyRecommendation
from app.services.supply_recommendation_service import (
    DEFAULT_BUFFER_RATE,
    SupplyRecommendationService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CalculateRequest(BaseModel):
    """Request payload để tính nhu cầu cho 1 bệnh cụ thể."""
    icd_code: str = Field(..., description="Mã ICD bệnh: J20, J06, J02, J01")
    predicted_cases: int = Field(..., ge=0, description="Tổng số ca dự báo")
    forecast_month: date = Field(..., description="Tháng dự báo (ngày đầu tháng)")
    buffer_rate: float = Field(
        DEFAULT_BUFFER_RATE,
        ge=0,
        le=100,
        description="Hệ số dự phòng % (mặc định 15)",
    )
    save: bool = Field(False, description="Có lưu vào DB không")


class CalculateMonthRequest(BaseModel):
    """Request payload để tính nhu cầu cho tất cả bệnh trong 1 tháng."""
    forecast_month: date = Field(..., description="Tháng dự báo")
    location: Optional[str] = Field(None, description="Khu vực, để trống = toàn quốc")
    buffer_rate: float = Field(
        DEFAULT_BUFFER_RATE,
        ge=0,
        le=100,
        description="Hệ số dự phòng %",
    )
    save: bool = Field(False, description="Có lưu vào DB không")


@router.post("/calculate")
def calculate_for_disease(
    payload: CalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Tính nhu cầu thuốc + đề xuất nhập cho 1 bệnh trong 1 tháng (mục 4-7).

    Áp dụng đầy đủ công thức:
    - Mục 5.1: Phân bổ ca theo Nhẹ/TB/Nặng
    - Mục 6: Nhu cầu = Σ(số ca × định mức) × (1 + dự phòng)
    - Mục 7: Đề xuất nhập = max(0, nhu cầu + ngưỡng AT - tồn kho)
    """
    service = SupplyRecommendationService(db)
    try:
        result = service.calculate_for_disease(
            icd_code=payload.icd_code,
            predicted_cases=payload.predicted_cases,
            forecast_month=payload.forecast_month,
            buffer_rate=payload.buffer_rate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if payload.save:
        saved = service.save_recommendations(result, created_by=current_user.username)
        result["saved_count"] = saved

    return result


@router.post("/calculate-month")
def calculate_for_month(
    payload: CalculateMonthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Tính nhu cầu + đề xuất nhập cho TẤT CẢ bệnh trong 1 tháng.

    Tự động lấy số ca dự báo từ disease_forecast hoặc disease_case (fallback).
    Trả về danh sách thuốc đã cộng dồn nhu cầu qua các bệnh.
    """
    service = SupplyRecommendationService(db)
    result = service.calculate_for_month(
        forecast_month=payload.forecast_month,
        location=payload.location,
        buffer_rate=payload.buffer_rate,
    )

    if payload.save:
        total_saved = 0
        for d in result["diseases"]:
            total_saved += service.save_recommendations(
                d, created_by=current_user.username
            )
        result["saved_count"] = total_saved

    return result


@router.get("/")
def list_recommendations(
    forecast_month: Optional[date] = Query(None, description="Filter theo tháng"),
    icd_code: Optional[str] = Query(None, description="Filter theo bệnh"),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Lấy danh sách đề xuất nhập kho đã lưu."""
    q = db.query(SupplyRecommendation).order_by(
        SupplyRecommendation.forecast_month.desc(),
        SupplyRecommendation.suggested_import.desc(),
    )
    if forecast_month:
        q = q.filter(SupplyRecommendation.forecast_month == forecast_month)
    if icd_code:
        q = q.filter(SupplyRecommendation.icd_code == icd_code)
    if status_filter:
        q = q.filter(SupplyRecommendation.status == status_filter)

    total = q.count()
    rows = q.offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "forecast_month": r.forecast_month.isoformat() if r.forecast_month else None,
                "icd_code": r.icd_code,
                "disease_name": r.disease_name,
                "supply_id": r.supply_id,
                "drug_code": r.drug_code,
                "ten_hoat_chat": r.ten_hoat_chat,
                "predicted_cases": r.predicted_cases,
                "predicted_mild": r.predicted_mild,
                "predicted_moderate": r.predicted_moderate,
                "predicted_severe": r.predicted_severe,
                "need_before_buffer": r.need_before_buffer,
                "buffer_rate": float(r.buffer_rate) if r.buffer_rate else None,
                "predicted_need": r.predicted_need,
                "current_stock": r.current_stock,
                "safety_stock": r.safety_stock,
                "suggested_import": r.suggested_import,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.put("/{rec_id}/status")
def update_recommendation_status(
    rec_id: int,
    new_status: str = Query(..., description="pending, approved, ordered, completed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Cập nhật trạng thái đề xuất nhập kho."""
    valid = {"pending", "approved", "ordered", "completed"}
    if new_status not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status phải là một trong: {', '.join(valid)}",
        )

    rec = db.query(SupplyRecommendation).filter(SupplyRecommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {rec_id} not found",
        )

    rec.status = new_status
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "status": rec.status}


@router.delete("/{rec_id}")
def delete_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Xóa 1 đề xuất nhập kho."""
    rec = db.query(SupplyRecommendation).filter(SupplyRecommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {rec_id} not found",
        )
    db.delete(rec)
    db.commit()
    return {"id": rec_id, "deleted": True}
