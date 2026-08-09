"""Tests for user management endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.core.security import get_password_hash

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def test_db():
    """Create a fresh database for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Create test admin user
    db = TestingSessionLocal()
    admin_user = User(
        username="admin",
        email="admin@test.com",
        password_hash=get_password_hash("admin123"),
        full_name="Test Admin",
        role="Administrator",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.close()
    
    yield
    
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_token(test_db):
    """Get admin access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    """Get authorization headers."""
    return {"Authorization": f"Bearer {admin_token}"}


def test_create_user(auth_headers):
    """Test creating a new user."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "role": "Pharmacist"
    }
    
    response = client.post("/api/v1/users/", json=user_data, headers=auth_headers)
    
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "Pharmacist"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_user_duplicate_username(auth_headers):
    """Test creating user with duplicate username."""
    user_data = {
        "username": "admin",  # Already exists
        "email": "test2@example.com",
        "password": "testpass123",
        "full_name": "Test User 2",
        "role": "Pharmacist"
    }
    
    response = client.post("/api/v1/users/", json=user_data, headers=auth_headers)
    
    assert response.status_code == 400
    assert "Username already exists" in response.json()["detail"]


def test_list_users(auth_headers):
    """Test listing users."""
    response = client.get("/api/v1/users/", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least the admin user
    
    # Check admin user is in the list
    admin_user = next((user for user in data if user["username"] == "admin"), None)
    assert admin_user is not None
    assert admin_user["role"] == "Administrator"


def test_get_user_by_id(auth_headers):
    """Test getting user by ID."""
    # First create a user
    user_data = {
        "username": "gettest",
        "email": "gettest@example.com",
        "password": "testpass123",
        "full_name": "Get Test User",
        "role": "Inventory_Manager"
    }
    
    create_response = client.post("/api/v1/users/", json=user_data, headers=auth_headers)
    user_id = create_response.json()["id"]
    
    # Get the user
    response = client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "gettest"
    assert data["email"] == "gettest@example.com"
    assert data["role"] == "Inventory_Manager"


def test_get_user_not_found(auth_headers):
    """Test getting non-existent user."""
    response = client.get("/api/v1/users/999", headers=auth_headers)
    
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


def test_update_user(auth_headers):
    """Test updating user."""
    # First create a user
    user_data = {
        "username": "updatetest",
        "email": "updatetest@example.com",
        "password": "testpass123",
        "full_name": "Update Test User",
        "role": "Pharmacist"
    }
    
    create_response = client.post("/api/v1/users/", json=user_data, headers=auth_headers)
    user_id = create_response.json()["id"]
    
    # Update the user
    update_data = {
        "full_name": "Updated Test User",
        "role": "Inventory_Manager"
    }
    
    response = client.put(f"/api/v1/users/{user_id}", json=update_data, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Test User"
    assert data["role"] == "Inventory_Manager"


def test_delete_user(auth_headers):
    """Test deleting user (soft delete)."""
    # First create a user
    user_data = {
        "username": "deletetest",
        "email": "deletetest@example.com",
        "password": "testpass123",
        "full_name": "Delete Test User",
        "role": "Pharmacist"
    }
    
    create_response = client.post("/api/v1/users/", json=user_data, headers=auth_headers)
    user_id = create_response.json()["id"]
    
    # Delete the user
    response = client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
    
    assert response.status_code == 204
    
    # Verify user is soft deleted
    get_response = client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


def test_unauthorized_access():
    """Test accessing endpoints without authentication."""
    response = client.get("/api/v1/users/")
    assert response.status_code == 401


def test_non_admin_cannot_list_users(test_db):
    """Test that non-admin users cannot list users."""
    # Create a pharmacist user
    db = TestingSessionLocal()
    pharmacist = User(
        username="pharmacist",
        email="pharmacist@test.com",
        password_hash=get_password_hash("pharma123"),
        full_name="Test Pharmacist",
        role="Pharmacist",
        is_active=True
    )
    db.add(pharmacist)
    db.commit()
    db.close()
    
    # Login as pharmacist
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "pharmacist", "password": "pharma123"}
    )
    pharmacist_token = login_response.json()["access_token"]
    pharmacist_headers = {"Authorization": f"Bearer {pharmacist_token}"}
    
    # Try to list users (should be forbidden)
    response = client.get("/api/v1/users/", headers=pharmacist_headers)
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]


def test_user_can_view_own_profile(test_db):
    """Test that users can view their own profile."""
    # Create a pharmacist user
    db = TestingSessionLocal()
    pharmacist = User(
        username="selfview",
        email="selfview@test.com",
        password_hash=get_password_hash("selfview123"),
        full_name="Self View User",
        role="Pharmacist",
        is_active=True
    )
    db.add(pharmacist)
    db.commit()
    user_id = pharmacist.id
    db.close()
    
    # Login as pharmacist
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "selfview", "password": "selfview123"}
    )
    pharmacist_token = login_response.json()["access_token"]
    pharmacist_headers = {"Authorization": f"Bearer {pharmacist_token}"}
    
    # View own profile
    response = client.get(f"/api/v1/users/{user_id}", headers=pharmacist_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "selfview"


def test_user_cannot_change_own_role(test_db):
    """Test that users cannot change their own role."""
    # Create a pharmacist user
    db = TestingSessionLocal()
    pharmacist = User(
        username="norole",
        email="norole@test.com",
        password_hash=get_password_hash("norole123"),
        full_name="No Role Change User",
        role="Pharmacist",
        is_active=True
    )
    db.add(pharmacist)
    db.commit()
    user_id = pharmacist.id
    db.close()
    
    # Login as pharmacist
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "norole", "password": "norole123"}
    )
    pharmacist_token = login_response.json()["access_token"]
    pharmacist_headers = {"Authorization": f"Bearer {pharmacist_token}"}
    
    # Try to change role
    response = client.put(
        f"/api/v1/users/{user_id}",
        json={"role": "Administrator"},
        headers=pharmacist_headers
    )
    assert response.status_code == 403
    assert "Only administrators can change user roles" in response.json()["detail"]