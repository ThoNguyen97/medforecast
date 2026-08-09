"""Tests for Medical Supplies API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.medical_supply import MedicalSupply
from app.core.security import hash_password, create_access_token


# ── Test Database Setup ───────────────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    user = User(
        username="admin",
        email="admin@test.com",
        password_hash=hash_password("adminpass123"),
        full_name="Admin User",
        role="Administrator",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def pharmacist_user(db_session):
    """Create a pharmacist user for testing."""
    user = User(
        username="pharmacist",
        email="pharmacist@test.com",
        password_hash=hash_password("pharmapass123"),
        full_name="Pharmacist User",
        role="Pharmacist",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Generate JWT token for admin user."""
    return create_access_token(data={"sub": admin_user.username})


@pytest.fixture
def pharmacist_token(pharmacist_user):
    """Generate JWT token for pharmacist user."""
    return create_access_token(data={"sub": pharmacist_user.username})


@pytest.fixture
def sample_supply(db_session):
    """Create a sample medical supply for testing."""
    supply = MedicalSupply(
        name="Surgical Mask N95",
        category="PPE",
        unit="box",
        unit_price=25.50,
        minimum_order_quantity=100,
        lead_time_days=7,
        storage_capacity=5000,
        description="N95 respirator masks for medical use"
    )
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


# ── Test Cases ────────────────────────────────────────────────────────────────

