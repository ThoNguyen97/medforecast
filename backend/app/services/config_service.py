"""Configuration service layer."""
import json
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.system_config import SystemConfig
from app.schemas.base import SystemConfigUpdate

logger = logging.getLogger(__name__)

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

    # 12/09/2026: get/update_conversion_ratios và get/update_thresholds (3/7/14
    # ngày) đã gỡ — không service nào đọc chúng; ngưỡng thật là `dss.thresholds`
    # (Đỏ ≤ 18 / Vàng ≤ 36 ngày DOI), sửa qua /api/v1/dss/params.
