"""
Unit tests for ForecastingPipeline

Tests the complete forecasting pipeline including data retrieval,
feature engineering, model training, forecast generation, and automatic retraining.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from .forecasting_pipeline import ForecastingPipeline
from .config import DISEASE_TYPES
from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.models.disease_forecast import DiseaseForecast


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_disease_cases():
    """Create sample disease case data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    cases = []
    
    for date in dates:
        case = Mock(spec=DiseaseCase)
        case.recorded_at = date
        case.disease_type = 'dengue_fever'
        case.case_count = np.random.randint(50, 150)
        case.location = 'Test Location'
        case.severity = 'medium'
        case.data_source = 'test'
        cases.append(case)
    
    return cases


@pytest.fixture
def sample_environmental_data():
    """Create sample environmental data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    env_data = []
    
    for date in dates:
        env = Mock(spec=EnvironmentalData)
        env.recorded_at = date
        env.location = 'Test Location'
        env.temperature = 30.0 + np.random.randn() * 2
        env.humidity = 75.0 + np.random.randn() * 5
        env.rainfall = 5.0 + np.random.randn() * 2
        env.air_quality_index = 100 + np.random.randint(-20, 20)
        env.data_source = 'test'
        env_data.append(env)
    
    return env_data


class TestForecastingPipelineInitialization:
    """Test ForecastingPipeline initialization."""
    
    def test_init_with_valid_disease_type(self, mock_db_session):
        """Test initialization with valid disease type."""
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        assert pipeline.disease_type == 'dengue_fever'
        assert pipeline.use_ensemble is True
        assert pipeline.ensemble_forecaster is not None
        assert pipeline.original_training_size is None
        assert pipeline.last_training_date is None
    
    def test_init_with_invalid_disease_type(self, mock_db_session):
        """Test initialization with invalid disease type."""
        with pytest.raises(ValueError, match="Invalid disease type"):
            ForecastingPipeline(
                db=mock_db_session,
                disease_type='invalid_disease'
            )
    
    def test_init_with_single_model(self, mock_db_session):
        """Test initialization with single model (not ensemble)."""
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever',
            use_ensemble=False
        )
        
        assert pipeline.use_ensemble is False
        assert pipeline.xgboost_forecaster is not None
        assert pipeline.forecaster == pipeline.xgboost_forecaster
    
    def test_init_with_ensemble_model(self, mock_db_session):
        """Test initialization with ensemble model."""
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='seasonal_flu',
            use_ensemble=True
        )
        
        assert pipeline.use_ensemble is True
        assert pipeline.ensemble_forecaster is not None
        assert pipeline.forecaster == pipeline.ensemble_forecaster


class TestDataRetrieval:
    """Test data retrieval from database."""
    
    def test_retrieve_historical_data_success(
        self,
        mock_db_session,
        sample_disease_cases,
        sample_environmental_data
    ):
        """Test successful data retrieval."""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.side_effect = [sample_disease_cases, sample_environmental_data]
        
        mock_db_session.query.return_value = mock_query
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Retrieve data
        disease_df, env_df = pipeline.retrieve_historical_data(min_days=90)
        
        # Assertions
        assert len(disease_df) == 100
        assert len(env_df) == 100
        assert 'recorded_at' in disease_df.columns
        assert 'case_count' in disease_df.columns
        assert 'temperature' in env_df.columns
        assert 'humidity' in env_df.columns
    
    def test_retrieve_historical_data_insufficient_data(
        self,
        mock_db_session
    ):
        """Test data retrieval with insufficient data."""
        # Setup mock query with insufficient data
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []  # No data
        
        mock_db_session.query.return_value = mock_query
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Insufficient historical data"):
            pipeline.retrieve_historical_data(min_days=90)
    
    def test_retrieve_historical_data_with_location_filter(
        self,
        mock_db_session,
        sample_disease_cases,
        sample_environmental_data
    ):
        """Test data retrieval with location filter."""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.side_effect = [sample_disease_cases, sample_environmental_data]
        
        mock_db_session.query.return_value = mock_query
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Retrieve data with location filter
        disease_df, env_df = pipeline.retrieve_historical_data(
            min_days=90,
            location='Test Location'
        )
        
        # Verify filter was called
        assert mock_query.filter.called
        assert len(disease_df) == 100


class TestFeatureEngineering:
    """Test feature engineering pipeline."""
    
    def test_engineer_features_success(self, mock_db_session):
        """Test successful feature engineering."""
        # Create sample data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        disease_df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=100),
            'location': 'Test Location'
        })
        
        env_df = pd.DataFrame({
            'recorded_at': dates,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(100) * 2,
            'humidity': 75.0 + np.random.randn(100) * 5,
            'rainfall': 5.0 + np.random.randn(100) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=100)
        })
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Engineer features
        features_df = pipeline.engineer_features(disease_df, env_df)
        
        # Assertions
        assert len(features_df) > 0
        assert 'case_count' in features_df.columns
        assert 'temperature' in features_df.columns
        # Check for lag features
        assert any('lag' in col for col in features_df.columns)
        # Check for rolling features
        assert any('rolling' in col for col in features_df.columns)


class TestModelTraining:
    """Test model training."""
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    def test_train_models_ensemble(
        self,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test training ensemble models."""
        # Setup mock data - need more samples due to lag features reducing sample count
        dates = pd.date_range(start='2024-01-01', periods=150, freq='D')
        disease_df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=150),
            'location': 'Test Location'
        })
        
        env_df = pd.DataFrame({
            'recorded_at': dates,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(150) * 2,
            'humidity': 75.0 + np.random.randn(150) * 5,
            'rainfall': 5.0 + np.random.randn(150) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=150)
        })
        
        mock_retrieve_data.return_value = (disease_df, env_df)
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever',
            use_ensemble=True
        )
        
        # Train models
        metrics = pipeline.train_models(min_days=90)
        
        # Assertions
        assert metrics is not None
        assert isinstance(metrics, dict)
        assert pipeline.original_training_size == 150
        assert pipeline.last_training_date is not None
        assert pipeline.ensemble_forecaster.is_trained


