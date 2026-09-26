"""Đọc/ghi cấu hình hệ thống (system_config) kèm audit log."""
import json
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.system_config import SystemConfig
from app.schemas.base import SystemConfigUpdate

logger = logging.getLogger(__name__)

class ConfigService:
    """Quản lý cấu hình hệ thống."""

    def __init__(self, db: Session):
        self.db = db

    # ── SystemConfig helpers ──────────────────────────────────────────────────

    def get_all_configs(self) -> List[SystemConfig]:
        """Mọi dòng system_config, mật khẩu HIS đã che."""
        rows = self.db.query(SystemConfig).order_by(SystemConfig.config_key).all()
        return [self._che_mat_khau(r) for r in rows]

    def get_config_by_key(self, key: str) -> SystemConfig:
        """Một dòng theo khoá; 404 nếu không có. Mật khẩu HIS đã che."""
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
        return self._che_mat_khau(cfg)

    def _che_mat_khau(self, cfg: SystemConfig) -> SystemConfig:
        """Bỏ `password_enc` khỏi `his_sync.connection` trước khi trả qua /config.

        Endpoint /config mở cho mọi người dùng đã đăng nhập; bản ghi được expunge khỏi
        session để không ghi đè giá trị gốc. Bản đầy đủ chỉ SyncService đọc.
        """
        if cfg.config_key != "his_sync.connection":
            return cfg
        try:
            d = json.loads(cfg.config_value or "{}")
        except (TypeError, ValueError):
            return cfg
        if "password_enc" not in d:
            return cfg
        d["has_password"] = bool(d.pop("password_enc"))
        self.db.expunge(cfg)
        cfg.config_value = json.dumps(d, ensure_ascii=False)
        return cfg

    def update_config(
        self,
        key: str,
        data: SystemConfigUpdate,
        updated_by_user_id: int,
        ip_address: str,
    ) -> SystemConfig:
        """Cập nhật (hoặc tạo) một khoá cấu hình và ghi audit log."""
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
            self.db.flush()  # cần cfg.id cho audit log

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
