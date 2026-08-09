"""Configuration service layer."""
import json
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.conversion_ratio import ConversionRatio
from app.models.medical_supply import MedicalSupply
from app.models.system_config import SystemConfig
from app.schemas.base import (
    ConversionRatioUpdate,
    SystemConfigUpdate,
    ThresholdConfig,
)

logger = logging.getLogger(__name__)

# Keys used in system_config for threshold settings
THRESHOLD_CRITICAL_KEY = "threshold_critical_days"
THRESHOLD_HIGH_KEY = "threshold_high_days"
THRESHOLD_MEDIUM_KEY = "threshold_medium_days"

# Default threshold values (days)
DEFAULT_CRITICAL_DAYS = 3
DEFAULT_HIGH_DAYS = 7
DEFAULT_MEDIUM_DAYS = 14


class ConfigService:
    """Service for managing system configuration."""

    def __init__(self, db: Session):
        self.db = db

    # ── SystemConfig helpers ──────────────────────────────────────────────────

    def get_all_configs(self) -> List[SystemConfig]:
        """Return all system config entries."""
        return self.db.query(SystemConfig).order_by(SystemConfig.config_key).all()

    def get_config_by_key(self, key: str) -> SystemConfig:
        """Return a single config entry by key, raising 404 if absent."""
        cfg = (
            self.db.query(SystemConfig)
            .filter(SystemConfig.config_key == key)
            .first()
        )
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration key '{key}' not found",
            )
        return cfg

    def update_config(
        self,
        key: str,
        data: SystemConfigUpdate,
        updated_by_user_id: int,
        ip_address: str,
    ) -> SystemConfig:
        """Update (or create) a config entry and write an audit log."""
        cfg = (
            self.db.query(SystemConfig)
            .filter(SystemConfig.config_key == key)
            .first()
        )

        old_value: Optional[dict] = None

        if cfg:
            old_value = {
                "config_key": cfg.config_key,
                "config_value": cfg.config_value,
                "description": cfg.description,
            }
            cfg.config_value = data.config_value
            if data.description is not None:
                cfg.description = data.description
            cfg.updated_by = updated_by_user_id
        else:
            cfg = SystemConfig(
                config_key=key,
                config_value=data.config_value,
                description=data.description,
                updated_by=updated_by_user_id,
            )
            self.db.add(cfg)
            self.db.flush()  # populate cfg.id before audit log

        new_value = {
            "config_key": key,
            "config_value": data.config_value,
            "description": data.description,
        }

        audit_log = AuditLog(
            user_id=updated_by_user_id,
            action="UPDATE_CONFIG",
            table_name="system_config",
            record_id=cfg.id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(cfg)

        logger.info(
            f"Config key='{key}' updated by user_id={updated_by_user_id}"
        )
        return cfg

    # ── Conversion Ratios ─────────────────────────────────────────────────────

    def get_conversion_ratios(self) -> List[ConversionRatio]:
        """Return all conversion ratios with supply names eagerly loaded."""
        return (
            self.db.query(ConversionRatio)
            .options(joinedload(ConversionRatio.supply))
            .order_by(ConversionRatio.disease_type, ConversionRatio.supply_id)
            .all()
        )

    def update_conversion_ratios(
        self,
        updates: List[ConversionRatioUpdate],
        updated_by_user_id: int,
        ip_address: str,
    ) -> List[ConversionRatio]:
        """
        Upsert conversion ratios.

        For each item in *updates*, if a row with the same
        (disease_type, supply_id) already exists it is updated;
        otherwise a new row is created.
        All changes are written to audit_logs in a single transaction.
        """
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No conversion ratios provided",
            )

        results: List[ConversionRatio] = []

        for item in updates:
            # Verify that the supply exists
            supply = (
                self.db.query(MedicalSupply)
                .filter(MedicalSupply.id == item.supply_id)
                .first()
            )
            if not supply:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Medical supply with ID {item.supply_id} not found",
                )

            existing = (
                self.db.query(ConversionRatio)
                .filter(
                    ConversionRatio.disease_type == item.disease_type,
                    ConversionRatio.supply_id == item.supply_id,
                )
                .first()
            )

            old_value: Optional[dict] = None
            if existing:
                old_value = {
                    "disease_type": existing.disease_type,
                    "supply_id": existing.supply_id,
                    "ratio": float(existing.ratio),
                    "unit": existing.unit,
                }
                existing.ratio = item.ratio
                existing.unit = item.unit
                existing.updated_by = updated_by_user_id
                ratio_row = existing
            else:
                ratio_row = ConversionRatio(
                    disease_type=item.disease_type,
                    supply_id=item.supply_id,
                    ratio=item.ratio,
                    unit=item.unit,
                    updated_by=updated_by_user_id,
                )
                self.db.add(ratio_row)
                self.db.flush()

            new_value = {
                "disease_type": item.disease_type,
                "supply_id": item.supply_id,
                "ratio": item.ratio,
                "unit": item.unit,
            }
            audit_log = AuditLog(
                user_id=updated_by_user_id,
                action="UPDATE_CONVERSION_RATIO",
                table_name="conversion_ratios",
                record_id=ratio_row.id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
            )
            self.db.add(audit_log)
            results.append(ratio_row)

        self.db.commit()

        # Reload with supply relationship
        refreshed: List[ConversionRatio] = []
        for r in results:
            self.db.refresh(r)
            # Re-load with join so supply_name is available
            full = (
                self.db.query(ConversionRatio)
                .options(joinedload(ConversionRatio.supply))
                .filter(ConversionRatio.id == r.id)
                .first()
            )
            refreshed.append(full)

        logger.info(
            f"{len(refreshed)} conversion ratio(s) updated by user_id={updated_by_user_id}"
        )
        return refreshed

    # ── Thresholds ────────────────────────────────────────────────────────────

    def get_thresholds(self) -> dict:
        """
        Return shortage threshold values as a dict.

        Falls back to the defaults (3 / 7 / 14) when a key is absent.
        """
        keys = [THRESHOLD_CRITICAL_KEY, THRESHOLD_HIGH_KEY, THRESHOLD_MEDIUM_KEY]
        rows = (
            self.db.query(SystemConfig)
            .filter(SystemConfig.config_key.in_(keys))
            .all()
        )
        row_map = {r.config_key: r.config_value for r in rows}

        return {
            "critical_days": int(
                row_map.get(THRESHOLD_CRITICAL_KEY, DEFAULT_CRITICAL_DAYS)
            ),
            "high_days": int(row_map.get(THRESHOLD_HIGH_KEY, DEFAULT_HIGH_DAYS)),
            "medium_days": int(
                row_map.get(THRESHOLD_MEDIUM_KEY, DEFAULT_MEDIUM_DAYS)
            ),
        }

    def update_thresholds(
        self,
        data: ThresholdConfig,
        updated_by_user_id: int,
        ip_address: str,
    ) -> dict:
        """
        Persist shortage threshold values to system_config and audit-log each change.
        """
        # Validate ordering: critical < high < medium
        if not (data.critical_days < data.high_days < data.medium_days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Threshold days must satisfy: "
                    "critical_days < high_days < medium_days"
                ),
            )

        updates_map = {
            THRESHOLD_CRITICAL_KEY: (
                str(data.critical_days),
                "Days until projected shortage for critical severity",
            ),
            THRESHOLD_HIGH_KEY: (
                str(data.high_days),
                "Days until projected shortage for high severity",
            ),
            THRESHOLD_MEDIUM_KEY: (
                str(data.medium_days),
                "Days until projected shortage for medium severity",
            ),
        }

        for key, (value, description) in updates_map.items():
            cfg = (
                self.db.query(SystemConfig)
                .filter(SystemConfig.config_key == key)
                .first()
            )

            old_value: Optional[dict] = None
            if cfg:
                old_value = {"config_key": key, "config_value": cfg.config_value}
                cfg.config_value = value
                cfg.description = description
                cfg.updated_by = updated_by_user_id
            else:
                cfg = SystemConfig(
                    config_key=key,
                    config_value=value,
                    description=description,
                    updated_by=updated_by_user_id,
                )
                self.db.add(cfg)
                self.db.flush()

            audit_log = AuditLog(
                user_id=updated_by_user_id,
                action="UPDATE_THRESHOLD",
                table_name="system_config",
                record_id=cfg.id,
                old_value=old_value,
                new_value={"config_key": key, "config_value": value},
                ip_address=ip_address,
            )
            self.db.add(audit_log)

        self.db.commit()

        logger.info(
            f"Thresholds updated by user_id={updated_by_user_id}: "
            f"critical={data.critical_days}, high={data.high_days}, "
            f"medium={data.medium_days}"
        )
        return {
            "critical_days": data.critical_days,
            "high_days": data.high_days,
            "medium_days": data.medium_days,
        }
