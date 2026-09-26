"""API nhật ký kiểm toán (audit_logs) và nhật ký hệ thống; mọi endpoint chỉ dành cho Administrator.

Routes
------
GET  /api/v1/audit-logs              – Nhật ký kiểm toán, phân trang
GET  /api/v1/system-logs             – Nhật ký hệ thống, phân trang
GET  /api/v1/system-logs/errors      – Chỉ các dòng mức ERROR
POST /api/v1/system-logs/cleanup     – Chạy dọn nhật ký theo hạn lưu giữ
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user
from app.models.user import User
from app.schemas.base import (
    AuditLogListResponse,
    AuditLogResponse,
    SystemLogListResponse,
    SystemLogResponse,
)
from app.services.audit_log_service import DEFAULT_PAGE_SIZE, AuditLogService

router = APIRouter(tags=["audit-logs"])
logger = logging.getLogger(__name__)


# ── Nhật ký kiểm toán ──

@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    start_date: Optional[datetime] = Query(
        None, description="Filter entries created on or after this datetime (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter entries created on or before this datetime (ISO 8601)"
    ),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(
        None, description="Filter by action (partial, case-insensitive match)"
    ),
    table_name: Optional[str] = Query(
        None, description="Filter by table name (partial, case-insensitive match)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=200, description="Items per page (default 50)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> AuditLogListResponse:
    """Danh sách thao tác thay đổi dữ liệu (tạo/sửa/xoá) có phân trang, lọc theo
    khoảng thời gian, người dùng, loại thao tác và bảng. Yêu cầu Administrator."""
    logger.info(
        "Audit logs requested by admin=%s page=%d page_size=%d "
        "start=%s end=%s user_id=%s action=%s table=%s",
        current_user.username,
        page,
        page_size,
        start_date,
        end_date,
        user_id,
        action,
        table_name,
    )
    service = AuditLogService(db)
    total, items = service.get_audit_logs(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action=action,
        table_name=table_name,
        page=page,
        page_size=page_size,
    )
    enriched = [AuditLogResponse(**service._enrich_audit_log(item)) for item in items]
    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=enriched,
    )


# ── Nhật ký hệ thống ──

@router.get("/system-logs/errors", response_model=SystemLogListResponse)
def list_error_logs(
    start_date: Optional[datetime] = Query(
        None, description="Filter entries created on or after this datetime (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter entries created on or before this datetime (ISO 8601)"
    ),
    module_name: Optional[str] = Query(
        None, description="Filter by module name (partial, case-insensitive match)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=200, description="Items per page (default 50)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> SystemLogListResponse:
    """Nhật ký hệ thống mức ERROR, tương đương `GET /system-logs?log_level=ERROR`;
    lọc theo khoảng thời gian và module. Yêu cầu Administrator."""
    logger.info(
        "Error logs requested by admin=%s page=%d page_size=%d "
        "start=%s end=%s module=%s",
        current_user.username,
        page,
        page_size,
        start_date,
        end_date,
        module_name,
    )
    service = AuditLogService(db)
    total, items = service.get_error_logs(
        start_date=start_date,
        end_date=end_date,
        module_name=module_name,
        page=page,
        page_size=page_size,
    )
    return SystemLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[SystemLogResponse.model_validate(item) for item in items],
    )


@router.get("/system-logs", response_model=SystemLogListResponse)
def list_system_logs(
    start_date: Optional[datetime] = Query(
        None, description="Filter entries created on or after this datetime (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter entries created on or before this datetime (ISO 8601)"
    ),
    log_level: Optional[str] = Query(
        None,
        description="Filter by log level: ERROR, WARNING, INFO",
        pattern="^(ERROR|WARNING|INFO)$",
    ),
    module_name: Optional[str] = Query(
        None, description="Filter by module name (partial, case-insensitive match)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=200, description="Items per page (default 50)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> SystemLogListResponse:
    """Nhật ký hệ thống có phân trang, lọc theo khoảng thời gian, mức
    (ERROR / WARNING / INFO) và module. Yêu cầu Administrator."""
    logger.info(
        "System logs requested by admin=%s page=%d page_size=%d "
        "start=%s end=%s level=%s module=%s",
        current_user.username,
        page,
        page_size,
        start_date,
        end_date,
        log_level,
        module_name,
    )
    service = AuditLogService(db)
    total, items = service.get_system_logs(
        start_date=start_date,
        end_date=end_date,
        log_level=log_level,
        module_name=module_name,
        page=page,
        page_size=page_size,
    )
    return SystemLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[SystemLogResponse.model_validate(item) for item in items],
    )


# ── Dọn nhật ký ──

@router.post("/system-logs/cleanup", status_code=200)
def trigger_log_cleanup(
    background_tasks: BackgroundTasks,
    retention_days: int = Query(
        90, ge=1, le=365, description="Delete logs older than this many days (default 90)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Xoá nhật ký kiểm toán và nhật ký hệ thống cũ hơn `retention_days` ngày
    (mặc định 90). Chạy nền nên phản hồi trả ngay; yêu cầu Administrator."""
    logger.info(
        "Log cleanup triggered by admin=%s retention_days=%d",
        current_user.username,
        retention_days,
    )

    def _run_cleanup() -> None:
        service = AuditLogService(db)
        result = service.delete_old_logs(retention_days=retention_days)
        logger.info("Log cleanup result: %s", result)

    background_tasks.add_task(_run_cleanup)

    return {
        "message": "Log retention cleanup scheduled",
        "retention_days": retention_days,
        "note": "Deletion runs as a background task; check server logs for results.",
    }
