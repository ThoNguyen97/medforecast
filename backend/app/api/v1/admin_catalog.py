"""Danh mục quản trị: bệnh, nhóm bệnh, khu vực — lưu JSON trong system_config.

Đọc: mọi người dùng đã đăng nhập; ghi: Administrator. GET không ghi DB.
`admin.safety_rate` (hệ số dự phòng) gỡ 13/09/2026: không service nào đọc,
núm vặn DSS chỉ nằm ở /dss/params.

Routes
------
GET    /api/v1/admin/diseases               – Lấy danh sách bệnh (admin)
POST   /api/v1/admin/diseases               – Thêm bệnh
PUT    /api/v1/admin/diseases/{key}         – Cập nhật bệnh
DELETE /api/v1/admin/diseases/{key}         – Xoá bệnh

GET    /api/v1/admin/disease-groups         – Lấy danh sách nhóm bệnh (admin)
POST   /api/v1/admin/disease-groups         – Thêm nhóm bệnh
PUT    /api/v1/admin/disease-groups/{key}   – Cập nhật nhóm bệnh (tên, danh sách mã bệnh)
DELETE /api/v1/admin/disease-groups/{key}   – Xoá nhóm bệnh

GET    /api/v1/admin/regions                – Lấy danh sách khu vực
POST   /api/v1/admin/regions                – Thêm khu vực
DELETE /api/v1/admin/regions/{name}         – Xoá khu vực

Lưu ý về "Danh mục nhóm bệnh" (admin.disease_groups): đây là danh mục THAM
KHẢO/hiển thị (giống admin.diseases) — sửa ở đây KHÔNG tự động đổi 3 nhóm ICD
mà mô hình dự báo đang dùng thật (NHOM_ICD cố định trong app/utils/icd_groups.py,
đã được backtest trên dữ liệu thật). Muốn đổi phạm vi nhóm dự báo phải sửa
icd_groups.py và huấn luyện/backtest lại — không nên chỉ đổi ở danh mục này.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.system_config import SystemConfig
from app.models.user import User
from app.utils.icd_groups import NHOM_ICD, ma_thuoc_nhom

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-catalog"])

# Config keys
DISEASES_KEY = "admin.diseases"
DISEASE_GROUPS_KEY = "admin.disease_groups"
REGIONS_KEY = "admin.regions"

# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_or_init(db: Session, key: str, default: str) -> SystemConfig:
    """Dòng cấu hình theo khoá; chưa có thì trả bản mặc định CHƯA GHI DB.
    Endpoint GET vì thế không có tác dụng phụ; dòng chỉ được persist khi một
    endpoint PUT/POST/DELETE gọi `_save_list` (add + commit)."""
    cfg = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if cfg:
        return cfg
    return SystemConfig(config_key=key, config_value=default,
                        description=f"Danh mục quản trị {key}")


def _parse_list(cfg: SystemConfig) -> List[Dict[str, Any]]:
    try:
        data = json.loads(cfg.config_value or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_list(db: Session, cfg: SystemConfig, items: List[Dict[str, Any]], user_id: int) -> None:
    cfg.config_value = json.dumps(items, ensure_ascii=False)
    if cfg.id is None:
        db.add(cfg)
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
    # 20 mã ICD lẻ thực tế đang có trong dữ liệu ca bệnh (disease_cases),
    # trải trong 3 nhóm đề tài J00-J06 / J09-J18 / J20-J22 — không còn chỉ
    # 4 mã cũ (J20/J06/J02/J01) như bản đầu.
    return [
        {"key": "J00", "label": "Viêm mũi họng cấp tính [cảm thường]", "description": ""},
        {"key": "J01", "label": "Viêm xoang cấp tính", "description": "Acute sinusitis"},
        {"key": "J02", "label": "Viêm họng cấp tính", "description": "Acute pharyngitis"},
        {"key": "J03", "label": "Viêm amydan cấp tính", "description": ""},
        {"key": "J04", "label": "Viêm thanh quản và/hoặc khí quản cấp tính", "description": ""},
        {"key": "J05", "label": "Viêm thanh quản tắc nghẽn cấp tính [croup] và viêm nắp thanh quản", "description": ""},
        {"key": "J06", "label": "Nhiễm trùng đường hô hấp trên cấp tính ở nhiều vị trí và/hoặc vị trí không xác định", "description": "Acute upper respiratory infection"},
        {"key": "J09", "label": "Cúm do virus cúm động vật hoặc đại dịch đã xác định", "description": ""},
        {"key": "J10", "label": "Cảm cúm do virus cúm mùa đã xác định", "description": ""},
        {"key": "J11", "label": "Cúm, virus không được định danh", "description": ""},
        {"key": "J12", "label": "Viêm phổi do virus, không phân loại mục khác", "description": ""},
        {"key": "J13", "label": "Viêm phổi do vi khuẩn phế cầu khuẩn [Streptococcus pneumoniae]", "description": ""},
        {"key": "J14", "label": "Viêm phổi do Haemophilus influenzae", "description": ""},
        {"key": "J15", "label": "Viêm phổi do vi khuẩn, không phân loại mục khác", "description": ""},
        {"key": "J16", "label": "Viêm phổi do vi sinh vật truyền nhiễm khác, không phân loại mục khác", "description": ""},
        {"key": "J17", "label": "Viêm phổi do nhiễm nấm", "description": ""},
        {"key": "J18", "label": "Viêm phổi, tác nhân không xác định", "description": ""},
        {"key": "J20", "label": "Viêm phế quản cấp tính", "description": "Acute bronchitis"},
        {"key": "J21", "label": "Viêm tiểu phế quản cấp tính", "description": ""},
        {"key": "J22", "label": "Nhiễm khuẩn cấp đường hô hấp dưới không xác định", "description": ""},
    ]


# ── Disease groups ──────────────────────────────────────────────────────────


class DiseaseGroupItem(BaseModel):
    key: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    # Danh sách mã bệnh (key trong Danh mục bệnh) thuộc nhóm này.
    icd_codes: List[str] = Field(default_factory=list)


@router.get("/disease-groups", response_model=List[DiseaseGroupItem])
def list_disease_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DiseaseGroupItem]:
    cfg = _get_or_init(db, DISEASE_GROUPS_KEY, default=json.dumps(_seed_disease_groups()))
    return [DiseaseGroupItem(**g) for g in _parse_list(cfg)]


@router.post("/disease-groups", response_model=DiseaseGroupItem, status_code=status.HTTP_201_CREATED)
def create_disease_group(
    payload: DiseaseGroupItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DiseaseGroupItem:
    cfg = _get_or_init(db, DISEASE_GROUPS_KEY, default=json.dumps(_seed_disease_groups()))
    items = _parse_list(cfg)
    if any(g["key"] == payload.key for g in items):
        raise HTTPException(status_code=409, detail=f"Nhóm bệnh với key '{payload.key}' đã tồn tại.")
    items.append(payload.model_dump())
    _save_list(db, cfg, items, current_user.id)
    return payload


@router.put("/disease-groups/{key}", response_model=DiseaseGroupItem)
def update_disease_group(
    key: str,
    payload: DiseaseGroupItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DiseaseGroupItem:
    cfg = _get_or_init(db, DISEASE_GROUPS_KEY, default=json.dumps(_seed_disease_groups()))
    items = _parse_list(cfg)
    found = next((g for g in items if g["key"] == key), None)
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm bệnh")
    found.update(payload.model_dump())
    _save_list(db, cfg, items, current_user.id)
    return DiseaseGroupItem(**found)


@router.delete("/disease-groups/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disease_group(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> None:
    cfg = _get_or_init(db, DISEASE_GROUPS_KEY, default=json.dumps(_seed_disease_groups()))
    items = _parse_list(cfg)
    new_items = [g for g in items if g["key"] != key]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm bệnh")
    _save_list(db, cfg, new_items, current_user.id)


def _seed_disease_groups() -> List[Dict[str, Any]]:
    # Khớp đúng NHOM_ICD thật đang dùng cho dự báo (icd_groups.py) — để danh
    # mục này bắt đầu nhất quán với hệ thống, dù sau đó admin có thể thêm/sửa
    # tự do (chỉ ảnh hưởng danh mục hiển thị, xem lưu ý ở đầu file).
    return [
        {"key": nhom, "name": ten, "icd_codes": ma_thuoc_nhom(nhom)}
        for nhom, ten in NHOM_ICD.items()
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
