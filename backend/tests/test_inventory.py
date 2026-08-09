"""Tests for Inventory API endpoints."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.medical_supply import MedicalSupply
from app.models.inventory import Inventory
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
def inventory_manager_user(db_session):
    """Create an inventory manager user for testing."""
    user = User(
        username="inventory_mgr",
        email="inventory@test.com",
        password_hash=hash_password("invpass123"),
        full_name="Inventory Manager",
        role="Inventory_Manager",
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
def inventory_manager_token(inventory_manager_user):
    """Generate JWT token for inventory manager user."""
    return create_access_token(data={"sub": inventory_manager_user.username})


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
        unit_price=25.50
    )
    db_session.add(supply)
    db_session.commit()
    db_session.refresh(supply)
    return supply


@pytest.fixture
def sample_inventory(db_session, sample_supply, admin_user):
    """Create a sample inventory item for testing."""
    inventory = Inventory(
        supply_id=sample_supply.id,
        current_stock=500,
        safety_stock=200,
        location="Warehouse A",
        batch_number="BATCH001",
        expiry_date=date.today() + timedelta(days=180),
        updated_by=admin_user.id
    )
    db_session.add(inventory)
    db_session.commit()
    db_session.refresh(inventory)
    return inventory


# ── Test Cases ────────────────────────────────────────────────────────────────

class TestListInventory:
    """Tests for GET /api/v1/inventory endpoint."""
    
    def test_list_inventory_success(self, admin_token, sample_inventory):
        """Test listing inventory as authenticated user."""
        response = client.get(
            "/api/v1/inventory",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["current_stock"] == 500
        assert data[0]["safety_stock"] == 200
        assert data[0]["supply"]["name"] == "Surgical Mask N95"
    
    def test_list_inventory_unauthorized(self):
        """Test listing inventory without authentication."""
        response = client.get("/api/v1/inventory")
        assert response.status_code == 401
    
    def test_list_inventory_filter_by_supply(self, admin_token, db_session, sample_supply, admin_user):
        """Test filtering inventory by supply_id."""
        # Create another supply and inventory
        supply2 = MedicalSupply(name="Gloves", category="PPE", unit="box")
        db_session.add(supply2)
        db_session.commit()
        
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=100, safety_stock=50, updated_by=admin_user.id)
        inv2 = Inventory(supply_id=supply2.id, current_stock=200, safety_stock=100, updated_by=admin_user.id)
        db_session.add_all([inv1, inv2])
        db_session.commit()
        
        response = client.get(
            f"/api/v1/inventory?supply_id={sample_supply.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["supply_id"] == sample_supply.id
    
    def test_list_inventory_filter_by_location(self, admin_token, db_session, sample_supply, admin_user):
        """Test filtering inventory by location."""
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=100, safety_stock=50, location="Warehouse A", updated_by=admin_user.id)
        inv2 = Inventory(supply_id=sample_supply.id, current_stock=200, safety_stock=100, location="Warehouse B", updated_by=admin_user.id)
        db_session.add_all([inv1, inv2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/inventory?location=Warehouse A",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["location"] == "Warehouse A"


class TestGetInventoryById:
    """Tests for GET /api/v1/inventory/{id} endpoint."""
    
    def test_get_inventory_success(self, admin_token, sample_inventory):
        """Test getting inventory by ID."""
        response = client.get(
            f"/api/v1/inventory/{sample_inventory.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_inventory.id
        assert data["current_stock"] == 500
        assert data["safety_stock"] == 200
        assert data["location"] == "Warehouse A"
    
    def test_get_inventory_not_found(self, admin_token):
        """Test getting a non-existent inventory item."""
        response = client.get(
            "/api/v1/inventory/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestUpdateInventory:
    """Tests for PUT /api/v1/inventory/{id} endpoint."""
    
    def test_update_inventory_as_admin(self, admin_token, sample_inventory):
        """Test updating inventory as admin."""
        update_data = {
            "current_stock": 600,
            "safety_stock": 250
        }
        
        response = client.put(
            f"/api/v1/inventory/{sample_inventory.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_stock"] == 600
        assert data["safety_stock"] == 250
        assert data["location"] == "Warehouse A"  # Unchanged
    
    def test_update_inventory_as_inventory_manager(self, inventory_manager_token, sample_inventory):
        """Test updating inventory as inventory manager."""
        update_data = {"current_stock": 450}
        
        response = client.put(
            f"/api/v1/inventory/{sample_inventory.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {inventory_manager_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_stock"] == 450
    
    def test_update_inventory_forbidden_pharmacist(self, pharmacist_token, sample_inventory):
        """Test that pharmacists cannot update inventory."""
        update_data = {"current_stock": 450}
        
        response = client.put(
            f"/api/v1/inventory/{sample_inventory.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 403
    
    def test_update_inventory_negative_stock(self, admin_token, sample_inventory):
        """Test that negative stock is rejected."""
        update_data = {"current_stock": -10}
        
        response = client.put(
            f"/api/v1/inventory/{sample_inventory.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Pydantic validation returns 422
        assert response.status_code == 422
    
    def test_update_inventory_not_found(self, admin_token):
        """Test updating a non-existent inventory item."""
        update_data = {"current_stock": 100}
        
        response = client.put(
            "/api/v1/inventory/99999",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestBatchUpdateInventory:
    """Tests for POST /api/v1/inventory/batch-update endpoint."""
    
    def test_batch_update_success(self, admin_token, db_session, sample_supply, admin_user):
        """Test batch updating multiple inventory items."""
        # Create multiple inventory items
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=100, safety_stock=50, updated_by=admin_user.id)
        inv2 = Inventory(supply_id=sample_supply.id, current_stock=200, safety_stock=100, updated_by=admin_user.id)
        db_session.add_all([inv1, inv2])
        db_session.commit()
        db_session.refresh(inv1)
        db_session.refresh(inv2)
        
        updates = [
            {"inventory_id": inv1.id, "current_stock": 150},
            {"inventory_id": inv2.id, "current_stock": 250, "safety_stock": 120}
        ]
        
        response = client.post(
            "/api/v1/inventory/batch-update",
            json=updates,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Verify updates
        updated_stocks = {item["id"]: item["current_stock"] for item in data}
        assert updated_stocks[inv1.id] == 150
        assert updated_stocks[inv2.id] == 250
    
    def test_batch_update_as_inventory_manager(self, inventory_manager_token, db_session, sample_supply, inventory_manager_user):
        """Test batch update as inventory manager."""
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=100, safety_stock=50, updated_by=inventory_manager_user.id)
        db_session.add(inv1)
        db_session.commit()
        db_session.refresh(inv1)
        
        updates = [{"inventory_id": inv1.id, "current_stock": 150}]
        
        response = client.post(
            "/api/v1/inventory/batch-update",
            json=updates,
            headers={"Authorization": f"Bearer {inventory_manager_token}"}
        )
        assert response.status_code == 200
    
    def test_batch_update_forbidden_pharmacist(self, pharmacist_token):
        """Test that pharmacists cannot batch update."""
        updates = [{"inventory_id": 1, "current_stock": 150}]
        
        response = client.post(
            "/api/v1/inventory/batch-update",
            json=updates,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 403
    
    def test_batch_update_skip_invalid(self, admin_token, db_session, sample_supply, admin_user):
        """Test that invalid items are skipped in batch update."""
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=100, safety_stock=50, updated_by=admin_user.id)
        db_session.add(inv1)
        db_session.commit()
        db_session.refresh(inv1)
        
        updates = [
            {"inventory_id": inv1.id, "current_stock": 150},
            {"inventory_id": 99999, "current_stock": 200}  # Non-existent
        ]
        
        response = client.post(
            "/api/v1/inventory/batch-update",
            json=updates,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Only valid item updated


class TestGetLowStockItems:
    """Tests for GET /api/v1/inventory/low-stock endpoint."""
    
    def test_get_low_stock_items(self, admin_token, db_session, sample_supply, admin_user):
        """Test getting low stock items."""
        # Create inventory items with different stock levels
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=50, safety_stock=200, updated_by=admin_user.id)  # Low
        inv2 = Inventory(supply_id=sample_supply.id, current_stock=500, safety_stock=200, updated_by=admin_user.id)  # Safe
        db_session.add_all([inv1, inv2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/inventory/low-stock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["current_stock"] == 50
    
    def test_get_low_stock_with_threshold(self, admin_token, db_session, sample_supply, admin_user):
        """Test getting low stock items with custom threshold."""
        # Create inventory at exactly safety stock
        inv1 = Inventory(supply_id=sample_supply.id, current_stock=200, safety_stock=200, updated_by=admin_user.id)
        db_session.add(inv1)
        db_session.commit()
        
        # With threshold 1.0, should be included
        response = client.get(
            "/api/v1/inventory/low-stock?threshold=1.0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        
        # With threshold 0.5, should not be included
        response = client.get(
            "/api/v1/inventory/low-stock?threshold=0.5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestGetExpiringItems:
    """Tests for GET /api/v1/inventory/expiring endpoint."""
    
    def test_get_expiring_items(self, admin_token, db_session, sample_supply, admin_user):
        """Test getting expiring items."""
        today = date.today()
        
        # Create inventory items with different expiry dates
        inv1 = Inventory(
            supply_id=sample_supply.id,
            current_stock=100,
            safety_stock=50,
            expiry_date=today + timedelta(days=15),  # Expiring soon
            updated_by=admin_user.id
        )
        inv2 = Inventory(
            supply_id=sample_supply.id,
            current_stock=200,
            safety_stock=100,
            expiry_date=today + timedelta(days=90),  # Not expiring soon
            updated_by=admin_user.id
        )
        inv3 = Inventory(
            supply_id=sample_supply.id,
            current_stock=150,
            safety_stock=75,
            expiry_date=None,  # No expiry date
            updated_by=admin_user.id
        )
        db_session.add_all([inv1, inv2, inv3])
        db_session.commit()
        
        response = client.get(
            "/api/v1/inventory/expiring?days=30",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["expiry_date"] == str(today + timedelta(days=15))
    
    def test_get_expiring_items_custom_days(self, admin_token, db_session, sample_supply, admin_user):
        """Test getting expiring items with custom days threshold."""
        today = date.today()
        
        inv1 = Inventory(
            supply_id=sample_supply.id,
            current_stock=100,
            safety_stock=50,
            expiry_date=today + timedelta(days=45),
            updated_by=admin_user.id
        )
        db_session.add(inv1)
        db_session.commit()
        
        # Should not be included with 30 days
        response = client.get(
            "/api/v1/inventory/expiring?days=30",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 0
        
        # Should be included with 60 days
        response = client.get(
            "/api/v1/inventory/expiring?days=60",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
