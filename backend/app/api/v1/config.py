"""API cấu hình hệ thống (bảng system_config, khoá → giá trị).

Thao tác ghi chỉ dành cho Administrator và được ghi vào audit_logs.
Ngưỡng DSS (`dss.thresholds`) và tham số Tầng 2 (`dss.care_level`) sửa qua
/api/v1/dss/params, nơi có kiểm tra miền giá trị.

Routes
------
GET  /api/v1/config                        – Liệt kê mọi cấu hình
GET  /api/v1/config/{key}                  – Lấy một cấu hình theo khoá
PUT  /api/v1/config/{key}                  – Cập nhật một cấu hình (Admin)
"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.schemas.base import SystemConfigResponse, SystemConfigUpdate
from app.services.config_service import ConfigService

router = APIRouter(tags=["configuration"])
logger = logging.getLogger(__name__)


# ── Helpers ──

def _get_client_ip(request: Request) -> str:
    """Lấy IP client, ưu tiên X-Forwarded-For khi chạy sau proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Endpoints ──

@router.get("", response_model=List[SystemConfigResponse])
def list_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Mọi dòng system_config (mật khẩu HIS đã che)."""
    service = ConfigService(db)
    return service.get_all_configs()


@router.get("/{key}", response_model=SystemConfigResponse)
def get_config_by_key(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Một dòng theo khoá; 404 nếu không có (mật khẩu HIS đã che)."""
    service = ConfigService(db)
    return service.get_config_by_key(key)


@router.put("/{key}", response_model=SystemConfigResponse)
def update_config_by_key(
    key: str,
    body: SystemConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> Any:
    """Tạo/sửa một dòng cấu hình (Admin), ghi audit_logs.

    Ba khoá có endpoint riêng kèm kiểm tra dữ liệu bị chặn ở đây, tránh ghi
    đè ngưỡng DSS hay mật khẩu HIS bằng chuỗi tự do:
    `dss.thresholds`, `dss.care_level` → PUT /dss/params;
    `his_sync.connection` → PUT /sync/config.
    """
    if key in ("dss.thresholds", "dss.care_level", "his_sync.connection"):
        raise HTTPException(
            status_code=422,
            detail=f"Khoá '{key}' phải sửa qua endpoint chuyên biệt (/dss/params hoặc /sync/config).",
        )
    service = ConfigService(db)
    return service.update_config(
        key=key,
        data=body,
        updated_by_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
