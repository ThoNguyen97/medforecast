"""
Configuration API endpoints.

Provides access to system-wide configuration (bảng system_config, key → value).
All write operations are restricted to users with the Administrator role and
are recorded in audit_logs.

Routes
------
GET  /api/v1/config                        – List all config entries
GET  /api/v1/config/{key}                  – Get a single config entry by key
PUT  /api/v1/config/{key}                  – Update a config entry (Admin)

12/09/2026: /conversion-ratios và /thresholds (3/7/14 ngày) đã gỡ. Ngưỡng
thật của DSS là `dss.thresholds`, tham số Tầng 2 là `dss.care_level` — hai
bản ghi này sửa qua /api/v1/dss/params (có kiểm khoảng và mô tả hệ quả).
"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.schemas.base import SystemConfigResponse, SystemConfigUpdate
from app.services.config_service import ConfigService

router = APIRouter(tags=["configuration"])
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[SystemConfigResponse])
def list_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Return all system configuration entries.

    All authenticated users can read configuration values.
    """
    logger.info(f"List configs requested by user={current_user.username}")
    service = ConfigService(db)
    return service.get_all_configs()


@router.get("/{key}", response_model=SystemConfigResponse)
def get_config_by_key(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Return a single configuration entry by its key.

    Returns 404 if the key does not exist.
    All authenticated users can read configuration values.
    """
    logger.info(
        f"Get config key='{key}' requested by user={current_user.username}"
    )
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
    """
    Create or update a configuration entry by key.

    Requires Administrator role.
    If the key does not exist it will be created.
    Changes are recorded in audit_logs with old and new values.
    """
    logger.info(
        f"Update config key='{key}' requested by user={current_user.username}"
    )
    service = ConfigService(db)
    return service.update_config(
        key=key,
        data=body,
        updated_by_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
