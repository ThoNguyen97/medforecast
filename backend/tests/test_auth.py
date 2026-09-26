"""Test các endpoint xác thực."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base
from app.models.user import User
from app.core.security import hash_password

# CSDL test dạng file
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Thay dependency CSDL bằng CSDL test."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def test_user():
    """Tạo người dùng test."""
    db = TestingSessionLocal()
    
    # Xoá người dùng test còn sót từ lần chạy trước
    existing_user = db.query(User).filter(User.username == "testuser").first()
    if existing_user:
        db.delete(existing_user)
        db.commit()
    
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Test User",
        role="Administrator",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_login_success(test_user):
    """Đăng nhập thành công."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_username():
    """Đăng nhập với tên người dùng không tồn tại."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "testpass123"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_invalid_password(test_user):
    """Đăng nhập với mật khẩu sai."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_get_current_user(test_user):
    """Lấy thông tin người dùng hiện tại."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["role"] == "Administrator"


def test_get_current_user_invalid_token():
    """Lấy người dùng hiện tại với token không hợp lệ."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_refresh_token(test_user):
    """Làm mới token."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["refresh_token"]      # /refresh nhận refresh token
    
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Token mới có thể trùng token cũ nếu sinh trong cùng giây
    assert len(data["access_token"]) > 0


def test_logout(test_user):
    """Đăng xuất."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


def test_protected_endpoint_without_token():
    """Gọi endpoint được bảo vệ khi không có token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401  # thiếu header Authorization


def test_inactive_user():
    """Đăng nhập bằng tài khoản bị khoá."""
    db = TestingSessionLocal()
    
    inactive_user = User(
        username="inactive",
        email="inactive@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Inactive User",
        role="Administrator",
        is_active=False
    )
    db.add(inactive_user)
    db.commit()
    
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "testpass123"}
    )
    assert response.status_code == 400
    assert "Inactive user" in response.json()["detail"]
    
    # Dọn dữ liệu test
    db.delete(inactive_user)
    db.commit()
    db.close()