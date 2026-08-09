"""API dự báo phân cấp (đọc từ tầng MART) + báo cáo tồn kho từ MART.

Đăng ký ở /api/v1/forecast-hier. Yêu cầu pipeline đã nạp mart vào cùng DB app.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.hierarchical_forecast_service import (
    HierarchicalForecastService, METHODS)

router = APIRouter()


@router.get("/methods")
def list_methods():
    """Danh sách các hướng hòa giải phân cấp hỗ trợ."""
    return {"methods": list(METHODS), "default": "top_down_dynamic"}


@router.get("/blocks")
def list_blocks(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Các nhóm ICD có sẵn trong MART."""
    return {"blocks": HierarchicalForecastService(db).list_blocks()}


@router.get("/inventory")
def inventory_report(
    limit: int = Query(500, ge=1, le=5000),
    group_name: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Báo cáo tồn kho hiện tại (đọc từ mart_inventory)."""
    return {"items": HierarchicalForecastService(db).inventory_report(limit, group_name)}


@router.get("/{block}")
def forecast_block(
    block: str,
    method: str = Query("top_down_dynamic", description=f"một trong {METHODS}"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Dự báo phân cấp cho một nhóm ICD (tháng kế tiếp), chia về từng mã."""
    try:
        return HierarchicalForecastService(db).forecast(block, method=method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503,
                            detail=f"Chưa sẵn sàng (có thể chưa đồng bộ dữ liệu): {e}")
