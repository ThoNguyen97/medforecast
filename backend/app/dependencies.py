"""FastAPI dependencies."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_token
from app.models.user import User

# Security scheme
security = HTTPBearer()


def _user_tu_token(token: str, db: Session, loai: str) -> User:
    """Giải mã JWT, kiểm đúng loại token ('access' | 'refresh') rồi tra user.
    Refresh token (hạn 7 ngày) không được dùng thay access token và ngược lại."""
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
    """Người dùng hiện tại từ ACCESS token."""
    return _user_tu_token(credentials.credentials, db, "access")


def get_user_from_refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Người dùng từ REFRESH token — chỉ dùng cho POST /auth/refresh."""
    return _user_tu_token(credentials.credentials, db, "refresh")


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify admin role."""
    if current_user.role != "Administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_pharmacist_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify pharmacist or admin role."""
    if current_user.role not in ["Administrator", "Pharmacist"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_inventory_manager_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify inventory manager or admin role."""
    if current_user.role not in ["Administrator", "Inventory_Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# Alias for convenience
get_inventory_manager_or_admin = get_inventory_manager_user