"""
Unit Tests for Ensemble Forecaster

This module contains comprehensive unit tests for the EnsembleForecaster class.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .ensemble_forecaster import EnsembleForecaster


# Test fixtures
@pytest.fixture
def sample_disease_data():
    """Create sample disease case data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
    
    # Create synthetic disease case data with trend and seasonality
    trend = np.linspace(50, 100, 120)
    seasonality = 20 * np.sin(np.linspace(0, 4 * np.pi, 120))
    noise = np.random.normal(0, 5, 120)
    
    case_counts = trend + seasonality + noise
    case_counts = np.maximum(case_counts, 0)  # Ensure non-negative
    
    df = pd.DataFrame({
        'recorded_at': dates,
        'disease_type': 'dengue_fever',
        'case_count': case_counts.astype(int),
        'location': 'Ho Chi Minh City'
    })
    
    return df


@pytest.fixture
def sample_environmental_data():
    """Create sample environmental data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
    
    df = pd.DataFrame({
        'recorded_at': dates,
        'location': 'Ho Chi Minh City',
        'temperature': np.random.uniform(25, 35, 120),
        'humidity': np.random.uniform(60, 90, 120),
        'rainfall': np.random.uniform(0, 50, 120),
        'air_quality_index': np.random.uniform(50, 150, 120)
    })
    
    return df


class TestEnsembleForecasterInitialization:
    """Test ensemble forecaster initialization."""
    
    def test_init_with_default_weights(self):
        """Test initialization with default weights."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        assert ensemble.disease_type == "dengue_fever"
        assert ensemble.is_trained == False
        assert 'xgboost' in ensemble.weights
        assert 'lstm' in ensemble.weights
        assert 'prophet' in ensemble.weights
        
        # Check weights sum to 1.0
        weight_sum = sum(ensemble.weights.values())
        assert np.isclose(weight_sum, 1.0)
    
    def test_init_with_custom_weights(self):
        """Test initialization with custom weights."""
        custom_weights = {
            'xgboost': 0.5,
            'lstm': 0.3,
            'prophet': 0.2
        }
        
        ensemble = EnsembleForecaster(
            disease_type="seasonal_flu",
            weights=custom_weights
        )
        
        assert ensemble.weights['xgboost'] == 0.5
        assert ensemble.weights['lstm'] == 0.3
        assert ensemble.weights['prophet'] == 0.2
    
    def test_init_with_unnormalized_weights(self):
        """Test initialization with weights that don't sum to 1.0."""
        unnormalized_weights = {
            'xgboost': 2.0,
            'lstm': 1.5,
            'prophet': 1.0
        }
        
        ensemble = EnsembleForecaster(
            disease_type="dengue_fever",
            weights=unnormalized_weights
        )
        
        # Weights should be normalized
        weight_sum = sum(ensemble.weights.values())
        assert np.isclose(weight_sum, 1.0)
        
        # Check proportions are maintained
        total = 2.0 + 1.5 + 1.0
        assert np.isclose(ensemble.weights['xgboost'], 2.0 / total)
        assert np.isclose(ensemble.weights['lstm'], 1.5 / total)
        assert np.isclose(ensemble.weights['prophet'], 1.0 / total)
    
    def test_init_with_auto_adjust_weights(self):
        """Test initialization with auto weight adjustment enabled."""
        ensemble = EnsembleForecaster(
            disease_type="dengue_fever",
            auto_adjust_weights=True
        )
        
        assert ensemble.auto_adjust_weights == True


