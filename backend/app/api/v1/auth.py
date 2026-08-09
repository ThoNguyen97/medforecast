"""Authentication API endpoints."""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.base import Token, LoginResponse, UserLogin, UserResponse

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)) -> Any:
    """
    User login endpoint.
    
    Authenticates user with username/password and returns JWT token.
    """
    # Find user by username
    user = db.query(User).filter(User.username == user_credentials.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create refresh token (same as access token for now, but with longer expiry)
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": user.username, "type": "refresh"}, expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": user
    }


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)) -> Any:
    """
    User logout endpoint.
    
    Note: Since we're using stateless JWT tokens, logout is handled client-side
    by removing the token. This endpoint serves as a confirmation.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> Any:
    """
    Get current user information.
    
    Returns the authenticated user's profile information.
    """
    return current_user


@router.post("/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user)) -> Any:
    """
    Refresh access token.
    
    Issues a new JWT token for the authenticated user.
    """
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }