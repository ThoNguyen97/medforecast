"""Dependency FastAPI: xác thực JWT và phân quyền theo vai trò."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_token
from app.models.user import User

security = HTTPBearer()


def _user_tu_token(token: str, db: Session, loai: str) -> User:
    """Giải mã JWT, kiểm tra loại token ('access' | 'refresh') rồi tra người dùng."""
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if (payload.get("type") or "access") != loai:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không phải loại {loai}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Người dùng hiện tại từ access token."""
    return _user_tu_token(credentials.credentials, db, "access")


def get_user_from_refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Người dùng từ refresh token; chỉ dùng cho POST /auth/refresh."""
    return _user_tu_token(credentials.credentials, db, "refresh")


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Yêu cầu vai trò Administrator."""
    if current_user.role != "Administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_inventory_manager_user(current_user: User = Depends(get_current_user)) -> User:
    """Yêu cầu vai trò Inventory_Manager hoặc Administrator."""
    if current_user.role not in ["Administrator", "Inventory_Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


get_inventory_manager_or_admin = get_inventory_manager_user