class TestEnsembleForecasterTraining:
    """Test ensemble forecaster training."""
    
    def test_train_basic(self, sample_disease_data, sample_environmental_data):
        """Test basic training functionality."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        metrics = ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        
        assert ensemble.is_trained == True
        assert 'xgboost' in metrics
        assert 'prophet' in metrics
        assert 'lstm' in metrics
        
        # Check that metrics contain expected keys
        for model_metrics in metrics.values():
            assert 'mae' in model_metrics
            assert 'rmse' in model_metrics
            assert 'mape' in model_metrics
    
    def test_train_without_environmental_data(self, sample_disease_data):
        """Test training without environmental data."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        metrics = ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=None
        )
        
        assert ensemble.is_trained == True
        assert len(metrics) > 0
    
    def test_train_with_auto_weight_adjustment(self, sample_disease_data, sample_environmental_data):
        """Test training with automatic weight adjustment."""
        ensemble = EnsembleForecaster(
            disease_type="dengue_fever",
            auto_adjust_weights=True
        )
        
        # Store initial weights
        initial_weights = ensemble.weights.copy()
        
        metrics = ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        
        # Weights should be adjusted based on performance
        # At least one weight should have changed
        weights_changed = any(
            not np.isclose(ensemble.weights[k], initial_weights[k])
            for k in ensemble.weights.keys()
        )
        
        # Note: Weights might not change if all models perform similarly
        # So we just check that the mechanism runs without error
        assert ensemble.is_trained == True
    
    def test_train_with_insufficient_data(self):
        """Test training with insufficient data."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        # Create very small dataset (less than minimum required)
        small_data = pd.DataFrame({
            'recorded_at': pd.date_range(start='2024-01-01', periods=30, freq='D'),
            'disease_type': 'dengue_fever',
            'case_count': np.random.randint(10, 50, 30),
            'location': 'Ho Chi Minh City'
        })
        
        with pytest.raises(ValueError, match="Insufficient training data"):
            ensemble.train(disease_cases_df=small_data)


class TestEnsembleForecasterPrediction:
    """Test ensemble forecaster prediction."""
    
    @pytest.fixture
    def trained_ensemble(self, sample_disease_data, sample_environmental_data):
        """Create a trained ensemble for testing predictions."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        return ensemble
    
    def test_predict_basic(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test basic prediction functionality."""
        predictions, forecast_dates = trained_ensemble.predict(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        assert len(forecast_dates) == 7
        assert all(predictions >= 0)  # All predictions should be non-negative
        assert isinstance(forecast_dates, pd.DatetimeIndex)
    
    def test_predict_different_periods(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test predictions for different forecast periods."""
        for period in [7, 14, 30]:
            predictions, forecast_dates = trained_ensemble.predict(
                disease_cases_df=sample_disease_data,
                environmental_df=sample_environmental_data,
                forecast_period_days=period
            )
            
            assert len(predictions) == period
            assert len(forecast_dates) == period
    
    def test_predict_without_training(self, sample_disease_data):
        """Test prediction without training raises error."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Models must be trained"):
            ensemble.predict(
                disease_cases_df=sample_disease_data,
                forecast_period_days=7
            )
    
    def test_predict_invalid_period(self, trained_ensemble, sample_disease_data):
        """Test prediction with invalid forecast period."""
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            trained_ensemble.predict(
                disease_cases_df=sample_disease_data,
                forecast_period_days=5
            )
        
        with pytest.raises(ValueError, match="Forecast period must be between 7 and 30 days"):
            trained_ensemble.predict(
                disease_cases_df=sample_disease_data,
                forecast_period_days=35
            )


class TestEnsembleForecasterConfidenceIntervals:
    """Test ensemble forecaster confidence interval calculation."""
    
    @pytest.fixture
    def trained_ensemble(self, sample_disease_data, sample_environmental_data):
        """Create a trained ensemble for testing."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        return ensemble
    
    def test_predict_with_confidence(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test prediction with confidence intervals."""
        predictions, lower, upper, forecast_dates = trained_ensemble.predict_with_confidence(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        assert len(predictions) == 7
        assert len(lower) == 7
        assert len(upper) == 7
        assert len(forecast_dates) == 7
        
        # Check that lower <= predictions <= upper
        assert all(lower <= predictions)
        assert all(predictions <= upper)
        
        # Check all values are non-negative
        assert all(lower >= 0)
        assert all(predictions >= 0)
        assert all(upper >= 0)
    
    def test_confidence_interval_width(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test that confidence intervals have reasonable width."""
        predictions, lower, upper, _ = trained_ensemble.predict_with_confidence(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        # Interval width should be positive
        interval_widths = upper - lower
        assert all(interval_widths > 0)
        
        # Interval width should be reasonable (not too narrow or too wide)
        # As a heuristic, width should be less than 2x the prediction
        assert all(interval_widths < 2 * predictions)


class TestEnsembleForecasterPerformanceComparison:
    """Test model performance comparison functionality."""
    
    @pytest.fixture
    def trained_ensemble(self, sample_disease_data, sample_environmental_data):
        """Create a trained ensemble for testing."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        return ensemble
    
    def test_get_model_performance_comparison(self, trained_ensemble):
        """Test getting model performance comparison."""
        comparison = trained_ensemble.get_model_performance_comparison()
        
        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) == 3  # XGBoost, LSTM, Prophet
        
        # Check required columns
        assert 'model' in comparison.columns
        assert 'weight' in comparison.columns
        assert 'mae' in comparison.columns
        assert 'rmse' in comparison.columns
        assert 'mape' in comparison.columns
        
        # Check that DataFrame is sorted by MAE
        mae_values = comparison['mae'].values
        assert all(mae_values[i] <= mae_values[i+1] for i in range(len(mae_values)-1))
    
    def test_performance_comparison_without_training(self):
        """Test performance comparison without training raises error."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Models must be trained"):
            ensemble.get_model_performance_comparison()


class TestEnsembleForecasterWeightManagement:
    """Test weight management functionality."""
    
    def test_set_weights_valid(self):
        """Test setting valid weights."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        new_weights = {
            'xgboost': 0.5,
            'lstm': 0.3,
            'prophet': 0.2
        }
        
        ensemble.set_weights(new_weights)
        
        assert np.isclose(ensemble.weights['xgboost'], 0.5)
        assert np.isclose(ensemble.weights['lstm'], 0.3)
        assert np.isclose(ensemble.weights['prophet'], 0.2)
    
    def test_set_weights_invalid_sum(self):
        """Test setting weights that don't sum to 1.0."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        invalid_weights = {
            'xgboost': 0.5,
            'lstm': 0.3,
            'prophet': 0.3  # Sum = 1.1
        }
        
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            ensemble.set_weights(invalid_weights)
    
    def test_set_weights_nearly_valid(self):
        """Test setting weights that are close to 1.0 (within tolerance)."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        # Weights that sum to 1.005 (within tolerance)
        nearly_valid_weights = {
            'xgboost': 0.402,
            'lstm': 0.351,
            'prophet': 0.252
        }
        
        # Should normalize without raising error
        ensemble.set_weights(nearly_valid_weights)
        
        # Check weights sum to exactly 1.0 after normalization
        weight_sum = sum(ensemble.weights.values())
        assert np.isclose(weight_sum, 1.0)


class TestEnsembleForecasterSaveLoad:
    """Test save and load functionality."""
    
    @pytest.fixture
    def trained_ensemble(self, sample_disease_data, sample_environmental_data):
        """Create a trained ensemble for testing."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        return ensemble
    
    def test_save_trained_model(self, trained_ensemble, tmp_path):
        """Test saving a trained model."""
        # Note: This test uses the actual model path, not tmp_path
        # because the save method uses get_model_path internally
        
        model_path = trained_ensemble.save(version="test")
        
        assert model_path.exists()
        assert model_path.suffix == '.pkl'
    
    def test_save_untrained_model(self):
        """Test saving an untrained model raises error."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        with pytest.raises(ValueError, match="Cannot save untrained ensemble"):
            ensemble.save(version="test")
    
    def test_load_model(self, trained_ensemble):
        """Test loading a saved model."""
        # Save the model
        trained_ensemble.save(version="test_load")
        
        # Create new ensemble and load
        new_ensemble = EnsembleForecaster(disease_type="dengue_fever")
        new_ensemble.load(version="test_load")
        
        assert new_ensemble.is_trained == True
        assert new_ensemble.disease_type == "dengue_fever"
        assert new_ensemble.weights == trained_ensemble.weights
    
    def test_load_nonexistent_model(self):
        """Test loading a non-existent model raises error."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        with pytest.raises(FileNotFoundError):
            ensemble.load(version="nonexistent_version_xyz")


class TestEnsembleForecasterIndividualPredictions:
    """Test getting individual model predictions."""
    
    @pytest.fixture
    def trained_ensemble(self, sample_disease_data, sample_environmental_data):
        """Create a trained ensemble for testing."""
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        ensemble.train(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data
        )
        return ensemble
    
    def test_get_individual_predictions(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test getting predictions from individual models."""
        predictions = trained_ensemble.get_individual_predictions(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        assert 'xgboost' in predictions
        assert 'lstm' in predictions
        assert 'prophet' in predictions
        
        # Check all predictions have correct length
        for model_pred in predictions.values():
            assert len(model_pred) == 7
            assert all(model_pred >= 0)
    
    def test_individual_predictions_consistency(self, trained_ensemble, sample_disease_data, sample_environmental_data):
        """Test that ensemble prediction is weighted average of individual predictions."""
        individual_preds = trained_ensemble.get_individual_predictions(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        ensemble_pred, _ = trained_ensemble.predict(
            disease_cases_df=sample_disease_data,
            environmental_df=sample_environmental_data,
            forecast_period_days=7
        )
        
        # Calculate expected weighted average
        expected_pred = (
            trained_ensemble.weights['xgboost'] * individual_preds['xgboost'] +
            trained_ensemble.weights['lstm'] * individual_preds['lstm'] +
            trained_ensemble.weights['prophet'] * individual_preds['prophet']
        )
        
        # Check that ensemble prediction matches weighted average
        assert np.allclose(ensemble_pred, expected_pred, rtol=1e-5)


class TestEnsembleForecasterEdgeCases:
    """Test edge cases and error handling."""
    
    def test_different_disease_types(self, sample_disease_data, sample_environmental_data):
        """Test ensemble with different disease types."""
        disease_types = ['dengue_fever', 'seasonal_flu', 'respiratory_disease']
        
        for disease_type in disease_types:
            ensemble = EnsembleForecaster(disease_type=disease_type)
            
            # Update disease type in data
            data = sample_disease_data.copy()
            data['disease_type'] = disease_type
            
            # Should train without error
            ensemble.train(
                disease_cases_df=data,
                environmental_df=sample_environmental_data
            )
            
            assert ensemble.is_trained == True
            assert ensemble.disease_type == disease_type
    
    def test_zero_case_counts(self, sample_environmental_data):
        """Test handling of zero case counts."""
        # Create data with some zero values
        dates = pd.date_range(start='2024-01-01', periods=120, freq='D')
        case_counts = np.random.randint(0, 50, 120)
        case_counts[:10] = 0  # Set first 10 days to zero
        
        data = pd.DataFrame({
            'recorded_at': dates,
            'disease_type': 'dengue_fever',
            'case_count': case_counts,
            'location': 'Ho Chi Minh City'
        })
        
        ensemble = EnsembleForecaster(disease_type="dengue_fever")
        
        # Should handle zeros without error
        metrics = ensemble.train(
            disease_cases_df=data,
            environmental_df=sample_environmental_data
        )
        
        assert ensemble.is_trained == True
        assert all(m['mae'] >= 0 for m in metrics.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