class TestForecastGeneration:
    """Test forecast generation."""
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline._check_and_retrain_if_needed')
    def test_generate_forecast_success(
        self,
        mock_retrain_check,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test successful forecast generation."""
        # Setup mock data - need more samples due to lag features
        dates = pd.date_range(start='2024-01-01', periods=150, freq='D')
        disease_df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=150),
            'location': 'Test Location'
        })
        
        env_df = pd.DataFrame({
            'recorded_at': dates,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(150) * 2,
            'humidity': 75.0 + np.random.randn(150) * 5,
            'rainfall': 5.0 + np.random.randn(150) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=150)
        })
        
        mock_retrieve_data.return_value = (disease_df, env_df)
        mock_retrain_check.return_value = False
        
        # Create and train pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever',
            use_ensemble=True
        )
        
        # Train first
        pipeline.train_models(min_days=90)
        
        # Generate forecast
        result = pipeline.generate_forecast(
            forecast_period_days=7,
            save_to_db=False
        )
        
        # Assertions
        assert result is not None
        assert 'forecast_dates' in result
        assert 'predictions' in result
        assert 'confidence_lower' in result
        assert 'confidence_upper' in result
        assert 'model_used' in result
        assert 'metrics' in result
        assert len(result['predictions']) == 7
    
    def test_generate_forecast_invalid_period(self, mock_db_session):
        """Test forecast generation with invalid period."""
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Should raise ValueError for invalid period
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            pipeline.generate_forecast(forecast_period_days=5)
        
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            pipeline.generate_forecast(forecast_period_days=35)


class TestAutomaticRetraining:
    """Test automatic model retraining."""
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    def test_retrain_triggered_when_threshold_exceeded(
        self,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test that retraining is triggered when data exceeds threshold."""
        # Setup initial data (150 samples)
        dates1 = pd.date_range(start='2024-01-01', periods=150, freq='D')
        disease_df1 = pd.DataFrame({
            'recorded_at': dates1,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=150),
            'location': 'Test Location'
        })
        
        env_df1 = pd.DataFrame({
            'recorded_at': dates1,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(150) * 2,
            'humidity': 75.0 + np.random.randn(150) * 5,
            'rainfall': 5.0 + np.random.randn(150) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=150)
        })
        
        # Setup new data (180 samples - 20% increase, exceeds 10% threshold)
        dates2 = pd.date_range(start='2024-01-01', periods=180, freq='D')
        disease_df2 = pd.DataFrame({
            'recorded_at': dates2,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=180),
            'location': 'Test Location'
        })
        
        env_df2 = pd.DataFrame({
            'recorded_at': dates2,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(180) * 2,
            'humidity': 75.0 + np.random.randn(180) * 5,
            'rainfall': 5.0 + np.random.randn(180) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=180)
        })
        
        # First call returns new data for retrain check
        mock_retrieve_data.return_value = (disease_df2, env_df2)
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Set original training size
        pipeline.original_training_size = 150
        
        # Check retrain
        retrained = pipeline._check_and_retrain_if_needed()
        
        # Assertions
        assert retrained is True
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    def test_retrain_not_triggered_when_below_threshold(
        self,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test that retraining is not triggered when data is below threshold."""
        # Setup data (105 samples - only 5% increase, below 10% threshold)
        dates = pd.date_range(start='2024-01-01', periods=105, freq='D')
        disease_df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=105),
            'location': 'Test Location'
        })
        
        env_df = pd.DataFrame({
            'recorded_at': dates,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(105) * 2,
            'humidity': 75.0 + np.random.randn(105) * 5,
            'rainfall': 5.0 + np.random.randn(105) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=105)
        })
        
        mock_retrieve_data.return_value = (disease_df, env_df)
        
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Set original training size
        pipeline.original_training_size = 100
        
        # Check retrain
        retrained = pipeline._check_and_retrain_if_needed()
        
        # Assertions
        assert retrained is False


class TestModelPersistence:
    """Test model loading and saving."""
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    def test_load_trained_models(
        self,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test loading trained models from disk."""
        # Setup mock data - need more samples due to lag features
        dates = pd.date_range(start='2024-01-01', periods=150, freq='D')
        disease_df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 150, size=150),
            'location': 'Test Location'
        })
        
        env_df = pd.DataFrame({
            'recorded_at': dates,
            'location': 'Test Location',
            'temperature': 30.0 + np.random.randn(150) * 2,
            'humidity': 75.0 + np.random.randn(150) * 5,
            'rainfall': 5.0 + np.random.randn(150) * 2,
            'air_quality_index': 100 + np.random.randint(-20, 20, size=150)
        })
        
        mock_retrieve_data.return_value = (disease_df, env_df)
        
        # Create and train pipeline
        pipeline1 = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever',
            use_ensemble=True
        )
        
        pipeline1.train_models(min_days=90)
        
        # Create new pipeline and load models
        pipeline2 = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever',
            use_ensemble=True
        )
        
        pipeline2.load_trained_models(version="latest")
        
        # Assertions
        assert pipeline2.ensemble_forecaster.is_trained


class TestErrorHandling:
    """Test error handling and logging."""
    
    def test_retrieve_data_error_handling(self, mock_db_session):
        """Test error handling in data retrieval."""
        # Setup mock to raise exception
        mock_db_session.query.side_effect = Exception("Database error")
        
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Should raise exception
        with pytest.raises(Exception, match="Database error"):
            pipeline.retrieve_historical_data(min_days=90)
    
    @patch('app.ai_engine.forecasting_pipeline.ForecastingPipeline.retrieve_historical_data')
    def test_train_models_error_handling(
        self,
        mock_retrieve_data,
        mock_db_session
    ):
        """Test error handling in model training."""
        # Setup mock to raise exception
        mock_retrieve_data.side_effect = Exception("Training error")
        
        pipeline = ForecastingPipeline(
            db=mock_db_session,
            disease_type='dengue_fever'
        )
        
        # Should raise exception
        with pytest.raises(Exception, match="Training error"):
            pipeline.train_models(min_days=90)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
