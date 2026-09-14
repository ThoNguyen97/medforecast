"""Tests for Data Collector Service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.data_collector_service import DataCollectorService
from app.models.environmental_data import EnvironmentalData
from app.models.system_log import SystemLog


# ── Test Database Setup ───────────────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
def mock_weather_response():
    """Mock OpenWeather API weather response."""
    return {
        "main": {
            "temp": 28.5,
            "humidity": 75
        },
        "rain": {
            "1h": 5.2
        }
    }


@pytest.fixture
def mock_air_pollution_response():
    """Mock OpenWeather API air pollution response."""
    return {
        "list": [
            {
                "main": {
                    "aqi": 3
                }
            }
        ]
    }


# ── Test Cases ────────────────────────────────────────────────────────────────

class TestDataCollectorService:
    """Tests for DataCollectorService."""
    
    @patch('app.services.data_collector_service.settings')
    def test_init_with_api_key(self, mock_settings, db_session):
        """Test initializing service with API key."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        service = DataCollectorService(db_session)
        
        assert service.api_key == "test_api_key"
        assert service.db == db_session
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    def test_collect_weather_data_success(
        self,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response,
        mock_air_pollution_response
    ):
        """Test successful weather data collection."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # Mock successful API responses
        mock_weather = Mock()
        mock_weather.json.return_value = mock_weather_response
        mock_weather.raise_for_status = Mock()
        
        mock_air = Mock()
        mock_air.json.return_value = mock_air_pollution_response
        mock_air.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_weather, mock_air]
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is not None
        assert isinstance(result, EnvironmentalData)
        assert result.location == "Ho Chi Minh City"
        assert float(result.temperature) == 28.5
        assert float(result.humidity) == 75
        assert float(result.rainfall) == 5.2
        assert result.air_quality_index == 3
        assert result.data_source == "OpenWeather API"
        
        # Verify data was saved to database
        saved_data = db_session.query(EnvironmentalData).first()
        assert saved_data is not None
        assert saved_data.location == "Ho Chi Minh City"
    
    @patch('app.services.data_collector_service.settings')
    def test_collect_weather_data_no_api_key(self, mock_settings, db_session):
        """Test that collection fails gracefully without API key."""
        mock_settings.OPENWEATHER_API_KEY = ""
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is None
        
        # Verify error was logged
        error_log = db_session.query(SystemLog).filter(
            SystemLog.log_level == "ERROR"
        ).first()
        assert error_log is not None
        assert "API key not configured" in error_log.message
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    @patch('app.services.data_collector_service.time.sleep')
    def test_collect_weather_data_with_retry(
        self,
        mock_sleep,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response,
        mock_air_pollution_response
    ):
        """Test retry mechanism on API failure."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # First call fails, second succeeds
        mock_fail = Mock()
        mock_fail.raise_for_status = Mock(side_effect=Exception("API Error"))
        
        mock_success_weather = Mock()
        mock_success_weather.json.return_value = mock_weather_response
        mock_success_weather.raise_for_status = Mock()
        
        mock_success_air = Mock()
        mock_success_air.json.return_value = mock_air_pollution_response
        mock_success_air.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_fail, mock_success_weather, mock_success_air]
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is not None
        assert float(result.temperature) == 28.5
        
        # Verify retry was attempted (sleep was called)
        mock_sleep.assert_called_once_with(60)
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    @patch('app.services.data_collector_service.time.sleep')
    def test_collect_weather_data_max_retries_exceeded(
        self,
        mock_sleep,
        mock_settings,
        mock_get,
        db_session
    ):
        """Test that collection fails after max retries."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # All calls fail
        mock_fail = Mock()
        mock_fail.raise_for_status = Mock(side_effect=Exception("API Error"))
        mock_get.return_value = mock_fail
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is None
        
        # Verify 3 attempts were made (MAX_RETRIES)
        assert mock_get.call_count == 3
        
        # Verify 2 sleep calls (between retries)
        assert mock_sleep.call_count == 2
        
        # Verify error was logged
        error_log = db_session.query(SystemLog).filter(
            SystemLog.log_level == "ERROR"
        ).first()
        assert error_log is not None
        assert "after 3 attempts" in error_log.message
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    def test_collect_weather_data_no_rainfall(
        self,
        mock_settings,
        mock_get,
        db_session,
        mock_air_pollution_response
    ):
        """Test handling weather data without rainfall."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # Weather response without rain
        weather_response = {
            "main": {
                "temp": 30.0,
                "humidity": 65
            }
            # No "rain" field
        }
        
        mock_weather = Mock()
        mock_weather.json.return_value = weather_response
        mock_weather.raise_for_status = Mock()
        
        mock_air = Mock()
        mock_air.json.return_value = mock_air_pollution_response
        mock_air.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_weather, mock_air]
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is not None
        assert float(result.temperature) == 30.0
        assert float(result.humidity) == 65
        assert result.rainfall is None
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    def test_collect_weather_data_no_air_quality(
        self,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response
    ):
        """Test handling when air quality data is unavailable."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        mock_weather = Mock()
        mock_weather.json.return_value = mock_weather_response
        mock_weather.raise_for_status = Mock()
        
        # Air pollution request fails
        mock_air = Mock()
        mock_air.raise_for_status = Mock(side_effect=Exception("API Error"))
        
        mock_get.side_effect = [
            mock_weather,
            mock_air,
            mock_air,
            mock_air  # All 3 retries fail
        ]
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        # Should still succeed with weather data only (air quality is optional)
        assert result is not None
        assert float(result.temperature) == 28.5
        assert float(result.humidity) == 75
        assert result.air_quality_index is None  # Air quality failed
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    def test_collect_data_for_multiple_locations(
        self,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response,
        mock_air_pollution_response
    ):
        """Test collecting data for multiple locations."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # Mock successful responses for all requests
        mock_weather = Mock()
        mock_weather.json.return_value = mock_weather_response
        mock_weather.raise_for_status = Mock()
        
        mock_air = Mock()
        mock_air.json.return_value = mock_air_pollution_response
        mock_air.raise_for_status = Mock()
        
        # 2 locations × 2 API calls each = 4 calls
        mock_get.side_effect = [mock_weather, mock_air, mock_weather, mock_air]
        
        locations = {
            "Ho Chi Minh City": {"lat": 10.8231, "lon": 106.6297},
            "Hanoi": {"lat": 21.0285, "lon": 105.8542}
        }
        
        service = DataCollectorService(db_session)
        results = service.collect_data_for_locations(locations)
        
        assert len(results) == 2
        assert "Ho Chi Minh City" in results
        assert "Hanoi" in results
        assert results["Ho Chi Minh City"] is not None
        assert results["Hanoi"] is not None
        
        # Verify both records were saved
        saved_count = db_session.query(EnvironmentalData).count()
        assert saved_count == 2
    
    @patch('app.services.data_collector_service.settings')
    def test_collect_data_for_locations_missing_coordinates(
        self,
        mock_settings,
        db_session
    ):
        """Test handling locations with missing coordinates."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        locations = {
            "Ho Chi Minh City": {"lat": 10.8231, "lon": 106.6297},
            "Invalid Location": {"lat": None, "lon": None},
            "Another Invalid": {}
        }
        
        service = DataCollectorService(db_session)
        results = service.collect_data_for_locations(locations)
        
        assert len(results) == 3
        assert results["Invalid Location"] is None
        assert results["Another Invalid"] is None
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    def test_system_logging(
        self,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response,
        mock_air_pollution_response
    ):
        """Test that system logs are created correctly."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        mock_weather = Mock()
        mock_weather.json.return_value = mock_weather_response
        mock_weather.raise_for_status = Mock()
        
        mock_air = Mock()
        mock_air.json.return_value = mock_air_pollution_response
        mock_air.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_weather, mock_air]
        
        service = DataCollectorService(db_session)
        result = service.collect_weather_data(
            location="Ho Chi Minh City",
            lat=10.8231,
            lon=106.6297
        )
        
        assert result is not None
        
        # Verify INFO log was created
        info_log = db_session.query(SystemLog).filter(
            SystemLog.log_level == "INFO"
        ).first()
        assert info_log is not None
        assert "Collected environmental data" in info_log.message
        assert "Ho Chi Minh City" in info_log.message


