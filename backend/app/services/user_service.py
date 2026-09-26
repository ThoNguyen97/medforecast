"""Nghiệp vụ quản lý người dùng: tạo, cập nhật, vô hiệu hoá kèm audit log."""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.base import UserCreate, UserUpdate
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


class UserService:
    """Quản lý người dùng."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_data: UserCreate, created_by_user_id: int, ip_address: str = None) -> User:
        """Tạo người dùng; HTTP 400 nếu trùng username/email."""
        try:
            password_hash = get_password_hash(user_data.password)
            
            db_user = User(
                username=user_data.username,
                email=user_data.email,
                password_hash=password_hash,
                full_name=user_data.full_name,
                role=user_data.role.value,
                is_active=True
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            self._log_audit(
                user_id=created_by_user_id,
                action="CREATE_USER",
                table_name="users",
                record_id=db_user.id,
                old_value=None,
                new_value={
                    "username": db_user.username,
                    "email": db_user.email,
                    "full_name": db_user.full_name,
                    "role": db_user.role,
                    "is_active": db_user.is_active
                },
                ip_address=ip_address
            )
            
            logger.info(f"User created: {db_user.username} (ID: {db_user.id})")
            return db_user
            
        except IntegrityError as e:
            self.db.rollback()
            if "username" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            elif "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User creation failed due to constraint violation"
                )
    
    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Danh sách người dùng có phân trang."""
        return self.db.query(User).offset(skip).limit(limit).all()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Người dùng theo ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Người dùng theo username."""
        return self.db.query(User).filter(User.username == username).first()
    
    def update_user(self, user_id: int, user_data: UserUpdate, updated_by_user_id: int, ip_address: str = None) -> User:
        """Cập nhật thông tin người dùng; 404 nếu không có, 400 nếu trùng email."""
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        old_values = {
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role,
            "is_active": db_user.is_active
        }
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        try:
            for field, value in update_data.items():
                if field == "role" and value:
                    setattr(db_user, field, value.value)
                else:
                    setattr(db_user, field, value)
            
            self.db.commit()
            self.db.refresh(db_user)
            
            new_values = {
                "email": db_user.email,
                "full_name": db_user.full_name,
                "role": db_user.role,
                "is_active": db_user.is_active
            }
            
            self._log_audit(
                user_id=updated_by_user_id,
                action="UPDATE_USER",
                table_name="users",
                record_id=db_user.id,
                old_value=old_values,
                new_value=new_values,
                ip_address=ip_address
            )
            
            logger.info(f"User updated: {db_user.username} (ID: {db_user.id})")
            return db_user
            
        except IntegrityError as e:
            self.db.rollback()
            if "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User update failed due to constraint violation"
                )
    
    def delete_user(self, user_id: int, deleted_by_user_id: int, ip_address: str = None) -> bool:
        """Xoá mềm người dùng (is_active = False); không cho tự xoá tài khoản của mình."""
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user_id == deleted_by_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        old_values = {
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role,
            "is_active": db_user.is_active
        }
        
        db_user.is_active = False
        self.db.commit()
        
        self._log_audit(
            user_id=deleted_by_user_id,
            action="DELETE_USER",
            table_name="users",
            record_id=db_user.id,
            old_value=old_values,
            new_value={"is_active": False},
            ip_address=ip_address
        )
        
        logger.info(f"User deleted: {db_user.username} (ID: {db_user.id})")
        return True
    
    def _log_audit(self, user_id: int, action: str, table_name: str, record_id: int, 
                   old_value: dict = None, new_value: dict = None, ip_address: str = None):
        """Thêm bản ghi audit log vào session."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address
        )
        
        self.db.add(audit_log)
        # Không commit tại đây; bản ghi chỉ được lưu ở lần commit kế tiếp của session.