"""Tests for Environmental Data API endpoints."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.environmental_data import EnvironmentalData
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
def sample_environmental_data(db_session):
    """Create sample environmental data for testing."""
    now = datetime.utcnow()
    data = EnvironmentalData(
        recorded_at=now,
        location="Ho Chi Minh City",
        temperature=28.5,
        humidity=75.0,
        rainfall=5.2,
        air_quality_index=85,
        data_source="manual"
    )
    db_session.add(data)
    db_session.commit()
    db_session.refresh(data)
    return data


# ── Test Cases ────────────────────────────────────────────────────────────────

class TestListEnvironmentalData:
    """Tests for GET /api/v1/environmental endpoint."""
    
    def test_list_environmental_data_success(self, admin_token, sample_environmental_data):
        """Test listing environmental data as authenticated user."""
        response = client.get(
            "/api/v1/environmental",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["location"] == "Ho Chi Minh City"
        assert data[0]["temperature"] == 28.5
        assert data[0]["humidity"] == 75.0
        assert data[0]["rainfall"] == 5.2
        assert data[0]["air_quality_index"] == 85
    
    def test_list_environmental_data_unauthorized(self):
        """Test listing environmental data without authentication."""
        response = client.get("/api/v1/environmental")
        assert response.status_code == 401
    
    def test_list_environmental_data_filter_by_location(
        self, admin_token, db_session
    ):
        """Test filtering environmental data by location."""
        now = datetime.utcnow()
        
        # Create data for different locations
        data1 = EnvironmentalData(
            recorded_at=now,
            location="Ho Chi Minh City",
            temperature=28.5,
            humidity=75.0,
            data_source="manual"
        )
        data2 = EnvironmentalData(
            recorded_at=now,
            location="Hanoi",
            temperature=25.0,
            humidity=70.0,
            data_source="manual"
        )
        db_session.add_all([data1, data2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/environmental?location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["location"] == "Ho Chi Minh City"
    
    def test_list_environmental_data_pagination(self, admin_token, db_session):
        """Test pagination of environmental data."""
        now = datetime.utcnow()
        
        # Create multiple records
        for i in range(5):
            data = EnvironmentalData(
                recorded_at=now - timedelta(hours=i),
                location="Ho Chi Minh City",
                temperature=28.0 + i,
                humidity=75.0,
                data_source="manual"
            )
            db_session.add(data)
        db_session.commit()
        
        # Test with limit
        response = client.get(
            "/api/v1/environmental?limit=3",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = client.get(
            "/api/v1/environmental?skip=2&limit=2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestCreateEnvironmentalData:
    """Tests for POST /api/v1/environmental endpoint."""
    
    def test_create_environmental_data_success(self, admin_token):
        """Test creating environmental data with valid values."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "temperature": 30.5,
            "humidity": 80.0,
            "rainfall": 10.5,
            "air_quality_index": 95,
            "data_source": "OpenWeather API"
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        result = response.json()
        assert result["location"] == "Ho Chi Minh City"
        assert result["temperature"] == 30.5
        assert result["humidity"] == 80.0
        assert result["rainfall"] == 10.5
        assert result["air_quality_index"] == 95
        assert "id" in result
        assert "created_at" in result
    
    def test_create_environmental_data_as_pharmacist(self, pharmacist_token):
        """Test that pharmacists can create environmental data."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Hanoi",
            "temperature": 25.0,
            "humidity": 70.0
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 201
    
    def test_create_environmental_data_minimal(self, admin_token):
        """Test creating environmental data with minimal fields."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "temperature": 28.0
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        result = response.json()
        assert result["temperature"] == 28.0
        assert result["humidity"] is None
        assert result["rainfall"] is None
        assert result["air_quality_index"] is None
    
    def test_create_environmental_data_invalid_temperature(self, admin_token):
        """Test that invalid temperature is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "temperature": 100.0  # Too high
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "Temperature" in response.json()["detail"]["errors"][0]
    
    def test_create_environmental_data_invalid_humidity(self, admin_token):
        """Test that invalid humidity is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "humidity": 150.0  # Too high
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "Humidity" in response.json()["detail"]["errors"][0]
    
    def test_create_environmental_data_invalid_rainfall(self, admin_token):
        """Test that invalid rainfall is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "rainfall": -5.0  # Negative
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "Rainfall" in response.json()["detail"]["errors"][0]
    
    def test_create_environmental_data_invalid_aqi(self, admin_token):
        """Test that invalid AQI is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "air_quality_index": 600  # Too high
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "Air Quality Index" in response.json()["detail"]["errors"][0]
    
    def test_create_environmental_data_no_measurements(self, admin_token):
        """Test that at least one measurement is required."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City"
        }
        
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "at least one environmental measurement" in response.json()["detail"]["errors"][0].lower()
    
    def test_create_environmental_data_unauthorized(self):
        """Test creating environmental data without authentication."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "location": "Ho Chi Minh City",
            "temperature": 28.0
        }
        
        response = client.post("/api/v1/environmental", json=data)
        assert response.status_code == 401


