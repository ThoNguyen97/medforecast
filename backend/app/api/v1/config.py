"""
Configuration API endpoints.

Provides access to system-wide configuration, conversion ratios, and
shortage thresholds.  All write operations are restricted to users with
the Administrator role and are recorded in audit_logs.

Routes
------
GET  /api/v1/config                        – List all config entries
GET  /api/v1/config/conversion-ratios      – List all conversion ratios
PUT  /api/v1/config/conversion-ratios      – Update conversion ratios (Admin)
GET  /api/v1/config/thresholds             – Get shortage thresholds
PUT  /api/v1/config/thresholds             – Update shortage thresholds (Admin)
GET  /api/v1/config/{key}                  – Get a single config entry by key
PUT  /api/v1/config/{key}                  – Update a config entry (Admin)

Note: The fixed-path routes (conversion-ratios, thresholds) must be declared
      *before* the parameterised route ({key}) so FastAPI does not interpret
      them as key values.
"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.schemas.base import (
    ConversionRatioResponse,
    ConversionRatiosBulkUpdate,
    SystemConfigResponse,
    SystemConfigUpdate,
    ThresholdConfig,
    ThresholdResponse,
)
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


def _enrich_conversion_ratio(ratio) -> dict:
    """Build a dict suitable for ConversionRatioResponse."""
    return {
        "id": ratio.id,
        "disease_type": ratio.disease_type,
        "supply_id": ratio.supply_id,
        "supply_name": ratio.supply.name if ratio.supply else None,
        "ratio": float(ratio.ratio),
        "unit": ratio.unit,
        "updated_by": ratio.updated_by,
        "updated_at": ratio.updated_at,
    }


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


@router.get("/conversion-ratios", response_model=List[ConversionRatioResponse])
def get_conversion_ratios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Return all disease-to-supply conversion ratios.

    All authenticated users can read conversion ratios.
    """
    logger.info(f"Get conversion ratios requested by user={current_user.username}")
    service = ConfigService(db)
    ratios = service.get_conversion_ratios()
    return [ConversionRatioResponse(**_enrich_conversion_ratio(r)) for r in ratios]


@router.put(
    "/conversion-ratios",
    response_model=List[ConversionRatioResponse],
    status_code=status.HTTP_200_OK,
)
def update_conversion_ratios(
    body: ConversionRatiosBulkUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> Any:
    """
    Update (upsert) one or more conversion ratios.

    Requires Administrator role.
    Changes are recorded in audit_logs with old and new values.
    """
    logger.info(
        f"Update conversion ratios requested by user={current_user.username} "
        f"({len(body.ratios)} item(s))"
    )
    service = ConfigService(db)
    ratios = service.update_conversion_ratios(
        updates=body.ratios,
        updated_by_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
    return [ConversionRatioResponse(**_enrich_conversion_ratio(r)) for r in ratios]


@router.get("/thresholds", response_model=ThresholdResponse)
def get_thresholds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Return shortage threshold configuration.

    Thresholds define the number of days before projected stockout that
    determines the alert severity (critical / high / medium).
    All authenticated users can read thresholds.
    """
    logger.info(f"Get thresholds requested by user={current_user.username}")
    service = ConfigService(db)
    return service.get_thresholds()


@router.put("/thresholds", response_model=ThresholdResponse)
def update_thresholds(
    body: ThresholdConfig,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> Any:
    """
    Update shortage threshold configuration.

    Requires Administrator role.
    Values must satisfy: critical_days < high_days < medium_days.
    Changes are recorded in audit_logs.
    """
    logger.info(
        f"Update thresholds requested by user={current_user.username}: "
        f"critical={body.critical_days}, high={body.high_days}, "
        f"medium={body.medium_days}"
    )
    service = ConfigService(db)
    return service.update_thresholds(
        data=body,
        updated_by_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )


# ── Parameterised key routes (must come AFTER fixed-path routes) ──────────────

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
