"""
Unit Tests for XGBoost Forecaster

This module contains comprehensive unit tests for the XGBoostForecaster class,
testing all functionality including training, prediction, saving/loading, and
feature importance.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

from .xgboost_forecaster import XGBoostForecaster
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
    """Create a trained XGBoost forecaster for testing."""
    forecaster = XGBoostForecaster(disease_type="dengue_fever")
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

class TestXGBoostForecasterInitialization:
    """Tests for XGBoostForecaster initialization."""
    
    def test_init_with_default_hyperparameters(self):
        """Test initialization with default hyperparameters."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        assert forecaster.disease_type == "dengue_fever"
        assert forecaster.is_trained is False
        assert forecaster.feature_columns is None
        assert forecaster.model is not None
        assert forecaster.hyperparameters is not None
    
    def test_init_with_custom_hyperparameters(self):
        """Test initialization with custom hyperparameters."""
        custom_params = {
            'n_estimators': 100,
            'max_depth': 3,
            'learning_rate': 0.1
        }
        
        forecaster = XGBoostForecaster(
            disease_type="seasonal_flu",
            hyperparameters=custom_params
        )
        
        assert forecaster.disease_type == "seasonal_flu"
        assert forecaster.hyperparameters['n_estimators'] == 100
        assert forecaster.hyperparameters['max_depth'] == 3
        assert forecaster.hyperparameters['learning_rate'] == 0.1


class TestFeaturePreparation:
    """Tests for feature preparation."""
    
    def test_prepare_features_without_environmental_data(self, sample_disease_cases_df):
        """Test feature preparation without environmental data."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        features_df = forecaster.prepare_features(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=None
        )
        
        assert len(features_df) > 0
        assert 'case_count' in features_df.columns
        assert 'case_count_lag_7' in features_df.columns
        assert 'case_count_rolling_7_mean' in features_df.columns
        assert 'month' in features_df.columns
        assert 'day_of_week' in features_df.columns
    
    def test_prepare_features_with_environmental_data(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test feature preparation with environmental data."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        features_df = forecaster.prepare_features(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert len(features_df) > 0
        assert 'temperature' in features_df.columns
        assert 'humidity' in features_df.columns
        assert 'rainfall' in features_df.columns
        assert 'air_quality_index' in features_df.columns
        assert 'temperature_x_humidity' in features_df.columns
    
    def test_prepare_features_handles_missing_values(self, sample_disease_cases_df):
        """Test that feature preparation handles missing values."""
        # Add some missing values
        df_with_nan = sample_disease_cases_df.copy()
        df_with_nan.loc[10:15, 'case_count'] = np.nan
        
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        features_df = forecaster.prepare_features(
            disease_cases_df=df_with_nan,
            environmental_df=None
        )
        
        # Check that NaN values are handled
        assert features_df['case_count'].isna().sum() == 0


class TestModelTraining:
    """Tests for model training."""
    
    def test_train_with_sufficient_data(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test training with sufficient data."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        metrics = forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert forecaster.is_trained is True
        assert forecaster.feature_columns is not None
        assert len(forecaster.feature_columns) > 0
        
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
        
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Insufficient training data"):
            forecaster.train(disease_cases_df=df)
    
    def test_train_without_environmental_data(self, sample_disease_cases_df):
        """Test training without environmental data."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        metrics = forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=None
        )
        
        assert forecaster.is_trained is True
        assert 'mae' in metrics
    
    def test_train_stores_feature_columns(
        self,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that training stores feature columns."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        forecaster.train(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df
        )
        
        assert forecaster.feature_columns is not None
        assert isinstance(forecaster.feature_columns, list)
        assert len(forecaster.feature_columns) > 0


class TestPrediction:
    """Tests for prediction functionality."""
    
    def test_predict_7_days(self, trained_forecaster, sample_disease_cases_df, sample_environmental_df):
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
    
    def test_predict_30_days(self, trained_forecaster, sample_disease_cases_df, sample_environmental_df):
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
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
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
            forecast_period_days=7,
            confidence_level=0.95
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
    
    def test_confidence_intervals_widen_appropriately(
        self,
        trained_forecaster,
        sample_disease_cases_df,
        sample_environmental_df
    ):
        """Test that confidence intervals are reasonable."""
        predictions, lower, upper, dates = trained_forecaster.predict_with_confidence(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        # Check that intervals have non-zero width
        interval_widths = upper - lower
        assert all(interval_widths > 0)


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
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
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
        new_forecaster = XGBoostForecaster(disease_type="dengue_fever")
        new_forecaster.load(version="test_v2")
        
        assert new_forecaster.is_trained is True
        assert new_forecaster.feature_columns == trained_forecaster.feature_columns
        assert new_forecaster.disease_type == trained_forecaster.disease_type
        
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
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        with pytest.raises(FileNotFoundError):
            forecaster.load(version="nonexistent_version")


class TestFeatureImportance:
    """Tests for feature importance."""
    
    def test_get_feature_importance(self, trained_forecaster):
        """Test getting feature importance."""
        importance_df = trained_forecaster.get_feature_importance(top_n=10)
        
        assert len(importance_df) <= 10
        assert 'feature' in importance_df.columns
        assert 'importance' in importance_df.columns
        
        # Check that importance scores are non-negative
        assert all(importance_df['importance'] >= 0)
        
        # Check that features are sorted by importance
        importance_values = importance_df['importance'].values
        assert all(importance_values[i] >= importance_values[i+1] 
                  for i in range(len(importance_values)-1))
    
    def test_get_feature_importance_untrained_raises_error(self):
        """Test that getting feature importance from untrained model raises error."""
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Model must be trained"):
            forecaster.get_feature_importance()


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
        
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
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
            forecaster = XGBoostForecaster(disease_type=disease_type)
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
        forecaster = XGBoostForecaster(disease_type="dengue_fever")
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
        new_forecaster = XGBoostForecaster(disease_type="dengue_fever")
        new_forecaster.load(version="integration_test")
        
        # Make predictions with loaded model
        predictions2, dates2 = new_forecaster.predict(
            disease_cases_df=sample_disease_cases_df,
            environmental_df=sample_environmental_df,
            forecast_period_days=7
        )
        
        # Predictions should be identical
        np.testing.assert_array_almost_equal(predictions1, predictions2)
        
        # Get feature importance
        importance = new_forecaster.get_feature_importance(top_n=5)
        assert len(importance) <= 5
        
        # Cleanup
        model_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
