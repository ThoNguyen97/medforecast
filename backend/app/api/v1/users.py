"""User management API endpoints."""
import logging
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.schemas.base import UserCreate, UserUpdate, UserResponse, PaginatedResponse
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
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
    """
    Create a new user.
    
    Only administrators can create users.
    """
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
    """
    List all users.
    
    Only administrators can list users.
    """
    user_service = UserService(db)
    users = user_service.get_users(skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get user by ID.
    
    Users can view their own profile or administrators can view any user.
    """
    user_service = UserService(db)
    
    # Allow users to view their own profile or admins to view any profile
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
    """
    Update user information.
    
    Users can update their own profile (except role).
    Administrators can update any user including role.
    """
    user_service = UserService(db)
    client_ip = get_client_ip(request)
    
    # Check permissions
    if current_user.role != "Administrator" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this user"
        )
    
    # Non-admin users cannot change role or is_active status
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
    """
    Delete user (soft delete).
    
    Only administrators can delete users.
    Users cannot delete themselves.
    """
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