class TestDataCollectorRetryMechanism:
    """Tests specifically for the retry mechanism."""
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    @patch('app.services.data_collector_service.time.sleep')
    def test_retry_interval(
        self,
        mock_sleep,
        mock_settings,
        mock_get,
        db_session,
        mock_weather_response,
        mock_air_pollution_response
    ):
        """Test that retry interval is 60 seconds."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        # First call fails, second succeeds
        mock_fail = Mock()
        mock_fail.raise_for_status = Mock(side_effect=Exception("API Error"))
        
        mock_success = Mock()
        mock_success.json.return_value = mock_weather_response
        mock_success.raise_for_status = Mock()
        
        mock_air = Mock()
        mock_air.json.return_value = mock_air_pollution_response
        mock_air.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_fail, mock_success, mock_air]
        
        service = DataCollectorService(db_session)
        service.collect_weather_data(
            location="Test Location",
            lat=10.0,
            lon=106.0
        )
        
        # Verify sleep was called with 60 seconds
        mock_sleep.assert_called_with(60)
    
    @patch('app.services.data_collector_service.requests.get')
    @patch('app.services.data_collector_service.settings')
    @patch('app.services.data_collector_service.time.sleep')
    def test_max_retries_is_three(
        self,
        mock_sleep,
        mock_settings,
        mock_get,
        db_session
    ):
        """Test that maximum retries is 3."""
        mock_settings.OPENWEATHER_API_KEY = "test_api_key"
        
        mock_fail = Mock()
        mock_fail.raise_for_status = Mock(side_effect=Exception("API Error"))
        mock_get.return_value = mock_fail
        
        service = DataCollectorService(db_session)
        service.collect_weather_data(
            location="Test Location",
            lat=10.0,
            lon=106.0
        )
        
        # Verify exactly 3 attempts were made
        assert mock_get.call_count == 3
        
        # Verify exactly 2 sleep calls (between 3 attempts)
        assert mock_sleep.call_count == 2
