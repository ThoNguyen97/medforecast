"""API đồng bộ dữ liệu từ HIS (dùng cho nút 'Đồng bộ' trên dashboard).

  POST /api/v1/sync/run       -> chạy đồng bộ (khám bệnh + tồn kho), trả tóm tắt
  GET  /api/v1/sync/status    -> trạng thái lần gần nhất + số liệu hiện có
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_inventory_manager_or_admin
from app.models.user import User
from app.services.sync_service import SyncService

router = APIRouter()


@router.post("/run")
def run_sync(full: bool = Query(False, description="True = nạp lại toàn bộ"),
             db: Session = Depends(get_db),
             _user: User = Depends(get_inventory_manager_or_admin)):
    try:
        return SyncService(db).run_sync(full=full)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Đồng bộ thất bại: {e}")


@router.get("/status")
def sync_status(db: Session = Depends(get_db),
                _user: User = Depends(get_current_user)):
    return SyncService(db).get_status()
