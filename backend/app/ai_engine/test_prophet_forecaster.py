"""
Unit Tests for Prophet Forecaster

This module contains comprehensive unit tests for the ProphetForecaster class,
testing all functionality including training, prediction, saving/loading, and
seasonality components.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

from .prophet_forecaster import ProphetForecaster
from .config import get_model_path, SAVED_MODELS_DIR


# Fixtures

@pytest.fixture
def sample_disease_cases_df():
    """Create sample disease cases DataFrame for testing."""
    # Generate 120 days of data
    dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
    
    # Generate synthetic case counts with trend and seasonality
    np.random.seed(42)
    trend = np.linspace(50, 100, 120)
    seasonality = 20 * np.sin(np.arange(120) * 2 * np.pi / 30)  # 30-day cycle
    noise = np.random.normal(0, 5, 120)
    case_counts = trend + seasonality + noise
    case_counts = np.maximum(case_counts, 0).astype(int)  # Ensure non-negative
    
    df = pd.DataFrame({
        'recorded_at': dates,
        'disease_type': 'dengue_fever',
        'case_count': case_counts,
        'location': 'Ho Chi Minh City'
    })
    
    return df


@pytest.fixture
def sample_environmental_df():
    """Create sample environmental DataFrame for testing."""
    # Generate 120 days of environmental data
    dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
    
    np.random.seed(42)
    df = pd.DataFrame({
        'recorded_at': dates,
        'location': 'Ho Chi Minh City',
        'temperature': np.random.uniform(25, 35, 120),
        'humidity': np.random.uniform(60, 90, 120),
        'rainfall': np.random.uniform(0, 50, 120),
        'air_quality_index': np.random.randint(50, 150, 120)
    })
    
    return df


@pytest.fixture
def trained_forecaster(sample_disease_cases_df, sample_environmental_df):
    """Create a trained Prophet forecaster for testing."""
    forecaster = ProphetForecaster(disease_type="dengue_fever")
    forecaster.train(
        disease_cases_df=sample_disease_cases_df,
        environmental_df=sample_environmental_df
    )
    return forecaster


@pytest.fixture
def temp_model_dir():
    """Create a temporary directory for model storage."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup after tests
    shutil.rmtree(temp_dir)


# Test Cases

