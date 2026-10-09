"""API đồng bộ dữ liệu từ HIS và cấu hình kết nối (nút 'Đồng bộ' trên dashboard)."""
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
    except RuntimeError as e:
        # Lỗi cấu hình (chưa khai báo kết nối, thiếu trường) do người dùng sửa được,
        # nên trả 400 để giao diện hiển thị nguyên thông điệp.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Đồng bộ thất bại: {e}")


@router.get("/status")
def sync_status(db: Session = Depends(get_db),
                _user: User = Depends(get_current_user)):
    return SyncService(db).get_status()


class SyncConfigIn(BaseModel):
    """Cấu hình kết nối HIS/DW; bỏ trống mật khẩu khi lưu thì giữ mật khẩu đang có."""
    source: str = Field("sqlserver", pattern="^sqlserver$")
    host: str = "localhost"
    port: int = 1433
    instance: str = ""            # instance có tên (localhost\\SQLEXPRESS): đặt thì bỏ qua port
    database: str = "MEDFORECAST_DW"
    auth: str = Field("windows", pattern="^(windows|sql)$")   # Trusted_Connection | UID/PWD
    username: str = ""
    password: Optional[str] = None
    driver: str = "ODBC Driver 18 for SQL Server"
    trust_cert: bool = True
    sql_profile: str = Field("dw", pattern="^(dw|mssql)$")
    lookback_months: int = Field(3, ge=0, le=24)


@router.get("/config")
def get_sync_config(db: Session = Depends(get_db),
                    _user: User = Depends(get_admin_user)):
    """Cấu hình hiện tại; mật khẩu không trả về, chỉ có `has_password`."""
    return sync_config_service.get_config(db)


@router.put("/config")
def save_sync_config(payload: SyncConfigIn,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_admin_user)):
    """Lưu cấu hình (Admin); lần đồng bộ sau dùng ngay, không cần khởi động lại."""
    return sync_config_service.save_config(db, payload.model_dump(), user.id)


@router.post("/config/test")
def test_sync_config(payload: SyncConfigIn,
                     db: Session = Depends(get_db),
                     _user: User = Depends(get_admin_user)):
    """Thử kết nối bằng cấu hình vừa nhập (chưa lưu), trả kết quả từng bước."""
    return sync_config_service.test_connection(db, payload.model_dump())
