"""API trang Tổng quan và Cảnh báo thiếu hụt.
Chỉ đọc; phần ghi duy nhất là cache dự báo do dss_dashboard quản lý.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import dss_dashboard

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/v2")
def get_dashboard_v2(
    focus: bool = Query(True, description="Tập trọng tâm (tỷ trọng hô hấp ≥ 25%) hay toàn danh mục"),
    level: Optional[str] = Query(None, description="Lọc bảng cảnh báo: red | amber | green | grey; bỏ trống = Đỏ + Vàng"),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Toàn bộ payload màn hình Tổng quan.
    Chưa ghi nhận dự báo kỳ tới thì `demand.ready = false`, `d_forecast`/`delta_need` = None."""
    try:
        return dss_dashboard.overview_payload(db, focus=focus, level=level, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/v2/alerts")
def get_dashboard_v2_alerts(
    focus: bool = Query(True, description="Tập trọng tâm (tỷ trọng hô hấp ≥ 25%) hay toàn danh mục"),
    level: Optional[str] = Query(None, description="red | amber | green | grey; bỏ trống = mọi mức"),
    q: Optional[str] = Query(None, description="Lọc theo mã hoặc tên hoạt chất"),
    danh_muc: Optional[str] = Query(None, description="Lọc theo danh mục"),
    limit: int = Query(50, ge=1, le=2000),  # 2000: trang Quản lý thuốc lấy toàn danh mục một lần
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Bảng cảnh báo đầy đủ, phân trang server; cùng chuỗi Tầng 1 → 2 → 3 với `/v2`."""
    try:
        return dss_dashboard.alerts_payload(db, focus=focus, level=level, q=q,
                                            danh_muc=danh_muc, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/v2/forecast")
def get_dashboard_v2_forecast(
    force: bool = Query(False, description="Bỏ cache, khớp lại mô hình"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Ŷ_g ba khối bằng ensemble, bản xem trước (Tổng quan/Cảnh báo đọc bản đã ghi nhận).
    Lần tính đầu mất vài chục giây; cache theo dấu vân tay dữ liệu + cấu hình."""
    return dss_dashboard.forecast_payload(db, compute=True, force=force)


@router.get("/v2/forecast/history")
def get_dashboard_v2_forecast_history(
    limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Sổ theo dõi mô hình trong vận hành: mỗi lần khớp một dòng, kỳ chốt thì điền thực tế và sai số."""
    return dss_dashboard.forecast_history(db, limit=limit)
