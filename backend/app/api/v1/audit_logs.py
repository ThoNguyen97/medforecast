"""
Audit & Logs API endpoints.

All endpoints are restricted to Administrator users (Requirement 10, 12.5).

Routes
------
GET  /api/v1/audit-logs              – Paginated audit log entries (Admin only)
GET  /api/v1/system-logs             – Paginated system log entries (Admin only)
GET  /api/v1/system-logs/errors      – Shortcut: ERROR-level logs only (Admin only)
POST /api/v1/system-logs/cleanup     – Manually trigger log retention cleanup (Admin only)
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


# ── Audit Logs ─────────────────────────────────────────────────────────────────

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
    """
    Return a paginated list of audit log entries.

    Shows all data modification events logged by the system (creates, updates,
    deletes across all modules).  Supports filtering by date range, user, action
    type, and affected table.

    **Requires Administrator role.**
    """
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


# ── System Logs ────────────────────────────────────────────────────────────────

# NOTE: The /errors fixed-path route MUST be declared before the generic
# /system-logs route is registered in main.py.  Because both are on the same
# router prefix, FastAPI sees the exact path "/system-logs/errors" before it
# could match a wildcard, so declaration order in this file is fine.

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
    """
    Return a paginated list of ERROR-level system log entries.

    Convenience shortcut equivalent to `GET /system-logs?log_level=ERROR`.
    Supports filtering by date range and module name.

    **Requires Administrator role.**
    """
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
    """
    Return a paginated list of system log entries.

    Shows errors, warnings, and informational messages recorded by the system.
    Supports filtering by date range, log level (ERROR / WARNING / INFO), and
    module name.

    **Requires Administrator role.**
    """
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


# ── Log Retention Cleanup ──────────────────────────────────────────────────────

@router.post("/system-logs/cleanup", status_code=200)
def trigger_log_cleanup(
    background_tasks: BackgroundTasks,
    retention_days: int = Query(
        90, ge=1, le=365, description="Delete logs older than this many days (default 90)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> dict:
    """
    Manually trigger the log retention cleanup.

    Deletes audit log and system log entries older than *retention_days* days
    (default: 90 days, per Requirement 12.4).

    The deletion runs as a **background task** so the response is returned
    immediately.  Check server logs for the completion message.

    **Requires Administrator role.**
    """
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
