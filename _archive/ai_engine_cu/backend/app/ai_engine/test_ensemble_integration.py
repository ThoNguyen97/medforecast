"""
Integration Test for Ensemble Forecaster

This script demonstrates the ensemble forecaster in action with realistic data.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.ai_engine.ensemble_forecaster import EnsembleForecaster


def create_realistic_disease_data(days=120):
    """Create realistic disease case data with trend and seasonality."""
    dates = pd.date_range(start='2024-01-01', periods=days, freq='D')
    
    # Create realistic pattern: trend + weekly seasonality + noise
    t = np.arange(days)
    trend = 50 + 0.3 * t  # Increasing trend
    weekly_seasonality = 15 * np.sin(2 * np.pi * t / 7)  # Weekly pattern
    noise = np.random.normal(0, 5, days)
    
    case_counts = trend + weekly_seasonality + noise
    case_counts = np.maximum(case_counts, 0).astype(int)
    
    df = pd.DataFrame({
        'recorded_at': dates,
        'disease_type': 'dengue_fever',
        'case_count': case_counts,
        'location': 'Ho Chi Minh City'
    })
    
    return df


def create_realistic_environmental_data(days=120):
    """Create realistic environmental data."""
    dates = pd.date_range(start='2024-01-01', periods=days, freq='D')
    
    # Create realistic patterns
    t = np.arange(days)
    
    # Temperature: seasonal variation
    temperature = 28 + 5 * np.sin(2 * np.pi * t / 365) + np.random.normal(0, 1, days)
    
    # Humidity: correlated with temperature
    humidity = 75 + 10 * np.sin(2 * np.pi * t / 365 + np.pi/4) + np.random.normal(0, 3, days)
    
    # Rainfall: more random with occasional spikes
    rainfall = np.abs(np.random.gamma(2, 5, days))
    
    # Air quality: some variation
    air_quality = 100 + np.random.normal(0, 20, days)
    air_quality = np.clip(air_quality, 0, 500)
    
    df = pd.DataFrame({
        'recorded_at': dates,
        'location': 'Ho Chi Minh City',
        'temperature': temperature,
        'humidity': humidity,
        'rainfall': rainfall,
        'air_quality_index': air_quality
    })
    
    return df


def main():
    """Run integration test."""
    print("=" * 80)
    print("ENSEMBLE FORECASTER INTEGRATION TEST")
    print("=" * 80)
    print()
    
    # Create realistic data
    print("Creating realistic disease and environmental data...")
    disease_data = create_realistic_disease_data(days=120)
    environmental_data = create_realistic_environmental_data(days=120)
    
    print(f"Disease data: {len(disease_data)} days")
    print(f"Case count range: {disease_data['case_count'].min()} - {disease_data['case_count'].max()}")
    print()
    
    # Initialize ensemble with default weights
    print("Initializing Ensemble Forecaster with default weights...")
    ensemble = EnsembleForecaster(disease_type="dengue_fever")
    print(f"Weights: XGBoost={ensemble.weights['xgboost']:.2f}, "
          f"LSTM={ensemble.weights['lstm']:.2f}, Prophet={ensemble.weights['prophet']:.2f}")
    print()
    
    # Train the ensemble
    print("Training ensemble models...")
    print("-" * 80)
    metrics = ensemble.train(
        disease_cases_df=disease_data,
        environmental_df=environmental_data
    )
    print()
    
    # Display training metrics
    print("Training Metrics:")
    print("-" * 80)
    for model_name, model_metrics in metrics.items():
        print(f"\n{model_name.upper()}:")
        print(f"  MAE:   {model_metrics['mae']:.2f}")
        print(f"  RMSE:  {model_metrics['rmse']:.2f}")
        print(f"  MAPE:  {model_metrics['mape']:.2f}%")
        print(f"  R²:    {model_metrics.get('r2', 0):.4f}")
    print()
    
    # Get model performance comparison
    print("Model Performance Comparison:")
    print("-" * 80)
    comparison = ensemble.get_model_performance_comparison()
    print(comparison.to_string(index=False))
    print()
    
    # Generate 7-day forecast
    print("Generating 7-day forecast...")
    predictions, forecast_dates = ensemble.predict(
        disease_cases_df=disease_data,
        environmental_df=environmental_data,
        forecast_period_days=7
    )
    
    print("\n7-Day Forecast:")
    print("-" * 80)
    for date, pred in zip(forecast_dates, predictions):
        print(f"{date.strftime('%Y-%m-%d')}: {pred:.0f} cases")
    print()
    
    # Generate forecast with confidence intervals
    print("Generating 7-day forecast with confidence intervals...")
    predictions, lower, upper, forecast_dates = ensemble.predict_with_confidence(
        disease_cases_df=disease_data,
        environmental_df=environmental_data,
        forecast_period_days=7,
        confidence_level=0.95
    )
    
    print("\n7-Day Forecast with 95% Confidence Intervals:")
    print("-" * 80)
    print(f"{'Date':<12} {'Prediction':<12} {'Lower Bound':<12} {'Upper Bound':<12} {'Interval Width':<15}")
    print("-" * 80)
    for date, pred, low, up in zip(forecast_dates, predictions, lower, upper):
        width = up - low
        print(f"{date.strftime('%Y-%m-%d'):<12} {pred:>11.0f} {low:>11.0f} {up:>11.0f} {width:>14.0f}")
    print()
    
    # Get individual model predictions
    print("Individual Model Predictions:")
    print("-" * 80)
    individual_preds = ensemble.get_individual_predictions(
        disease_cases_df=disease_data,
        environmental_df=environmental_data,
        forecast_period_days=7
    )
    
    print(f"{'Date':<12} {'XGBoost':<12} {'LSTM':<12} {'Prophet':<12} {'Ensemble':<12}")
    print("-" * 80)
    for i, date in enumerate(forecast_dates):
        print(f"{date.strftime('%Y-%m-%d'):<12} "
              f"{individual_preds['xgboost'][i]:>11.0f} "
              f"{individual_preds['lstm'][i]:>11.0f} "
              f"{individual_preds['prophet'][i]:>11.0f} "
              f"{predictions[i]:>11.0f}")
    print()
    
    # Test with auto weight adjustment
    print("Testing with automatic weight adjustment...")
    print("-" * 80)
    ensemble_auto = EnsembleForecaster(
        disease_type="dengue_fever",
        auto_adjust_weights=True
    )
    
    print("Initial weights:", ensemble_auto.weights)
    
    metrics_auto = ensemble_auto.train(
        disease_cases_df=disease_data,
        environmental_df=environmental_data
    )
    
    print("Adjusted weights:", ensemble_auto.weights)
    print()
    
    # Test custom weights
    print("Testing with custom weights...")
    print("-" * 80)
    custom_weights = {
        'xgboost': 0.5,
        'lstm': 0.3,
        'prophet': 0.2
    }
    
    ensemble_custom = EnsembleForecaster(
        disease_type="dengue_fever",
        weights=custom_weights
    )
    
    print(f"Custom weights: XGBoost={ensemble_custom.weights['xgboost']:.2f}, "
          f"LSTM={ensemble_custom.weights['lstm']:.2f}, Prophet={ensemble_custom.weights['prophet']:.2f}")
    
    ensemble_custom.train(
        disease_cases_df=disease_data,
        environmental_df=environmental_data
    )
    
    custom_predictions, _ = ensemble_custom.predict(
        disease_cases_df=disease_data,
        environmental_df=environmental_data,
        forecast_period_days=7
    )
    
    print("\nComparison of predictions with different weights:")
    print(f"{'Date':<12} {'Default':<12} {'Custom':<12} {'Difference':<12}")
    print("-" * 80)
    for i, date in enumerate(forecast_dates):
        diff = custom_predictions[i] - predictions[i]
        print(f"{date.strftime('%Y-%m-%d'):<12} {predictions[i]:>11.0f} "
              f"{custom_predictions[i]:>11.0f} {diff:>11.0f}")
    print()
    
    # Save and load test
    print("Testing save and load functionality...")
    print("-" * 80)
    save_path = ensemble.save(version="integration_test")
    print(f"Model saved to: {save_path}")
    
    # Load into new instance
    ensemble_loaded = EnsembleForecaster(disease_type="dengue_fever")
    ensemble_loaded.load(version="integration_test")
    print("Model loaded successfully")
    
    # Verify loaded model produces same predictions
    loaded_predictions, _ = ensemble_loaded.predict(
        disease_cases_df=disease_data,
        environmental_df=environmental_data,
        forecast_period_days=7
    )
    
    predictions_match = np.allclose(predictions, loaded_predictions)
    print(f"Predictions match: {predictions_match}")
    print()
    
    print("=" * 80)
    print("INTEGRATION TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == '__main__':
    main()
