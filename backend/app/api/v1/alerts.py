"""
Alerts API endpoints.

Provides CRUD-like access to supply shortage alerts and exposes a
manual resolve action.  Critical and high-severity alerts trigger
email notifications to Administrator users.

Routes
------
GET  /api/v1/alerts               – List all alerts (with optional filters)
GET  /api/v1/alerts/active        – List only unresolved alerts
GET  /api/v1/alerts/critical      – List critical (unresolved) alerts
GET  /api/v1/alerts/{id}          – Get a single alert by ID
PUT  /api/v1/alerts/{id}/resolve  – Manually mark an alert as resolved
POST /api/v1/alerts/check         – Run alert detection scan and send notifications
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.alert import Alert
from app.models.user import User
from app.schemas.base import AlertResponse
from app.services.alert_service import AlertModule
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich_response(alert: Alert) -> dict:
    """
    Add supply_name to the alert dict so the AlertResponse schema can be
    populated without a separate JOIN.  The alert.supply relationship is
    eagerly loaded by AlertModule query helpers.
    """
    data = {
        "id": alert.id,
        "supply_id": alert.supply_id,
        "supply_name": alert.supply.name if alert.supply else None,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "current_stock": alert.current_stock,
        "required_stock": alert.required_stock,
        "shortage_date": alert.shortage_date,
        "message": alert.message,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }
    return data


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/active", response_model=List[AlertResponse])
async def get_active_alerts(
    severity: Optional[str] = Query(
        None,
        description="Filter by severity: critical, high, medium",
        pattern="^(critical|high|medium)$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertResponse]:
    """
    Return all **unresolved** alerts, optionally filtered by severity.

    Active alerts are those where `is_resolved = false`.
    Results are ordered by creation date (newest first).
    """
    logger.info(
        f"Active alerts requested by user={current_user.username} severity={severity}"
    )
    module = AlertModule(db)
    alerts = module.get_active_alerts(severity=severity)
    return [AlertResponse(**_enrich_response(a)) for a in alerts]


@router.get("/critical", response_model=List[AlertResponse])
async def get_critical_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertResponse]:
    """
    Return all unresolved **critical** alerts.

    Convenience shortcut for `GET /alerts/active?severity=critical`.
    Critical alerts indicate projected stock-out within 3 days.
    """
    logger.info(f"Critical alerts requested by user={current_user.username}")
    module = AlertModule(db)
    alerts = module.get_active_alerts(severity="critical")
    return [AlertResponse(**_enrich_response(a)) for a in alerts]


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    severity: Optional[str] = Query(
        None,
        description="Filter by severity: critical, high, medium",
        pattern="^(critical|high|medium)$",
    ),
    is_resolved: Optional[bool] = Query(
        None,
        description="Filter by resolution status (true/false)",
    ),
    supply_id: Optional[int] = Query(
        None,
        description="Filter by supply ID",
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertResponse]:
    """
    List all alerts with optional filters.

    Supports filtering by `severity`, `is_resolved` status, and `supply_id`.
    Results are paginated via `limit` / `offset` parameters.
    """
    logger.info(
        f"Listing alerts requested by user={current_user.username} "
        f"severity={severity} is_resolved={is_resolved} supply_id={supply_id} "
        f"limit={limit} offset={offset}"
    )
    module = AlertModule(db)
    alerts = module.get_all_alerts(
        severity=severity,
        is_resolved=is_resolved,
        supply_id=supply_id,
        limit=limit,
        offset=offset,
    )
    return [AlertResponse(**_enrich_response(a)) for a in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert_by_id(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """
    Retrieve a single alert by its ID.

    Returns 404 if the alert does not exist.
    """
    logger.info(
        f"Alert {alert_id} detail requested by user={current_user.username}"
    )
    module = AlertModule(db)
    alert = module.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )
    return AlertResponse(**_enrich_response(alert))


@router.put("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """
    Manually mark an alert as resolved.

    Sets `is_resolved = true` and records `resolved_at` timestamp.
    Returns 404 if the alert does not exist.
    Idempotent: resolving an already-resolved alert is a no-op.
    """
    logger.info(
        f"Resolve alert {alert_id} requested by user={current_user.username}"
    )
    module = AlertModule(db)
    alert = module.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )
    return AlertResponse(**_enrich_response(alert))


@router.post("/{alert_id}/fulfill", response_model=AlertResponse)
async def fulfill_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """
    "Nhập vào tồn kho" cho một cảnh báo cụ thể.

    Cộng số thiếu hụt (``required_stock - current_stock``) vào inventory của
    vật tư tương ứng rồi đánh dấu cảnh báo đã xử lý.
    """
    from datetime import datetime, timezone
    from app.models.inventory import Inventory as InventoryModel

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )

    if alert.is_resolved:
        # Đã xử lý rồi, trả về luôn
        return AlertResponse(**_enrich_response(alert))

    shortage = max(0, int(alert.required_stock or 0) - int(alert.current_stock or 0))
    if shortage > 0 and alert.supply_id:
        inv = (
            db.query(InventoryModel)
            .filter(InventoryModel.supply_id == alert.supply_id)
            .first()
        )
        if inv:
            inv.current_stock = (inv.current_stock or 0) + shortage
        else:
            db.add(
                InventoryModel(
                    supply_id=alert.supply_id,
                    current_stock=shortage,
                    safety_stock=int(shortage * 0.2),
                )
            )

    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    alert.current_stock = int(alert.current_stock or 0) + shortage

    try:
        db.commit()
        db.refresh(alert)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to fulfill alert {alert_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể nhập vào tồn kho",
        )

    logger.info(
        f"Alert {alert_id} fulfilled by user={current_user.username} "
        f"(supply_id={alert.supply_id}, shortage={shortage})"
    )
    return AlertResponse(**_enrich_response(alert))


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_and_generate_alerts(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Trigger a full alert detection scan over all current supply requirements.

    Compares supply requirements against current inventory levels, generates
    or updates shortage alerts, and sends email notifications for **critical**
    and **high** severity alerts to Administrator users.

    This endpoint is idempotent: existing alerts are updated in place rather
    than duplicated.

    Returns a summary with the count of alerts generated and notifications sent.
    """
    logger.info(f"Alert check triggered by user={current_user.username}")

    module = AlertModule(db)
    try:
        generated_alerts = module.check_and_generate_alerts()
    except Exception as exc:
        logger.error(f"Alert generation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run alert detection scan",
        )

    # Collect alerts that need notifications (critical or high severity)
    alerts_to_notify = [a for a in generated_alerts if a.severity in ("critical", "high")]

    async def _send_notifications_bg() -> None:
        """Send email notifications for critical/high alerts (runs as background task)."""
        notification_service = NotificationService(db)
        sent = 0
        for alert in alerts_to_notify:
            try:
                success = await notification_service.notify_alert(alert)
                if success:
                    sent += 1
            except Exception as exc:
                logger.error(f"Notification failed for alert id={alert.id}: {exc}")
        logger.info(f"Background notifications sent: {sent}/{len(alerts_to_notify)}")

    background_tasks.add_task(_send_notifications_bg)

    return {
        "message": "Alert check completed",
        "alerts_generated": len(generated_alerts),
        "critical_alerts": sum(1 for a in generated_alerts if a.severity == "critical"),
        "high_alerts": sum(1 for a in generated_alerts if a.severity == "high"),
        "medium_alerts": sum(1 for a in generated_alerts if a.severity == "medium"),
    }


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_orphan_alerts(
    all: bool = Query(False, description="If true, resolve every open alert"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Resolve open alerts in bulk.

    By default only resolves alerts whose supply has no inventory record
    (orphan/ma alerts). Pass ``?all=true`` to resolve every open alert
    regardless of inventory state.
    """
    from datetime import datetime, timezone
    from app.models.inventory import Inventory

    logger.info(
        f"Cleanup alerts requested by user={current_user.username} all={all}"
    )

    open_alerts = (
        db.query(Alert).filter(Alert.is_resolved == False).all()  # noqa: E712
    )
    now = datetime.now(timezone.utc)

    if all:
        cleaned = 0
        for alert in open_alerts:
            alert.is_resolved = True
            alert.resolved_at = now
            cleaned += 1
        db.commit()
        return {
            "message": "All open alerts resolved",
            "alerts_cleaned": cleaned,
        }

    # Default: only resolve alerts whose supply has no inventory row
    tracked_ids = {
        row[0] for row in db.query(Inventory.supply_id).distinct().all()
    }
    cleaned = 0
    for alert in open_alerts:
        if alert.supply_id not in tracked_ids:
            alert.is_resolved = True
            alert.resolved_at = now
            cleaned += 1

    db.commit()
    return {
        "message": "Cleanup complete",
        "alerts_cleaned": cleaned,
        "tracked_supplies": len(tracked_ids),
    }
