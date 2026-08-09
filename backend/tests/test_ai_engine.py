"""
Tests for AI Engine utilities
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.ai_engine.feature_engineering import (
    create_lag_features,
    create_rolling_statistics,
    create_seasonality_features,
    create_trend_features,
    prepare_features_for_forecasting
)

from app.ai_engine.model_evaluation import (
    calculate_mae,
    calculate_rmse,
    calculate_mape,
    calculate_all_metrics,
    compare_models
)


class TestFeatureEngineering:
    """Test feature engineering functions"""
    
    def test_create_lag_features(self):
        """Test lag feature creation"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'case_count': range(100)
        })
        
        result = create_lag_features(df, 'case_count', [7, 14])
        
        assert 'case_count_lag_7' in result.columns
        assert 'case_count_lag_14' in result.columns
        assert result['case_count_lag_7'].iloc[7] == 0
        assert result['case_count_lag_14'].iloc[14] == 0
    
    def test_create_rolling_statistics(self):
        """Test rolling statistics creation"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'case_count': range(100)
        })
        
        result = create_rolling_statistics(df, 'case_count', [7], ['mean', 'std'])
        
        assert 'case_count_rolling_7_mean' in result.columns
        assert 'case_count_rolling_7_std' in result.columns
        
        # Check that rolling mean is calculated correctly
        assert result['case_count_rolling_7_mean'].iloc[6] == 3.0  # mean of 0-6
    
    def test_create_seasonality_features(self):
        """Test seasonality feature creation"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100)
        })
        
        result = create_seasonality_features(df, 'date')
        
        assert 'month' in result.columns
        assert 'day_of_week' in result.columns
        assert 'is_weekend' in result.columns
        assert 'month_sin' in result.columns
        assert 'month_cos' in result.columns
        
        # Check first date is January (month=1)
        assert result['month'].iloc[0] == 1
    
    def test_create_trend_features(self):
        """Test trend feature creation"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100)
        })
        
        result = create_trend_features(df, 'date')
        
        assert 'days_since_start' in result.columns
        assert 'linear_trend' in result.columns
        
        # Check first day is 0
        assert result['days_since_start'].iloc[0] == 0
        # Check last day is 99
        assert result['days_since_start'].iloc[-1] == 99
        # Check linear trend is normalized
        assert result['linear_trend'].iloc[-1] == 1.0


class TestModelEvaluation:
    """Test model evaluation functions"""
    
    def test_calculate_mae(self):
        """Test MAE calculation"""
        y_true = np.array([100, 120, 115, 130, 125])
        y_pred = np.array([105, 118, 120, 128, 130])
        
        mae = calculate_mae(y_true, y_pred)
        
        # MAE = (5 + 2 + 5 + 2 + 5) / 5 = 3.8
        assert abs(mae - 3.8) < 0.01
    
    def test_calculate_rmse(self):
        """Test RMSE calculation"""
        y_true = np.array([100, 120, 115, 130, 125])
        y_pred = np.array([105, 118, 120, 128, 130])
        
        rmse = calculate_rmse(y_true, y_pred)
        
        # RMSE = sqrt((25 + 4 + 25 + 4 + 25) / 5) = sqrt(16.6) ≈ 4.07
        assert abs(rmse - 4.07) < 0.1
    
    def test_calculate_mape(self):
        """Test MAPE calculation"""
        y_true = np.array([100, 120, 115, 130, 125])
        y_pred = np.array([105, 118, 120, 128, 130])
        
        mape = calculate_mape(y_true, y_pred)
        
        # MAPE should be a percentage
        assert 0 <= mape <= 100
        assert abs(mape - 3.15) < 0.5  # Approximate expected value
    
    def test_calculate_all_metrics(self):
        """Test all metrics calculation"""
        y_true = np.array([100, 120, 115, 130, 125])
        y_pred = np.array([105, 118, 120, 128, 130])
        
        metrics = calculate_all_metrics(y_true, y_pred)
        
        assert 'mae' in metrics
        assert 'rmse' in metrics
        assert 'mape' in metrics
        assert 'smape' in metrics
        assert 'r2' in metrics
        
        # All metrics should be numeric
        for key, value in metrics.items():
            assert isinstance(value, (int, float))
    
    def test_compare_models(self):
        """Test model comparison"""
        y_true = np.array([100, 120, 115, 130, 125])
        
        predictions = {
            'Model_A': np.array([105, 118, 120, 128, 130]),
            'Model_B': np.array([102, 122, 113, 132, 123]),
            'Model_C': np.array([100, 120, 115, 130, 125])  # Perfect predictions
        }
        
        comparison = compare_models(y_true, predictions)
        
        assert len(comparison) == 3
        assert 'model' in comparison.columns
        assert 'mae' in comparison.columns
        
        # Model_C should have the best (lowest) MAE
        best_model = comparison.iloc[0]['model']
        assert best_model == 'Model_C'
        assert comparison.iloc[0]['mae'] == 0.0


class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_prepare_features_workflow(self):
        """Test complete feature preparation workflow"""
        # Create sample disease cases data
        dates = pd.date_range('2024-01-01', periods=100)
        disease_cases_df = pd.DataFrame({
            'recorded_at': dates,
            'case_count': np.random.randint(50, 150, 100)
        })
        
        # Create sample environmental data
        environmental_df = pd.DataFrame({
            'recorded_at': dates,
            'temperature': np.random.uniform(25, 35, 100),
            'humidity': np.random.uniform(60, 90, 100),
            'rainfall': np.random.uniform(0, 50, 100),
            'air_quality_index': np.random.randint(50, 150, 100)
        })
        
        # Prepare features
        features_df = prepare_features_for_forecasting(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            target_col='case_count'
        )
        
        # Check that all expected features are present
        assert 'case_count_lag_7' in features_df.columns
        assert 'case_count_rolling_7_mean' in features_df.columns
        assert 'month' in features_df.columns
        assert 'temperature' in features_df.columns
        assert 'temperature_x_humidity' in features_df.columns
        
        # Check that data is not empty
        assert len(features_df) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
