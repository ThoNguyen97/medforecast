"""
Configuration for AI/ML Engine

This module contains configuration settings for the ML models,
feature engineering, and model storage.
"""

import os
from pathlib import Path
from typing import Dict, List


# Base paths
BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
SAVED_MODELS_DIR = MODELS_DIR / "saved_models"
CHECKPOINTS_DIR = MODELS_DIR / "checkpoints"

# Ensure directories exist
SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


# Feature Engineering Configuration
FEATURE_CONFIG = {
    # Lag features configuration
    "lag_periods": [7, 14, 30],  # Days to lag
    
    # Rolling window configuration
    "rolling_windows": [7, 14, 30],  # Window sizes in days
    "rolling_stats": ["mean", "std", "min", "max"],  # Statistics to calculate
    
    # Date features
    "include_seasonality": True,
    "include_trend": True,
    
    # Environmental features
    "environmental_features": [
        "temperature",
        "humidity",
        "rainfall",
        "air_quality_index"
    ],
    
    # Interaction features
    "interaction_pairs": [
        ("temperature", "humidity"),
        ("temperature", "rainfall"),
        ("humidity", "rainfall")
    ]
}


# Model Configuration
MODEL_CONFIG = {
    # XGBoost configuration
    "xgboost": {
        "n_estimators": 200,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1
    },
    
    # LSTM configuration
    "lstm": {
        "sequence_length": 30,  # Days of history to use
        "lstm_units_1": 64,
        "lstm_units_2": 32,
        "dense_units": 16,
        "dropout_rate": 0.2,
        "learning_rate": 0.001,
        "epochs": 100,
        "batch_size": 32,
        "validation_split": 0.2,
        "early_stopping_patience": 10
    },
    
    # Prophet configuration
    "prophet": {
        "yearly_seasonality": True,
        "weekly_seasonality": True,
        "daily_seasonality": False,
        "changepoint_prior_scale": 0.05,
        "seasonality_prior_scale": 10,
        "interval_width": 0.95  # 95% confidence intervals
    },
    
    # Ensemble configuration
    "ensemble": {
        "weights": {
            "xgboost": 0.4,
            "lstm": 0.35,
            "prophet": 0.25
        },
        "method": "weighted_average"  # or "stacking"
    }
}


# Training Configuration
TRAINING_CONFIG = {
    "test_size": 0.2,  # Proportion of data for testing
    "validation_size": 0.2,  # Proportion of training data for validation
    "min_training_samples": 90,  # Minimum days of data required
    "retrain_threshold": 0.1,  # Retrain when new data exceeds 10% of training size
    "random_state": 42
}


# Evaluation Configuration
EVALUATION_CONFIG = {
    "metrics": ["mae", "rmse", "mape", "smape", "r2"],
    "forecast_horizons": [7, 14, 30],  # Days to evaluate
    "confidence_level": 0.95
}


# Disease Types
DISEASE_TYPES = [
    "dengue_fever",
    "seasonal_flu",
    "respiratory_disease"
]


# Model File Naming Convention
def get_model_path(model_type: str, disease_type: str, version: str = "latest") -> Path:
    """
    Get the file path for a saved model.
    
    Args:
        model_type: Type of model (xgboost, lstm, prophet, ensemble)
        disease_type: Disease type (dengue_fever, seasonal_flu, respiratory_disease)
        version: Model version (default: "latest")
    
    Returns:
        Path to the model file
    
    Example:
        >>> path = get_model_path("xgboost", "dengue_fever", "v1")
        >>> # Returns: .../saved_models/xgboost_dengue_fever_v1.pkl
    """
    filename = f"{model_type}_{disease_type}_{version}.pkl"
    return SAVED_MODELS_DIR / filename


def get_checkpoint_path(model_type: str, disease_type: str, epoch: int) -> Path:
    """
    Get the file path for a model checkpoint.
    
    Args:
        model_type: Type of model
        disease_type: Disease type
        epoch: Training epoch number
    
    Returns:
        Path to the checkpoint file
    
    Example:
        >>> path = get_checkpoint_path("lstm", "dengue_fever", 50)
        >>> # Returns: .../checkpoints/lstm_dengue_fever_epoch_50.h5
    """
    filename = f"{model_type}_{disease_type}_epoch_{epoch}.h5"
    return CHECKPOINTS_DIR / filename


# Conversion Ratios (default values, can be overridden from database)
DEFAULT_CONVERSION_RATIOS = {
    "dengue_fever": {
        "masks": 2.0,
        "gloves": 4.0,
        "test_kits": 1.0,
        "disinfectant": 0.5,
        "iv_fluids": 0.3,
        "medications": 1.5
    },
    "seasonal_flu": {
        "masks": 2.0,
        "gloves": 4.0,
        "test_kits": 0.8,
        "disinfectant": 0.5,
        "medications": 2.0,
        "tissues": 5.0
    },
    "respiratory_disease": {
        "masks": 3.0,
        "gloves": 4.0,
        "test_kits": 1.0,
        "disinfectant": 0.5,
        "oxygen": 0.2,
        "medications": 2.5
    }
}


# Logging Configuration
LOGGING_CONFIG = {
    "log_level": "INFO",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "ai_engine.log"
}
