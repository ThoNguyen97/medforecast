"""API quản lý người dùng (tạo, xem, sửa, vô hiệu hoá); thao tác ghi được ghi audit."""
import logging
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.schemas.base import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Lấy IP client, ưu tiên X-Forwarded-For khi chạy sau proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
) -> Any:
    """Tạo người dùng mới (chỉ Administrator)."""
    user_service = UserService(db)
    client_ip = get_client_ip(request)
    
    try:
        new_user = user_service.create_user(
            user_data=user_data,
            created_by_user_id=current_user.id,
            ip_address=client_ip
        )
        return new_user
    except Exception as e:
        logger.error(f"Failed to create user: {str(e)}")
        raise


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
) -> Any:
    """Liệt kê người dùng, phân trang skip/limit (chỉ Administrator)."""
    user_service = UserService(db)
    users = user_service.get_users(skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Xem một người dùng; người dùng thường chỉ xem được hồ sơ của mình."""
    user_service = UserService(db)
    
    if current_user.role != "Administrator" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view this user"
        )
    
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Cập nhật người dùng; người dùng thường chỉ sửa hồ sơ của mình và không đổi
    được vai trò hay trạng thái kích hoạt."""
    user_service = UserService(db)
    client_ip = get_client_ip(request)
    
    if current_user.role != "Administrator" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this user"
        )
    
    if current_user.role != "Administrator":
        if user_data.role is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can change user roles"
            )
        if user_data.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can change user active status"
            )
    
    try:
        updated_user = user_service.update_user(
            user_id=user_id,
            user_data=user_data,
            updated_by_user_id=current_user.id,
            ip_address=client_ip
        )
        return updated_user
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {str(e)}")
        raise


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Xoá mềm người dùng (chỉ Administrator, không tự xoá chính mình)."""
    user_service = UserService(db)
    client_ip = get_client_ip(request)
    
    try:
        user_service.delete_user(
            user_id=user_id,
            deleted_by_user_id=current_user.id,
            ip_address=client_ip
        )
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {str(e)}")
        raise