"""Tests for Disease Cases API endpoints."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.disease_case import DiseaseCase
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
def sample_disease_case(db_session):
    """Create sample disease case for testing."""
    now = datetime.utcnow()
    case = DiseaseCase(
        recorded_at=now,
        disease_type="dengue_fever",
        case_count=150,
        location="Ho Chi Minh City",
        severity="moderate",
        data_source="manual"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


# ── Test Cases ────────────────────────────────────────────────────────────────

class TestListDiseaseCases:
    """Tests for GET /api/v1/disease-cases endpoint."""
    
    def test_list_disease_cases_success(self, admin_token, sample_disease_case):
        """Test listing disease cases as authenticated user."""
        response = client.get(
            "/api/v1/disease-cases",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["disease_type"] == "dengue_fever"
        assert data[0]["case_count"] == 150
        assert data[0]["location"] == "Ho Chi Minh City"
        assert data[0]["severity"] == "moderate"
    
    def test_list_disease_cases_unauthorized(self):
        """Test listing disease cases without authentication."""
        response = client.get("/api/v1/disease-cases")
        assert response.status_code == 401
    
    def test_list_disease_cases_filter_by_disease_type(
        self, admin_token, db_session
    ):
        """Test filtering disease cases by disease type."""
        now = datetime.utcnow()
        
        # Create cases for different disease types
        case1 = DiseaseCase(
            recorded_at=now,
            disease_type="dengue_fever",
            case_count=150,
            location="Ho Chi Minh City",
            data_source="manual"
        )
        case2 = DiseaseCase(
            recorded_at=now,
            disease_type="seasonal_flu",
            case_count=320,
            location="Ho Chi Minh City",
            data_source="manual"
        )
        db_session.add_all([case1, case2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases?disease_type=dengue_fever",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["disease_type"] == "dengue_fever"
    
    def test_list_disease_cases_filter_by_location(
        self, admin_token, db_session
    ):
        """Test filtering disease cases by location."""
        now = datetime.utcnow()
        
        # Create cases for different locations
        case1 = DiseaseCase(
            recorded_at=now,
            disease_type="dengue_fever",
            case_count=150,
            location="Ho Chi Minh City",
            data_source="manual"
        )
        case2 = DiseaseCase(
            recorded_at=now,
            disease_type="dengue_fever",
            case_count=80,
            location="Hanoi",
            data_source="manual"
        )
        db_session.add_all([case1, case2])
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases?location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["location"] == "Ho Chi Minh City"
    
    def test_list_disease_cases_pagination(self, admin_token, db_session):
        """Test pagination of disease cases."""
        now = datetime.utcnow()
        
        # Create multiple records
        for i in range(5):
            case = DiseaseCase(
                recorded_at=now - timedelta(hours=i),
                disease_type="dengue_fever",
                case_count=100 + i * 10,
                location="Ho Chi Minh City",
                data_source="manual"
            )
            db_session.add(case)
        db_session.commit()
        
        # Test with limit
        response = client.get(
            "/api/v1/disease-cases?limit=3",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = client.get(
            "/api/v1/disease-cases?skip=2&limit=2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestCreateDiseaseCase:
    """Tests for POST /api/v1/disease-cases endpoint."""
    
    def test_create_disease_case_success(self, admin_token):
        """Test creating disease case with valid values."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": 150,
            "location": "Ho Chi Minh City",
            "severity": "moderate",
            "data_source": "Health Department API"
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        result = response.json()
        assert result["disease_type"] == "dengue_fever"
        assert result["case_count"] == 150
        assert result["location"] == "Ho Chi Minh City"
        assert result["severity"] == "moderate"
        assert "id" in result
        assert "created_at" in result
    
    def test_create_disease_case_as_pharmacist(self, pharmacist_token):
        """Test that pharmacists can create disease cases."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "seasonal_flu",
            "case_count": 320,
            "location": "Hanoi"
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {pharmacist_token}"}
        )
        assert response.status_code == 201
    
    def test_create_disease_case_all_disease_types(self, admin_token):
        """Test creating cases for all valid disease types."""
        now = datetime.utcnow()
        disease_types = ["dengue_fever", "seasonal_flu", "respiratory_disease"]
        
        for disease_type in disease_types:
            data = {
                "recorded_at": now.isoformat(),
                "disease_type": disease_type,
                "case_count": 100,
                "location": "Ho Chi Minh City"
            }
            
            response = client.post(
                "/api/v1/disease-cases",
                json=data,
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 201
            result = response.json()
            assert result["disease_type"] == disease_type
    
    def test_create_disease_case_zero_count(self, admin_token):
        """Test creating disease case with zero count (valid edge case)."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": 0,
            "location": "Ho Chi Minh City"
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        result = response.json()
        assert result["case_count"] == 0
    
    def test_create_disease_case_negative_count(self, admin_token):
        """Test that negative case count is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": -10,
            "location": "Ho Chi Minh City"
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Pydantic validation catches this at 422 level
        assert response.status_code == 422
    
    def test_create_disease_case_invalid_disease_type(self, admin_token):
        """Test that invalid disease type is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "invalid_disease",
            "case_count": 100,
            "location": "Ho Chi Minh City"
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 422  # Pydantic validation error
    
    def test_create_disease_case_empty_location(self, admin_token):
        """Test that empty location is rejected."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": 100,
            "location": ""
        }
        
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "location" in response.json()["detail"]["errors"][0].lower()
    
    def test_create_disease_case_unauthorized(self):
        """Test creating disease case without authentication."""
        now = datetime.utcnow()
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": 100,
            "location": "Ho Chi Minh City"
        }
        
        response = client.post("/api/v1/disease-cases", json=data)
        assert response.status_code == 401


class TestGetDiseaseCaseStatistics:
    """Tests for GET /api/v1/disease-cases/stats endpoint."""
    
    def test_get_statistics_success(self, admin_token, db_session):
        """Test getting disease case statistics."""
        now = datetime.utcnow()
        
        # Create multiple cases for different disease types
        cases = [
            DiseaseCase(
                recorded_at=now - timedelta(days=1),
                disease_type="dengue_fever",
                case_count=150,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=200,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="seasonal_flu",
                case_count=320,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "statistics" in data
        stats = data["statistics"]
        
        # Check dengue fever stats
        dengue_stats = next(s for s in stats if s["disease_type"] == "dengue_fever")
        assert dengue_stats["total_cases"] == 350  # 150 + 200
        assert dengue_stats["record_count"] == 2
        
        # Check seasonal flu stats
        flu_stats = next(s for s in stats if s["disease_type"] == "seasonal_flu")
        assert flu_stats["total_cases"] == 320
        assert flu_stats["record_count"] == 1
    
    def test_get_statistics_filter_by_location(self, admin_token, db_session):
        """Test getting statistics filtered by location."""
        now = datetime.utcnow()
        
        # Create cases for different locations
        cases = [
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=150,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=80,
                location="Hanoi",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/stats?location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        stats = data["statistics"]
        assert len(stats) == 1
        assert stats[0]["total_cases"] == 150
    
    def test_get_statistics_filter_by_date_range(self, admin_token, db_session):
        """Test getting statistics filtered by date range."""
        now = datetime.utcnow()
        
        # Create cases across different dates
        cases = [
            DiseaseCase(
                recorded_at=now - timedelta(days=5),
                disease_type="dengue_fever",
                case_count=100,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now - timedelta(days=2),
                disease_type="dengue_fever",
                case_count=150,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=200,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        start_date = (now - timedelta(days=3)).isoformat()
        end_date = now.isoformat()
        
        response = client.get(
            f"/api/v1/disease-cases/stats?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        stats = data["statistics"]
        assert len(stats) == 1
        assert stats[0]["total_cases"] == 350  # 150 + 200 (excludes the 5-day-old record)
    
    def test_get_statistics_empty_result(self, admin_token):
        """Test getting statistics when no data exists."""
        response = client.get(
            "/api/v1/disease-cases/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["statistics"] == []


class TestGetDiseaseCaseTrends:
    """Tests for GET /api/v1/disease-cases/trends endpoint."""
    
    def test_get_trends_success(self, admin_token, db_session):
        """Test getting disease case trends."""
        now = datetime.utcnow()
        
        # Create cases across multiple days
        for i in range(3):
            case = DiseaseCase(
                recorded_at=now - timedelta(days=i),
                disease_type="dengue_fever",
                case_count=100 + i * 10,
                location="Ho Chi Minh City",
                data_source="manual"
            )
            db_session.add(case)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/trends",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        trends = data["trends"]
        assert len(trends) == 3
        assert all("date" in t for t in trends)
        assert all("disease_type" in t for t in trends)
        assert all("total_cases" in t for t in trends)
    
    def test_get_trends_filter_by_disease_type(self, admin_token, db_session):
        """Test getting trends filtered by disease type."""
        now = datetime.utcnow()
        
        # Create cases for different disease types
        cases = [
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=150,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="seasonal_flu",
                case_count=320,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/trends?disease_type=dengue_fever",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        trends = data["trends"]
        assert len(trends) == 1
        assert trends[0]["disease_type"] == "dengue_fever"
    
    def test_get_trends_filter_by_location(self, admin_token, db_session):
        """Test getting trends filtered by location."""
        now = datetime.utcnow()
        
        # Create cases for different locations
        cases = [
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=150,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=80,
                location="Hanoi",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/trends?location=Ho Chi Minh City",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        trends = data["trends"]
        assert len(trends) == 1
        assert trends[0]["location"] == "Ho Chi Minh City"
    
    def test_get_trends_aggregation_by_date(self, admin_token, db_session):
        """Test that trends aggregate multiple records on the same date."""
        now = datetime.utcnow()
        
        # Create multiple cases on the same date
        cases = [
            DiseaseCase(
                recorded_at=now,
                disease_type="dengue_fever",
                case_count=100,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
            DiseaseCase(
                recorded_at=now + timedelta(hours=2),
                disease_type="dengue_fever",
                case_count=50,
                location="Ho Chi Minh City",
                data_source="manual"
            ),
        ]
        db_session.add_all(cases)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/trends",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        trends = data["trends"]
        assert len(trends) == 1
        assert trends[0]["total_cases"] == 150  # 100 + 50
    
    def test_get_trends_with_limit(self, admin_token, db_session):
        """Test trends with limit parameter."""
        now = datetime.utcnow()
        
        # Create cases across multiple days
        for i in range(10):
            case = DiseaseCase(
                recorded_at=now - timedelta(days=i),
                disease_type="dengue_fever",
                case_count=100,
                location="Ho Chi Minh City",
                data_source="manual"
            )
            db_session.add(case)
        db_session.commit()
        
        response = client.get(
            "/api/v1/disease-cases/trends?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        trends = data["trends"]
        assert len(trends) == 5
    
    def test_get_trends_empty_result(self, admin_token):
        """Test getting trends when no data exists."""
        response = client.get(
            "/api/v1/disease-cases/trends",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trends"] == []


class TestDiseaseCaseValidation:
    """Tests for disease case data validation."""
    
    def test_valid_case_count_boundary(self, admin_token):
        """Test valid case count boundary values."""
        now = datetime.utcnow()
        
        # Test zero (minimum valid)
        data = {
            "recorded_at": now.isoformat(),
            "disease_type": "dengue_fever",
            "case_count": 0,
            "location": "Test Location"
        }
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        
        # Test large number
        data["case_count"] = 999999
        response = client.post(
            "/api/v1/disease-cases",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
    
    def test_all_disease_types_valid(self, admin_token):
        """Test that all three disease types are accepted."""
        now = datetime.utcnow()
        disease_types = ["dengue_fever", "seasonal_flu", "respiratory_disease"]
        
        for disease_type in disease_types:
            data = {
                "recorded_at": now.isoformat(),
                "disease_type": disease_type,
                "case_count": 100,
                "location": "Test Location"
            }
            response = client.post(
                "/api/v1/disease-cases",
                json=data,
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 201, f"Failed for {disease_type}"