class TestGetLatestEnvironmentalData:
    """Tests for GET /api/v1/environmental/latest endpoint."""
    
    def test_get_latest_data_success(self, admin_token, db_session):
        """Test getting the latest environmental data."""
        now = datetime.utcnow()
        
        # Create multiple records
        data1 = EnvironmentalData(
            recorded_at=now - timedelta(hours=2),
            location="Ho Chi Minh City",
            temperature=27.0,
            humidity=70.0,
            data_source="manual"
        )
        data2 = EnvironmentalData(
            recorded_at=now,
            location="Ho Chi Minh City",
            temperature=29.0,
            humidity=75.0,
            data_source="manual"
        )
        db_session.add_all([data1, data2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/environmental/latest",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["temperature"] == 29.0  # Latest record
    
    def test_get_latest_data_by_location(self, admin_token, db_session):
        """Test getting latest data filtered by location."""
        now = datetime.utcnow()
        
        # Create data for different locations
        data1 = EnvironmentalData(
            recorded_at=now - timedelta(hours=1),
            location="Ho Chi Minh City",
            temperature=28.0,
            humidity=75.0,
            data_source="manual"
        )
        data2 = EnvironmentalData(
            recorded_at=now,
            location="Hanoi",
            temperature=25.0,
            humidity=70.0,
            data_source="manual"
        )
        db_session.add_all([data1, data2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/environmental/latest?location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Ho Chi Minh City"
        assert data["temperature"] == 28.0
    
    def test_get_latest_data_not_found(self, admin_token):
        """Test getting latest data when no data exists."""
        response = client.get(
            "/api/v1/environmental/latest",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
    
    def test_get_latest_data_location_not_found(self, admin_token, sample_environmental_data):
        """Test getting latest data for non-existent location."""
        response = client.get(
            "/api/v1/environmental/latest?location=NonExistentCity",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestGetEnvironmentalDataRange:
    """Tests for GET /api/v1/environmental/range endpoint."""
    
    def test_get_data_range_success(self, admin_token, db_session):
        """Test getting environmental data for a date range."""
        now = datetime.utcnow()
        
        # Create data across multiple days
        for i in range(5):
            data = EnvironmentalData(
                recorded_at=now - timedelta(days=i),
                location="Ho Chi Minh City",
                temperature=28.0 + i,
                humidity=75.0,
                data_source="manual"
            )
            db_session.add(data)
        db_session.commit()
        
        start_date = (now - timedelta(days=3)).isoformat()
        end_date = now.isoformat()
        
        response = client.get(
            f"/api/v1/environmental/range?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4  # Days 0, 1, 2, 3
    
    def test_get_data_range_with_location(self, admin_token, db_session):
        """Test getting data range filtered by location."""
        now = datetime.utcnow()
        
        # Create data for different locations
        data1 = EnvironmentalData(
            recorded_at=now - timedelta(days=1),
            location="Ho Chi Minh City",
            temperature=28.0,
            humidity=75.0,
            data_source="manual"
        )
        data2 = EnvironmentalData(
            recorded_at=now - timedelta(days=1),
            location="Hanoi",
            temperature=25.0,
            humidity=70.0,
            data_source="manual"
        )
        data3 = EnvironmentalData(
            recorded_at=now,
            location="Ho Chi Minh City",
            temperature=29.0,
            humidity=76.0,
            data_source="manual"
        )
        db_session.add_all([data1, data2, data3])
        db_session.commit()
        
        start_date = (now - timedelta(days=2)).isoformat()
        end_date = now.isoformat()
        
        response = client.get(
            f"/api/v1/environmental/range?start_date={start_date}&end_date={end_date}&location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(item["location"] == "Ho Chi Minh City" for item in data)
    
    def test_get_data_range_invalid_dates(self, admin_token):
        """Test that start_date after end_date is rejected."""
        now = datetime.utcnow()
        start_date = now.isoformat()
        end_date = (now - timedelta(days=1)).isoformat()
        
        response = client.get(
            f"/api/v1/environmental/range?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "Start date must be before or equal to end date" in response.json()["detail"]
    
    def test_get_data_range_empty_result(self, admin_token, sample_environmental_data):
        """Test getting data range with no matching records."""
        now = datetime.utcnow()
        start_date = (now + timedelta(days=1)).isoformat()
        end_date = (now + timedelta(days=2)).isoformat()
        
        response = client.get(
            f"/api/v1/environmental/range?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestEnvironmentalDataValidation:
    """Tests for environmental data validation."""
    
    def test_valid_temperature_range(self, admin_token):
        """Test valid temperature values."""
        now = datetime.utcnow()
        
        # Test minimum valid temperature
        data = {
            "recorded_at": now.isoformat(),
            "location": "Test Location",
            "temperature": -49.0
        }
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        
        # Test maximum valid temperature
        data["temperature"] = 59.0
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
    
    def test_valid_humidity_range(self, admin_token):
        """Test valid humidity values."""
        now = datetime.utcnow()
        
        # Test minimum valid humidity
        data = {
            "recorded_at": now.isoformat(),
            "location": "Test Location",
            "humidity": 0.0
        }
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        
        # Test maximum valid humidity
        data["humidity"] = 100.0
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
    
    def test_valid_aqi_range(self, admin_token):
        """Test valid AQI values."""
        now = datetime.utcnow()
        
        # Test minimum valid AQI
        data = {
            "recorded_at": now.isoformat(),
            "location": "Test Location",
            "air_quality_index": 0
        }
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        
        # Test maximum valid AQI
        data["air_quality_index"] = 500
        response = client.post(
            "/api/v1/environmental",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
