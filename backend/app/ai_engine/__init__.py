"""
AI Engine Module for Medical Supply Forecasting System

This module provides machine learning capabilities for forecasting disease cases
and calculating supply requirements.
"""

from .feature_engineering import (
    create_lag_features,
    create_rolling_statistics,
    create_seasonality_features,
    create_trend_features,
    create_interaction_features,
    prepare_features_for_forecasting,
    split_train_test,
    handle_missing_values
)

from .model_evaluation import (
    calculate_mae,
    calculate_rmse,
    calculate_mape,
    calculate_smape,
    calculate_r2,
    calculate_all_metrics,
    evaluate_forecast_by_horizon,
    calculate_forecast_bias,
    calculate_coverage_probability,
    create_evaluation_report,
    compare_models,
    calculate_directional_accuracy,
    plot_predictions_vs_actual
)

from .config import (
    FEATURE_CONFIG,
    MODEL_CONFIG,
    TRAINING_CONFIG,
    EVALUATION_CONFIG,
    DISEASE_TYPES,
    DEFAULT_CONVERSION_RATIOS,
    get_model_path,
    get_checkpoint_path,
    SAVED_MODELS_DIR,
    CHECKPOINTS_DIR
)

from .xgboost_forecaster import XGBoostForecaster
from .prophet_forecaster import ProphetForecaster
from .ensemble_forecaster import EnsembleForecaster

__all__ = [
    # Feature Engineering
    'create_lag_features',
    'create_rolling_statistics',
    'create_seasonality_features',
    'create_trend_features',
    'create_interaction_features',
    'prepare_features_for_forecasting',
    'split_train_test',
    'handle_missing_values',
    
    # Model Evaluation
    'calculate_mae',
    'calculate_rmse',
    'calculate_mape',
    'calculate_smape',
    'calculate_r2',
    'calculate_all_metrics',
    'evaluate_forecast_by_horizon',
    'calculate_forecast_bias',
    'calculate_coverage_probability',
    'create_evaluation_report',
    'compare_models',
    'calculate_directional_accuracy',
    'plot_predictions_vs_actual',
    
    # Configuration
    'FEATURE_CONFIG',
    'MODEL_CONFIG',
    'TRAINING_CONFIG',
    'EVALUATION_CONFIG',
    'DISEASE_TYPES',
    'DEFAULT_CONVERSION_RATIOS',
    'get_model_path',
    'get_checkpoint_path',
    'SAVED_MODELS_DIR',
    'CHECKPOINTS_DIR',
    
    # Forecasters
    'XGBoostForecaster',
    'ProphetForecaster',
    'EnsembleForecaster'
]

__version__ = '1.0.0'
