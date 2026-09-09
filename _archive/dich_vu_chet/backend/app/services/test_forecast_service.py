"""Unit tests for forecast service."""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.forecast_service import ForecastService
from app.models.disease_forecast import DiseaseForecast
from app.schemas.base import DiseaseType


class TestForecastService:
    """Test cases for ForecastService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def forecast_service(self, mock_db):
        """Create a ForecastService instance with mock db."""
        return ForecastService(mock_db)
    
    @pytest.fixture
    def sample_forecast(self):
        """Create a sample forecast object."""
        return DiseaseForecast(
            id=1,
            forecast_date=date.today() + timedelta(days=1),
            disease_type="dengue_fever",
            predicted_cases=100,
            confidence_lower=80,
            confidence_upper=120,
            model_used="ensemble",
            model_accuracy_mae=5.2,
            model_accuracy_rmse=7.8,
            model_accuracy_mape=4.5,
            forecast_period_days=7,
            created_at=datetime.now()
        )
    
    def test_get_forecast_by_id_found(self, forecast_service, mock_db, sample_forecast):
        """Test getting a forecast by ID when it exists."""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = sample_forecast
        
        # Act
        result = forecast_service.get_forecast_by_id(1)
        
        # Assert
        assert result == sample_forecast
        mock_db.query.assert_called_once_with(DiseaseForecast)
    
    def test_get_forecast_by_id_not_found(self, forecast_service, mock_db):
        """Test getting a forecast by ID when it doesn't exist."""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        
        # Act
        result = forecast_service.get_forecast_by_id(999)
        
        # Assert
        assert result is None
    
    def test_get_forecasts_with_filters(self, forecast_service, mock_db, sample_forecast):
        """Test getting forecasts with filters applied."""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_forecast]
        
        # Act
        result = forecast_service.get_forecasts(
            disease_type=DiseaseType.DENGUE_FEVER,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            limit=10,
            offset=0
        )
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_forecast
    
    def test_get_latest_forecast(self, forecast_service, mock_db, sample_forecast):
        """Test getting the latest forecast for a disease type."""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = sample_forecast
        
        # Act
        result = forecast_service.get_latest_forecast(DiseaseType.DENGUE_FEVER)
        
        # Assert
        assert result == sample_forecast
    
    def test_get_accuracy_metrics_with_data(self, forecast_service, mock_db):
        """Test getting accuracy metrics when forecasts exist."""
        # Arrange
        forecasts = [
            DiseaseForecast(
                id=1,
                forecast_date=date.today(),
                disease_type="dengue_fever",
                predicted_cases=100,
                model_accuracy_mae=5.0,
                model_accuracy_rmse=7.0,
                model_accuracy_mape=4.0,
                created_at=datetime.now()
            ),
            DiseaseForecast(
                id=2,
                forecast_date=date.today() + timedelta(days=1),
                disease_type="dengue_fever",
                predicted_cases=110,
                model_accuracy_mae=6.0,
                model_accuracy_rmse=8.0,
                model_accuracy_mape=5.0,
                created_at=datetime.now()
            )
        ]
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = forecasts
        
        # Act
        result = forecast_service.get_accuracy_metrics(
            disease_type=DiseaseType.DENGUE_FEVER
        )
        
        # Assert
        assert result["count"] == 2
        assert result["mae"] == 5.5  # Average of 5.0 and 6.0
        assert result["rmse"] == 7.5  # Average of 7.0 and 8.0
        assert result["mape"] == 4.5  # Average of 4.0 and 5.0
        assert result["disease_type"] == "dengue_fever"
    
    def test_get_accuracy_metrics_no_data(self, forecast_service, mock_db):
        """Test getting accuracy metrics when no forecasts exist."""
        # Arrange
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        result = forecast_service.get_accuracy_metrics(
            disease_type=DiseaseType.DENGUE_FEVER
        )
        
        # Assert
        assert result["count"] == 0
        assert result["mae"] is None
        assert result["rmse"] is None
        assert result["mape"] is None
    
    @patch('app.services.forecast_service.ForecastingPipeline')
    def test_generate_forecast_success(self, mock_pipeline_class, forecast_service, mock_db):
        """Test successful forecast generation."""
        # Arrange
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_pipeline.load_trained_models.return_value = None
        mock_pipeline.generate_forecast.return_value = {
            'forecast_dates': [date.today() + timedelta(days=i) for i in range(1, 8)],
            'predictions': [100, 105, 110, 108, 112, 115, 118],
            'confidence_lower': [80, 85, 90, 88, 92, 95, 98],
            'confidence_upper': [120, 125, 130, 128, 132, 135, 138],
            'model_used': 'ensemble',
            'metrics': {'mae': 5.2, 'rmse': 7.8, 'mape': 4.5},
            'forecast_period_days': 7,
            'disease_type': 'dengue_fever'
        }
        
        # Act
        result = forecast_service.generate_forecast(
            disease_type=DiseaseType.DENGUE_FEVER,
            forecast_period_days=7
        )
        
        # Assert
        assert result is not None
        assert result['disease_type'] == 'dengue_fever'
        assert result['forecast_period_days'] == 7
        assert len(result['predictions']) == 7
        mock_pipeline.load_trained_models.assert_called_once()
        mock_pipeline.generate_forecast.assert_called_once()
    
    @patch('app.services.forecast_service.ForecastingPipeline')
    def test_generate_forecast_trains_if_no_models(self, mock_pipeline_class, forecast_service, mock_db):
        """Test forecast generation trains models if none exist."""
        # Arrange
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Simulate no existing models
        mock_pipeline.load_trained_models.side_effect = FileNotFoundError("No models found")
        mock_pipeline.train_models.return_value = {'mae': 5.0, 'rmse': 7.0, 'mape': 4.0}
        mock_pipeline.generate_forecast.return_value = {
            'forecast_dates': [date.today() + timedelta(days=i) for i in range(1, 8)],
            'predictions': [100, 105, 110, 108, 112, 115, 118],
            'confidence_lower': [80, 85, 90, 88, 92, 95, 98],
            'confidence_upper': [120, 125, 130, 128, 132, 135, 138],
            'model_used': 'ensemble',
            'metrics': {'mae': 5.2, 'rmse': 7.8, 'mape': 4.5},
            'forecast_period_days': 7,
            'disease_type': 'dengue_fever'
        }
        
        # Act
        result = forecast_service.generate_forecast(
            disease_type=DiseaseType.DENGUE_FEVER,
            forecast_period_days=7
        )
        
        # Assert
        assert result is not None
        mock_pipeline.load_trained_models.assert_called_once()
        mock_pipeline.train_models.assert_called_once()
        mock_pipeline.generate_forecast.assert_called_once()
    
    def test_get_supply_requirements_for_forecast(self, forecast_service, mock_db):
        """Test getting supply requirements for a forecast."""
        # Arrange
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        
        mock_supply = MedicalSupply(
            id=1,
            name="Surgical Masks",
            category="PPE",
            unit="box"
        )
        
        mock_requirement = SupplyRequirement(
            id=1,
            forecast_id=1,
            supply_id=1,
            required_quantity=200,
            requirement_date=date.today() + timedelta(days=1),
            disease_type="dengue_fever"
        )
        
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        
        # First query for requirements
        mock_query.filter.return_value.all.return_value = [mock_requirement]
        # Second query for supply details
        mock_query.filter.return_value.first.return_value = mock_supply
        
        # Act
        result = forecast_service.get_supply_requirements_for_forecast(1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["supply_id"] == 1
        assert result[0]["supply_name"] == "Surgical Masks"
        assert result[0]["required_quantity"] == 200
