"""Admin catalog endpoints — manage disease list, region list, safety rate.

Lưu danh mục dưới dạng JSON trong bảng ``system_config`` để không phải migrate
schema khi mở rộng. Endpoint chỉ dành cho Administrator.

Routes
------
GET    /api/v1/admin/diseases               – Lấy danh sách bệnh (admin)
POST   /api/v1/admin/diseases               – Thêm bệnh
PUT    /api/v1/admin/diseases/{key}         – Cập nhật bệnh
DELETE /api/v1/admin/diseases/{key}         – Xoá bệnh

GET    /api/v1/admin/regions                – Lấy danh sách khu vực
POST   /api/v1/admin/regions                – Thêm khu vực
DELETE /api/v1/admin/regions/{name}         – Xoá khu vực

GET    /api/v1/admin/safety-rate            – Lấy hệ số dự phòng (%)
PUT    /api/v1/admin/safety-rate            – Cập nhật hệ số dự phòng
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.system_config import SystemConfig
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-catalog"])

# Config keys
DISEASES_KEY = "admin.diseases"
REGIONS_KEY = "admin.regions"
SAFETY_RATE_KEY = "admin.safety_rate"

# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_or_init(db: Session, key: str, default: str) -> SystemConfig:
    cfg = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if cfg:
        return cfg
    cfg = SystemConfig(config_key=key, config_value=default, description=f"Auto-created {key}")
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _parse_list(cfg: SystemConfig) -> List[Dict[str, Any]]:
    try:
        data = json.loads(cfg.config_value or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_list(db: Session, cfg: SystemConfig, items: List[Dict[str, Any]], user_id: int) -> None:
    cfg.config_value = json.dumps(items, ensure_ascii=False)
    cfg.updated_by = user_id
    db.commit()


# ── Diseases ────────────────────────────────────────────────────────────────


class DiseaseItem(BaseModel):
    key: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None


@router.get("/diseases", response_model=List[DiseaseItem])
def list_diseases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DiseaseItem]:
    cfg = _get_or_init(db, DISEASES_KEY, default=json.dumps(_seed_diseases()))
    return [DiseaseItem(**d) for d in _parse_list(cfg)]


@router.post("/diseases", response_model=DiseaseItem, status_code=status.HTTP_201_CREATED)
def create_disease(
    payload: DiseaseItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DiseaseItem:
    cfg = _get_or_init(db, DISEASES_KEY, default=json.dumps(_seed_diseases()))
    items = _parse_list(cfg)
    if any(d["key"] == payload.key for d in items):
        raise HTTPException(status_code=409, detail=f"Bệnh với key '{payload.key}' đã tồn tại.")
    items.append(payload.model_dump())
    _save_list(db, cfg, items, current_user.id)
    return payload


@router.put("/diseases/{key}", response_model=DiseaseItem)
def update_disease(
    key: str,
    payload: DiseaseItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DiseaseItem:
    cfg = _get_or_init(db, DISEASES_KEY, default=json.dumps(_seed_diseases()))
    items = _parse_list(cfg)
    found = next((d for d in items if d["key"] == key), None)
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy bệnh")
    found.update(payload.model_dump())
    _save_list(db, cfg, items, current_user.id)
    return DiseaseItem(**found)


@router.delete("/diseases/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disease(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> None:
    cfg = _get_or_init(db, DISEASES_KEY, default=json.dumps(_seed_diseases()))
    items = _parse_list(cfg)
    new_items = [d for d in items if d["key"] != key]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Không tìm thấy bệnh")
    _save_list(db, cfg, new_items, current_user.id)


def _seed_diseases() -> List[Dict[str, Any]]:
    # 4 bệnh hô hấp dùng cho dự báo (theo mã ICD)
    return [
        {"key": "J20", "label": "Viêm phế quản cấp", "description": "Acute bronchitis"},
        {"key": "J06", "label": "Nhiễm trùng đường hô hấp trên cấp", "description": "Acute upper respiratory infection"},
        {"key": "J02", "label": "Viêm họng cấp", "description": "Acute pharyngitis"},
        {"key": "J01", "label": "Viêm xoang cấp", "description": "Acute sinusitis"},
    ]


# ── Regions ─────────────────────────────────────────────────────────────────


class RegionItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    province: Optional[str] = None
    description: Optional[str] = None


@router.get("/regions", response_model=List[RegionItem])
def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[RegionItem]:
    cfg = _get_or_init(db, REGIONS_KEY, default=json.dumps(_seed_regions()))
    return [RegionItem(**r) for r in _parse_list(cfg)]


@router.post("/regions", response_model=RegionItem, status_code=status.HTTP_201_CREATED)
def create_region(
    payload: RegionItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> RegionItem:
    cfg = _get_or_init(db, REGIONS_KEY, default=json.dumps(_seed_regions()))
    items = _parse_list(cfg)
    if any(r["name"] == payload.name for r in items):
        raise HTTPException(status_code=409, detail="Khu vực đã tồn tại")
    items.append(payload.model_dump())
    _save_list(db, cfg, items, current_user.id)
    return payload


@router.delete("/regions/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_region(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> None:
    cfg = _get_or_init(db, REGIONS_KEY, default=json.dumps(_seed_regions()))
    items = _parse_list(cfg)
    new_items = [r for r in items if r["name"] != name]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Không tìm thấy khu vực")
    _save_list(db, cfg, new_items, current_user.id)


def _seed_regions() -> List[Dict[str, Any]]:
    return [
        {"name": "Toàn thành phố", "province": "TP. Hồ Chí Minh", "description": ""},
        {"name": "Quận 1", "province": "TP. Hồ Chí Minh", "description": ""},
        {"name": "Quận 7", "province": "TP. Hồ Chí Minh", "description": ""},
        {"name": "Thành phố Thủ Đức", "province": "TP. Hồ Chí Minh", "description": ""},
    ]


# ── Safety rate ─────────────────────────────────────────────────────────────


class SafetyRatePayload(BaseModel):
    safety_rate: float = Field(..., ge=0, le=1.0, description="Tỷ lệ dự phòng 0..1 (vd 0.15 = 15%)")


@router.get("/safety-rate")
def get_safety_rate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, float]:
    cfg = _get_or_init(db, SAFETY_RATE_KEY, default="0.15")
    try:
        rate = float(cfg.config_value)
    except (TypeError, ValueError):
        rate = 0.15
    return {"safety_rate": rate}


@router.put("/safety-rate")
def update_safety_rate(
    payload: SafetyRatePayload = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> Dict[str, float]:
    cfg = _get_or_init(db, SAFETY_RATE_KEY, default="0.15")
    cfg.config_value = str(payload.safety_rate)
    cfg.updated_by = current_user.id
    db.commit()
    return {"safety_rate": payload.safety_rate}
