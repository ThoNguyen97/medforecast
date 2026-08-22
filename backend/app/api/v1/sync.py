"""API đồng bộ dữ liệu từ HIS (dùng cho nút 'Đồng bộ' trên dashboard).

  POST /api/v1/sync/run          -> chạy đồng bộ (khám bệnh + tồn kho), trả tóm tắt
  GET  /api/v1/sync/status       -> trạng thái lần gần nhất + số liệu hiện có
  GET  /api/v1/sync/config       -> cấu hình kết nối (KHÔNG kèm mật khẩu)
  PUT  /api/v1/sync/config       -> lưu cấu hình (chỉ Administrator)
  POST /api/v1/sync/config/test  -> thử kết nối với cấu hình vừa nhập, CHƯA lưu
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (get_admin_user, get_current_user,
                              get_inventory_manager_or_admin)
from app.models.user import User
from app.services import sync_config_service
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


# ── Cấu hình kết nối — sửa từ giao diện, không phải xuống code ───────────────
class SyncConfigIn(BaseModel):
    """Mật khẩu là tuỳ chọn: bỏ trống khi lưu = GIỮ mật khẩu cũ."""
    source: str = Field("file", pattern="^(file|sqlserver)$")
    host: str = ""
    port: int = 1433
    instance: str = ""            # instance có tên (MÁY\\STA) — đặt thì bỏ qua port
    database: str = "MEDFORECAST_DW"
    username: str = ""
    password: Optional[str] = None
    driver: str = "ODBC Driver 18 for SQL Server"
    trust_cert: bool = True
    sql_profile: str = Field("sta", pattern="^(sta|mssql)$")
    lookback_months: int = Field(3, ge=0, le=24)


@router.get("/config")
def get_sync_config(db: Session = Depends(get_db),
                    _user: User = Depends(get_admin_user)):
    """Trả cấu hình hiện tại. Mật khẩu không bao giờ rời server —
    chỉ trả `has_password` để giao diện biết đã đặt hay chưa."""
    return sync_config_service.get_config(db)


@router.put("/config")
def save_sync_config(payload: SyncConfigIn,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_admin_user)):
    """Lưu vào bảng system_config. Lần đồng bộ sau tự dùng cấu hình mới,
    không cần khởi động lại backend."""
    return sync_config_service.save_config(db, payload.model_dump(), user.id)


@router.post("/config/test")
def test_sync_config(payload: SyncConfigIn,
                     db: Session = Depends(get_db),
                     _user: User = Depends(get_admin_user)):
    """Thử kết nối bằng cấu hình VỪA NHẬP (chưa lưu). Trả từng bước
    kiểm tra để giao diện chỉ đúng chỗ hỏng."""
    if payload.source != "sqlserver":
        return {"ok": True, "steps": [{
            "name": "Nguồn file", "ok": True,
            "detail": "Nguồn 'file' đọc CSV nội bộ — không có gì để thử."}]}
    return sync_config_service.test_connection(db, payload.model_dump())