class TestListSupplies:
    """Tests for GET /api/v1/supplies endpoint."""
    
    def test_list_supplies_success(self, admin_token, sample_supply):
        """Test listing supplies as authenticated user."""
        response = client.get(
            "/api/v1/supplies",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Surgical Mask N95"
        assert data[0]["category"] == "PPE"
    
    def test_list_supplies_unauthorized(self):
        """Test listing supplies without authentication."""
        response = client.get("/api/v1/supplies")
        assert response.status_code == 401
    
    def test_list_supplies_filter_by_category(self, admin_token, db_session):
        """Test filtering supplies by category."""
        # Create supplies in different categories
        supplies = [
            MedicalSupply(name="Mask", category="PPE", unit="box"),
            MedicalSupply(name="Gloves", category="PPE", unit="box"),
            MedicalSupply(name="Paracetamol", category="Medication", unit="bottle")
        ]
        for supply in supplies:
            db_session.add(supply)
        db_session.commit()
        
        response = client.get(
            "/api/v1/supplies?category=PPE",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(item["category"] == "PPE" for item in data)
    
    def test_list_supplies_search_by_name(self, admin_token, db_session):
        """Test searching supplies by name."""
        supplies = [
            MedicalSupply(name="Surgical Mask N95", category="PPE", unit="box"),
            MedicalSupply(name="Surgical Gloves", category="PPE", unit="box"),
            MedicalSupply(name="Paracetamol", category="Medication", unit="bottle")
        ]
        for supply in supplies:
            db_session.add(supply)
        db_session.commit()
        
        response = client.get(
            "/api/v1/supplies?search=Surgical",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("Surgical" in item["name"] for item in data)
    
    def test_list_supplies_pagination(self, admin_token, db_session):
        """Test pagination parameters."""
        # Create 5 supplies
        for i in range(5):
            supply = MedicalSupply(
                name=f"Supply {i}",
                category="Test",
                unit="unit"
            )
            db_session.add(supply)
        db_session.commit()
        
        response = client.get(
            "/api/v1/supplies?skip=2&limit=2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestCreateSupply:
    """Tests for POST /api/v1/supplies endpoint."""
    
    def test_create_supply_success(self, admin_token):
        """Test creating a supply as admin."""
        supply_data = {
            "name": "Latex Gloves",
            "category": "PPE",
            "unit": "box",
            "unit_price": 15.99,
            "minimum_order_quantity": 50,
            "lead_time_days": 5,
            "storage_capacity": 3000,
            "description": "Disposable latex gloves"
        }
        
        response = client.post(
            "/api/v1/supplies",
            json=supply_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Latex Gloves"
        assert data["category"] == "PPE"
        assert data["unit_price"] == 15.99
        assert "id" in data
        assert "created_at" in data
    
    def test_create_supply_forbidden_non_admin(self, pharmacist_token):
        """Test that non-admin users cannot create supplies."""
        supply_data = {
            "name": "Test Supply",
            "category": "Test",
            "unit": "unit"
        }
        
        response = client.post(
            "/api/v1/supplies",
            json=supply_data,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 403
    
    def test_create_supply_duplicate_name(self, admin_token, sample_supply):
        """Test creating a supply with duplicate name."""
        supply_data = {
            "name": "Surgical Mask N95",  # Same as sample_supply
            "category": "PPE",
            "unit": "box"
        }
        
        response = client.post(
            "/api/v1/supplies",
            json=supply_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_create_supply_minimal_data(self, admin_token):
        """Test creating a supply with only required fields."""
        supply_data = {
            "name": "Basic Supply",
            "category": "General",
            "unit": "piece"
        }
        
        response = client.post(
            "/api/v1/supplies",
            json=supply_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Basic Supply"
        assert data["unit_price"] is None
        assert data["description"] is None


class TestGetSupplyById:
    """Tests for GET /api/v1/supplies/{id} endpoint."""
    
    def test_get_supply_success(self, admin_token, sample_supply):
        """Test getting a supply by ID."""
        response = client.get(
            f"/api/v1/supplies/{sample_supply.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_supply.id
        assert data["name"] == "Surgical Mask N95"
        assert data["category"] == "PPE"
    
    def test_get_supply_not_found(self, admin_token):
        """Test getting a non-existent supply."""
        response = client.get(
            "/api/v1/supplies/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
    
    def test_get_supply_unauthorized(self, sample_supply):
        """Test getting a supply without authentication."""
        response = client.get(f"/api/v1/supplies/{sample_supply.id}")
        assert response.status_code == 401


class TestUpdateSupply:
    """Tests for PUT /api/v1/supplies/{id} endpoint."""
    
    def test_update_supply_success(self, admin_token, sample_supply):
        """Test updating a supply as admin."""
        update_data = {
            "unit_price": 30.00,
            "minimum_order_quantity": 150,
            "description": "Updated description"
        }
        
        response = client.put(
            f"/api/v1/supplies/{sample_supply.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unit_price"] == 30.00
        assert data["minimum_order_quantity"] == 150
        assert data["description"] == "Updated description"
        # Unchanged fields should remain the same
        assert data["name"] == "Surgical Mask N95"
        assert data["category"] == "PPE"
    
    def test_update_supply_forbidden_non_admin(self, pharmacist_token, sample_supply):
        """Test that non-admin users cannot update supplies."""
        update_data = {"unit_price": 30.00}
        
        response = client.put(
            f"/api/v1/supplies/{sample_supply.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 403
    
    def test_update_supply_not_found(self, admin_token):
        """Test updating a non-existent supply."""
        update_data = {"unit_price": 30.00}
        
        response = client.put(
            "/api/v1/supplies/99999",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
    
    def test_update_supply_duplicate_name(self, admin_token, db_session, sample_supply):
        """Test updating supply name to an existing name."""
        # Create another supply
        another_supply = MedicalSupply(
            name="Another Supply",
            category="Test",
            unit="unit"
        )
        db_session.add(another_supply)
        db_session.commit()
        
        # Try to update sample_supply name to match another_supply
        update_data = {"name": "Another Supply"}
        
        response = client.put(
            f"/api/v1/supplies/{sample_supply.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestDeleteSupply:
    """Tests for DELETE /api/v1/supplies/{id} endpoint."""
    
    def test_delete_supply_success(self, admin_token, sample_supply, db_session):
        """Test deleting a supply as admin."""
        supply_id = sample_supply.id
        
        response = client.delete(
            f"/api/v1/supplies/{supply_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 204
        
        # Verify supply is deleted
        deleted_supply = db_session.query(MedicalSupply).filter(
            MedicalSupply.id == supply_id
        ).first()
        assert deleted_supply is None
    
    def test_delete_supply_forbidden_non_admin(self, pharmacist_token, sample_supply):
        """Test that non-admin users cannot delete supplies."""
        response = client.delete(
            f"/api/v1/supplies/{sample_supply.id}",
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 403
    
    def test_delete_supply_not_found(self, admin_token):
        """Test deleting a non-existent supply."""
        response = client.delete(
            "/api/v1/supplies/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestGetCategories:
    """Tests for GET /api/v1/supplies/categories endpoint."""
    
    def test_get_categories_success(self, admin_token, db_session):
        """Test getting unique categories."""
        supplies = [
            MedicalSupply(name="Supply 1", category="PPE", unit="box"),
            MedicalSupply(name="Supply 2", category="PPE", unit="box"),
            MedicalSupply(name="Supply 3", category="Medication", unit="bottle"),
            MedicalSupply(name="Supply 4", category="Equipment", unit="unit")
        ]
        for supply in supplies:
            db_session.add(supply)
        db_session.commit()
        
        response = client.get(
            "/api/v1/supplies/categories",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert "PPE" in data
        assert "Medication" in data
        assert "Equipment" in data
    
    def test_get_categories_empty(self, admin_token):
        """Test getting categories when no supplies exist."""
        response = client.get(
            "/api/v1/supplies/categories",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_categories_unauthorized(self):
        """Test getting categories without authentication."""
        response = client.get("/api/v1/supplies/categories")
        assert response.status_code == 401
