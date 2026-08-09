"""
Audit & System Log Service.

Provides read access to audit_logs and system_logs tables with filtering,
pagination, and a log-retention cleanup utility that removes entries older
than 90 days.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.system_log import SystemLog
from app.models.user import User

logger = logging.getLogger(__name__)

# Log retention period in days (Requirement 12.4)
LOG_RETENTION_DAYS = 90
# Default page size
DEFAULT_PAGE_SIZE = 50


class AuditLogService:
    """Service for querying and maintaining audit and system logs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Audit Logs ────────────────────────────────────────────────────────────

    def get_audit_logs(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        table_name: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[int, list]:
        """
        Return a paginated, filtered list of audit log entries.

        Returns a (total_count, items) tuple so the caller can build a
        PaginatedResponse without a second query.
        """
        query = self.db.query(AuditLog)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        if user_id is not None:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            # Case-insensitive partial match
            query = query.filter(AuditLog.action.ilike(f"%{action}%"))
        if table_name:
            query = query.filter(AuditLog.table_name.ilike(f"%{table_name}%"))

        total = query.count()

        offset = (page - 1) * page_size
        items = (
            query.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return total, items

    def _enrich_audit_log(self, log: AuditLog) -> dict:
        """Add username to an audit log dict for response enrichment."""
        username: Optional[str] = None
        if log.user_id is not None:
            user = self.db.query(User).filter(User.id == log.user_id).first()
            username = user.username if user else None

        return {
            "id": log.id,
            "user_id": log.user_id,
            "username": username,
            "action": log.action,
            "table_name": log.table_name,
            "record_id": log.record_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }

    # ── System Logs ───────────────────────────────────────────────────────────

    def get_system_logs(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        log_level: Optional[str] = None,
        module_name: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[int, list]:
        """
        Return a paginated, filtered list of system log entries.

        Returns a (total_count, items) tuple.
        """
        query = self.db.query(SystemLog)

        if start_date:
            query = query.filter(SystemLog.created_at >= start_date)
        if end_date:
            query = query.filter(SystemLog.created_at <= end_date)
        if log_level:
            query = query.filter(SystemLog.log_level == log_level.upper())
        if module_name:
            query = query.filter(SystemLog.module_name.ilike(f"%{module_name}%"))

        total = query.count()

        offset = (page - 1) * page_size
        items = (
            query.order_by(SystemLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return total, items

    def get_error_logs(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        module_name: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[int, list]:
        """
        Shortcut that returns only ERROR-level system log entries.
        """
        return self.get_system_logs(
            start_date=start_date,
            end_date=end_date,
            log_level="ERROR",
            module_name=module_name,
            page=page,
            page_size=page_size,
        )

    # ── Retention Cleanup ─────────────────────────────────────────────────────

    def delete_old_logs(self, retention_days: int = LOG_RETENTION_DAYS) -> dict:
        """
        Delete audit and system log entries older than *retention_days* days.

        This implements Requirement 12.4: logs older than 90 days are
        automatically deleted.

        Returns a dict with the number of deleted rows for each table so the
        caller can log or surface the result.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        audit_deleted = (
            self.db.query(AuditLog)
            .filter(AuditLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )

        system_deleted = (
            self.db.query(SystemLog)
            .filter(SystemLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )

        self.db.commit()

        result = {
            "audit_logs_deleted": audit_deleted,
            "system_logs_deleted": system_deleted,
            "cutoff_date": cutoff.isoformat(),
            "retention_days": retention_days,
        }
        logger.info(
            "Log retention cleanup completed: "
            "audit_logs_deleted=%d system_logs_deleted=%d cutoff=%s",
            audit_deleted,
            system_deleted,
            cutoff.isoformat(),
        )
        return result
