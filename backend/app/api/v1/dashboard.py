"""Trang Tổng quan và Cảnh báo thiếu hụt — API v2.

Routes
------
GET /api/v1/dashboard/v2                   toàn bộ màn hình Tổng quan (một payload)
GET /api/v1/dashboard/v2/alerts            trang Cảnh báo thiếu hụt, phân trang server
GET /api/v1/dashboard/v2/forecast          Ŷ_g ba khối bằng ensemble (xem trước, có cache)
GET /api/v1/dashboard/v2/forecast/history  sổ theo dõi mô hình trong vận hành

Cả bốn endpoint CHỈ ĐỌC dữ liệu nghiệp vụ. Phần ghi duy nhất là cache dự báo
(`dss_forecast_cache`, `forecast_runs`) — do dss_dashboard quản, khoá theo dấu
vân tay dữ liệu, không đụng vào bảng nghiệp vụ nào.

Các endpoint cũ (/overview, /summary, /risk-status, /critical-alerts,
/case-trend, /care-level) và lớp cache Redis đã gỡ 13/09/2026: giao diện không
còn gọi, mỗi cái một mốc thời gian và một cách đếm khác v2.
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
    """Số ca kỳ đã chốt, dự báo đã ghi nhận, DOI + cảnh báo, phân cấp chăm sóc,
    chất lượng mô hình, tình trạng dữ liệu.

    Chưa ghi nhận dự báo kỳ tới thì `demand.ready = false`, cột `d_forecast` /
    `delta_need` để None — giao diện phải nói "chưa có dự báo", không hiện 0.
    """
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
    """Cùng chuỗi Tầng 1 → 2 → 3 với `/v2` (cùng dự báo, cùng định mức, cùng
    ngưỡng), chỉ khác là trả toàn bộ dòng có phân trang thay vì top-8."""
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
    """Ŷ_g ba khối bằng ensemble PRODUCTION_CONFIG — bản xem trước, KHÔNG nuôi
    Tổng quan/Cảnh báo (hai trang đó đọc bản đã Ghi nhận ở trang Phân tích).

    Lần đầu với một bộ dữ liệu mất vài chục giây (dựng khoảng thực nghiệm
    ~25 lần khớp mỗi khối); kết quả cache theo dấu vân tay chuỗi ca + thời
    tiết + cấu hình, đồng bộ xong khoá tự đổi.
    """
    return dss_dashboard.forecast_payload(db, compute=True, force=force)


@router.get("/v2/forecast/history")
def get_dashboard_v2_forecast_history(
    limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Mỗi lần app khớp mô hình là một dòng; kỳ đích chốt thì điền thực tế và
    sai số. Khác backtest: đây là con số màn hình đã hiện vào thời điểm đó."""
    return dss_dashboard.forecast_history(db, limit=limit)