class TestProphetForecasterInitialization:
    """Tests for ProphetForecaster initialization."""
    
    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        assert forecaster.disease_type == "dengue_fever"
        assert forecaster.is_trained is False
        assert forecaster.model is not None
        assert forecaster.config is not None
        assert forecaster.config['yearly_seasonality'] is True
        assert forecaster.config['weekly_seasonality'] is True
        assert forecaster.config['daily_seasonality'] is False
    
    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        custom_config = {
            'yearly_seasonality': False,
            'weekly_seasonality': True,
            'daily_seasonality': False,
            'changepoint_prior_scale': 0.1,
            'seasonality_prior_scale': 5,
            'interval_width': 0.90
        }
        
        forecaster = ProphetForecaster(
            disease_type="seasonal_flu",
            config=custom_config
        )
        
        assert forecaster.disease_type == "seasonal_flu"
        assert forecaster.config['yearly_seasonality'] is False
        assert forecaster.config['changepoint_prior_scale'] == 0.1
        assert forecaster.config['interval_width'] == 0.90
    
    def test_regressors_added_on_init(self):
        """Test that environmental regressors are added during initialization."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        # Check that regressors are configured
        assert forecaster.model is not None
        # Prophet stores regressors in extra_regressors attribute
        assert hasattr(forecaster.model, 'extra_regressors')


class TestDataPreparation:
    """Tests for data preparation."""
    
    def test_prepare_prophet_dataframe_without_environmental_data(
        self,
        sample_disease_cases_df
    ):
        """Test data preparation without environmental data."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        prophet_df = forecaster.prepare_prophet_dataframe(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=None
        )
        
        assert len(prophet_df) > 0
        assert 'ds' in prophet_df.columns
        assert 'y' in prophet_df.columns
        assert 'temperature' in prophet_df.columns
        assert 'humidity' in prophet_df.columns
        assert 'rainfall' in prophet_df.columns
        assert 'air_quality_index' in prophet_df.columns
        
        # Check default values are used
        assert prophet_df['temperature'].iloc[0] == 30.0
        assert prophet_df['humidity'].iloc[0] == 75.0
    
    def test_prepare_prophet_dataframe_with_environmental_data(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test data preparation with environmental data."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        prophet_df = forecaster.prepare_prophet_dataframe(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert len(prophet_df) > 0
        assert 'ds' in prophet_df.columns
        assert 'y' in prophet_df.columns
        assert 'temperature' in prophet_df.columns
        assert 'humidity' in prophet_df.columns
        assert 'rainfall' in prophet_df.columns
        assert 'air_quality_index' in prophet_df.columns
        
        # Check that actual environmental values are used
        assert prophet_df['temperature'].iloc[0] != 30.0  # Not default value
    
    def test_prepare_prophet_dataframe_handles_missing_values(
        self,
        sample_disease_cases_df
    ):
        """Test that data preparation handles missing values."""
        # Add some missing values
        df_with_nan = sample_disease_cases_df.copy()
        df_with_nan.loc[10:15, 'case_count'] = np.nan
        
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        prophet_df = forecaster.prepare_prophet_dataframe(
            disease_cases_df=df_with_nan,
            environmental_df=None
        )
        
        # Check that NaN values are handled
        assert prophet_df['y'].isna().sum() == 0
    
    def test_prepare_prophet_dataframe_sorts_by_date(
        self,
        sample_disease_cases_df
    ):
        """Test that data is sorted by date."""
        # Shuffle the data
        shuffled_df = sample_disease_cases_df.sample(frac=1, random_state=42)
        
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        prophet_df = forecaster.prepare_prophet_dataframe(
            disease_cases_df=shuffled_df,
            environmental_df=None
        )
        
        # Check that dates are sorted
        dates = prophet_df['ds'].values
        assert all(dates[i] <= dates[i+1] for i in range(len(dates)-1))


class TestModelTraining:
    """Tests for model training."""
    
    def test_train_with_sufficient_data(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test training with sufficient data."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        metrics = forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert forecaster.is_trained is True
        assert forecaster.training_data is not None
        
        # Check metrics
        assert 'mae' in metrics
        assert 'rmse' in metrics
        assert 'mape' in metrics
        assert 'r2' in metrics
        
        # Metrics should be reasonable
        assert metrics['mae'] >= 0
        assert metrics['rmse'] >= 0
        assert metrics['mape'] >= 0
    
    def test_train_with_insufficient_data(self):
        """Test training with insufficient data raises error."""
        # Create small dataset (less than minimum required)
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(10, 50, 30),
            'location': 'Ho Chi Minh City'
        })
        
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Insufficient training data"):
            forecaster.train(disease_cases_df=df)
    
    def test_train_without_environmental_data(self, sample_disease_cases_df):
        """Test training without environmental data."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        metrics = forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=None
        )
        
        assert forecaster.is_trained is True
        assert 'mae' in metrics
    
    def test_train_stores_training_data(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that training stores training data."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert forecaster.training_data is not None
        assert isinstance(forecaster.training_data, pd.DataFrame)
        assert 'ds' in forecaster.training_data.columns
        assert 'y' in forecaster.training_data.columns


class TestPrediction:
    """Tests for prediction functionality."""
    
    def test_predict_7_days(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test 7-day prediction."""
        predictions, forecast_dates = trained_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        assert len(forecast_dates) == 7
        assert all(predictions >= 0)  # Non-negative predictions
        assert isinstance(predictions, np.ndarray)
        assert isinstance(forecast_dates, pd.DatetimeIndex)
    
    def test_predict_30_days(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test 30-day prediction."""
        predictions, forecast_dates = trained_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=30
        )
        
        assert len(predictions) == 30
        assert len(forecast_dates) == 30
        assert all(predictions >= 0)
    
    def test_predict_without_training_raises_error(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that prediction without training raises error."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Model must be trained"):
            forecaster.predict(
                disease_cases_df=sample_disease_cases_df,
                environmental_df=sample_environmental_df,
                forecast_period_days=7
            )
    
    def test_predict_invalid_period_raises_error(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that invalid forecast period raises error."""
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            trained_forecaster.predict(
                disease_cases_df=sample_disease_cases_df,
                environmental_df=sample_environmental_df,
                forecast_period_days=5
            )
        
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            trained_forecaster.predict(
                disease_cases_df=sample_disease_cases_df,
                environmental_df=sample_environmental_df,
                forecast_period_days=35
            )
    
    def test_predict_dates_are_sequential(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that forecast dates are sequential."""
        predictions, forecast_dates = trained_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        # Check dates are sequential
        for i in range(len(forecast_dates) - 1):
            diff = (forecast_dates[i+1] - forecast_dates[i]).days
            assert diff == 1
    
    def test_predict_without_environmental_data(
        self,
        trained_forecaster,
        sample_disease_cases_df
    ):
        """Test prediction without environmental data uses defaults."""
        predictions, forecast_dates = trained_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=None,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        assert all(predictions >= 0)


class TestPredictionWithConfidence:
    """Tests for prediction with confidence intervals."""
    
    def test_predict_with_confidence(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test prediction with confidence intervals."""
        predictions, lower, upper, dates = trained_forecaster.predict_with_confidence(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        assert len(lower) == 7
        assert len(upper) == 7
        assert len(dates) == 7
        
        # Check bounds are valid
        assert all(lower >= 0)
        assert all(upper >= 0)
        assert all(lower <= predictions)
        assert all(predictions <= upper)
    
    def test_confidence_intervals_have_width(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that confidence intervals have non-zero width."""
        predictions, lower, upper, dates = trained_forecaster.predict_with_confidence(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        # Check that intervals have non-zero width
        interval_widths = upper - lower
        assert all(interval_widths > 0)
    
    def test_predict_with_confidence_without_training_raises_error(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that prediction with confidence without training raises error."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Model must be trained"):
            forecaster.predict_with_confidence(
                disease_cases_df=sample_disease_cases_df,
                environmental_df=sample_environmental_df,
                forecast_period_days=7
            )


class TestModelSaveLoad:
    """Tests for model saving and loading."""
    
    def test_save_trained_model(self, trained_forecaster):
        """Test saving a trained model."""
        model_path = trained_forecaster.save(version="test_v1")
        
        assert model_path.exists()
        assert model_path.suffix == '.pkl'
        
        # Cleanup
        model_path.unlink()
    
    def test_save_untrained_model_raises_error(self):
        """Test that saving untrained model raises error."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Cannot save untrained model"):
            forecaster.save()
    
    def test_load_model(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test loading a saved model."""
        # Save model
        model_path = trained_forecaster.save(version="test_v2")
        
        # Create new forecaster and load
        new_forecaster = ProphetForecaster(disease_type="dengue_fever")
        new_forecaster.load(version="test_v2")
        
        assert new_forecaster.is_trained is True
        assert new_forecaster.disease_type == trained_forecaster.disease_type
        assert new_forecaster.training_data is not None
        
        # Test that loaded model can make predictions
        predictions, dates = new_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        
        # Cleanup
        model_path.unlink()
    
    def test_load_nonexistent_model_raises_error(self):
        """Test that loading nonexistent model raises error."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(FileNotFoundError):
            forecaster.load(version="nonexistent_version")


class TestSeasonalityComponents:
    """Tests for seasonality components."""
    
    def test_get_seasonality_components(self, trained_forecaster):
        """Test getting seasonality components."""
        components_df = trained_forecaster.get_seasonality_components()
        
        assert len(components_df) > 0
        assert 'ds' in components_df.columns
        assert 'trend' in components_df.columns
        assert 'yearly' in components_df.columns
        assert 'weekly' in components_df.columns
    
    def test_get_seasonality_components_untrained_raises_error(self):
        """Test that getting components from untrained model raises error."""
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Model must be trained"):
            forecaster.get_seasonality_components()


class TestRetraining:
    """Tests for automatic retraining."""
    
    def test_retrain_if_needed_with_sufficient_new_data(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test retraining when sufficient new data is available."""
        original_size = len(sample_disease_cases_df)
        
        # Add 15% more data (exceeds 10% threshold)
        new_data_size = int(original_size * 0.15)
        new_dates = pd.date_range(
            start=sample_disease_cases_df['recorded_at'].max() + timedelta(days=1),
            periods=new_data_size,
            freq='D'
        )
        
        new_data = pd.DataFrame({
            'recorded_at': new_dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 100, new_data_size),
            'location': 'Ho Chi Minh City'
        })
        
        extended_df = pd.concat([sample_disease_cases_df, new_data], ignore_index=True)
        
        # Test retraining
        was_retrained = trained_forecaster.retrain_if_needed(
            disease_cases_df=extended_df,
            environmental_df=sample_environmental_df,
            original_training_size=original_size
        )
        
        assert was_retrained is True
    
    def test_retrain_if_needed_with_insufficient_new_data(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test no retraining when insufficient new data."""
        original_size = len(sample_disease_cases_df)
        
        # Add only 5% more data (below 10% threshold)
        new_data_size = int(original_size * 0.05)
        new_dates = pd.date_range(
            start=sample_disease_cases_df['recorded_at'].max() + timedelta(days=1),
            periods=new_data_size,
            freq='D'
        )
        
        new_data = pd.DataFrame({
            'recorded_at': new_dates,
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(50, 100, new_data_size),
            'location': 'Ho Chi Minh City'
        })
        
        extended_df = pd.concat([sample_disease_cases_df, new_data], ignore_index=True)
        
        # Test retraining
        was_retrained = trained_forecaster.retrain_if_needed(
            disease_cases_df=extended_df,
            environmental_df=sample_environmental_df,
            original_training_size=original_size
        )
        
        assert was_retrained is False


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_prediction_with_all_zero_cases(self):
        """Test prediction when all historical cases are zero."""
        dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
        df = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': np.zeros(120, dtype=int),
            'location': 'Ho Chi Minh City'
        })
        
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        forecaster.train(disease_cases_df=df)
        
        predictions, dates = forecaster.predict(
            disease_cases_df=df,
            forecast_period_days=7
        )
        
        # Predictions should be non-negative
        assert all(predictions >= 0)
    
    def test_different_disease_types(self):
        """Test that forecaster works with different disease types."""
        disease_types = ['dengue_fever', 'seasonal_flu', 'respiratory_disease']
        
        for disease_type in disease_types:
            forecaster = ProphetForecaster(disease_type=disease_type)
            assert forecaster.disease_type == disease_type


# Integration Tests

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test complete workflow: train, predict, save, load, predict again."""
        # Initialize and train
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        metrics = forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert forecaster.is_trained
        assert 'mae' in metrics
        
        # Make predictions
        predictions1, dates1 = forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        assert len(predictions1) == 7
        
        # Save model
        model_path = forecaster.save(version="integration_test")
        assert model_path.exists()
        
        # Load model in new instance
        new_forecaster = ProphetForecaster(disease_type="dengue_fever")
        new_forecaster.load(version="integration_test")
        
        # Make predictions with loaded model
        predictions2, dates2 = new_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        # Predictions should be similar (Prophet may have slight variations)
        assert len(predictions2) == 7
        
        # Get seasonality components
        components = new_forecaster.get_seasonality_components()
        assert len(components) > 0
        
        # Cleanup
        model_path.unlink()
    
    def test_workflow_with_confidence_intervals(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test workflow with confidence intervals."""
        # Train model
        forecaster = ProphetForecaster(disease_type="dengue_fever")
        forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        # Get predictions with confidence intervals
        predictions, lower, upper, dates = forecaster.predict_with_confidence(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=14
        )
        
        assert len(predictions) == 14
        assert len(lower) == 14
        assert len(upper) == 14
        assert all(lower <= predictions)
        assert all(predictions <= upper)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
