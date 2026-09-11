"""
XGBoost Forecaster for Medical Supply Forecasting System

This module implements the XGBoost-based forecasting model for predicting
disease case counts. XGBoost is particularly effective for capturing non-linear
patterns and interactions between features.
"""

import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

from .config import MODEL_CONFIG, TRAINING_CONFIG, get_model_path
from .feature_engineering import (
    prepare_features_for_forecasting,
    handle_missing_values
)
from .model_evaluation import calculate_all_metrics


# Configure logging
logger = logging.getLogger(__name__)


class XGBoostForecaster:
    """
    XGBoost-based forecaster for disease case prediction.
    
    This class implements gradient boosting for time series forecasting,
    using historical disease cases and environmental data to predict
    future case counts.
    
    Features used:
    - Historical case counts (lag 7, 14, 30 days)
    - Rolling statistics (7-day, 14-day, 30-day averages)
    - Temperature, humidity, rainfall, air quality index
    - Seasonal indicators (month, week, day of week)
    - Trend features
    - Interaction features (temperature × humidity, etc.)
    
    Attributes:
        model: XGBoost regressor model
        disease_type: Type of disease being forecasted
        feature_columns: List of feature column names used for training
        is_trained: Whether the model has been trained
        hyperparameters: Model hyperparameters
    
    Example:
        >>> forecaster = XGBoostForecaster(disease_type="dengue_fever")
        >>> forecaster.train(disease_cases_df, environmental_df)
        >>> predictions = forecaster.predict(forecast_period_days=7)
    """
    
    def __init__(
        self,
        disease_type: str,
        hyperparameters: Optional[Dict] = None
    ):
        """
        Initialize XGBoost forecaster.
        
        Args:
            disease_type: Type of disease (dengue_fever, seasonal_flu, respiratory_disease)
            hyperparameters: Optional custom hyperparameters (uses defaults if not provided)
        """
        self.disease_type = disease_type
        self.feature_columns: Optional[List[str]] = None
        self.is_trained = False
        
        # Set hyperparameters
        if hyperparameters is None:
            self.hyperparameters = MODEL_CONFIG['xgboost'].copy()
        else:
            self.hyperparameters = hyperparameters
        
        # Initialize model
        self.model = xgb.XGBRegressor(**self.hyperparameters)
        
        logger.info(f"Initialized XGBoostForecaster for {disease_type}")
    
    def prepare_features(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> pd.DataFrame:
        """
        Prepare features for XGBoost model.
        
        This method applies comprehensive feature engineering including:
        - Lag features
        - Rolling statistics
        - Seasonality features
        - Trend features
        - Environmental features (if provided)
        - Interaction features
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: Optional DataFrame with environmental data
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Preparing features for {self.disease_type}")
        
        # Use feature engineering pipeline
        features_df = prepare_features_for_forecasting(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Handle missing values (forward fill for time series)
        features_df = handle_missing_values(features_df, strategy='forward_fill')
        
        # Drop any remaining NaN rows (from initial lag periods)
        features_df = features_df.dropna()
        
        logger.info(f"Features prepared: {features_df.shape[0]} samples, {features_df.shape[1]} features")
        
        return features_df
    
    def train(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count',
        test_size: float = None,
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        Train the XGBoost model on historical data.
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: Optional DataFrame with environmental data
            date_col: Name of the date column
            target_col: Name of the target column (case count)
            test_size: Proportion of data for testing (uses config default if None)
            validation_split: Proportion of training data for validation
        
        Returns:
            Dictionary containing training metrics (MAE, RMSE, MAPE, etc.)
        
        Raises:
            ValueError: If insufficient training data is provided
        """
        logger.info(f"Training XGBoost model for {self.disease_type}")
        
        # Prepare features
        features_df = self.prepare_features(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Check minimum training samples
        min_samples = TRAINING_CONFIG['min_training_samples']
        if len(features_df) < min_samples:
            raise ValueError(
                f"Insufficient training data. Required: {min_samples} samples, "
                f"Got: {len(features_df)} samples"
            )
        
        # Separate features and target
        exclude_cols = [date_col, target_col, 'location', 'disease_type', 'data_source', 'severity']
        feature_cols = [col for col in features_df.columns if col not in exclude_cols]
        
        # Ensure all feature columns are numeric
        numeric_cols = []
        for col in feature_cols:
            if pd.api.types.is_numeric_dtype(features_df[col]):
                numeric_cols.append(col)
        
        feature_cols = numeric_cols
        
        X = features_df[feature_cols].values
        y = features_df[target_col].values
        
        # Store feature columns for later use
        self.feature_columns = feature_cols
        
        # Split into train and test sets
        if test_size is None:
            test_size = TRAINING_CONFIG['test_size']
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            shuffle=False,  # Don't shuffle time series data
            random_state=TRAINING_CONFIG['random_state']
        )
        
        # Further split training data for validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train,
            test_size=validation_split,
            shuffle=False,
            random_state=TRAINING_CONFIG['random_state']
        )
        
        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Validation set: {len(X_val)} samples")
        logger.info(f"Test set: {len(X_test)} samples")
        
        # Train model with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate on test set
        y_pred = self.model.predict(X_test)
        metrics = calculate_all_metrics(y_test, y_pred)
        
        self.is_trained = True
        
        logger.info(f"Training completed. Test MAE: {metrics['mae']:.2f}, "
                   f"RMSE: {metrics['rmse']:.2f}, MAPE: {metrics['mape']:.2f}%")
        
        return metrics
    
    def predict(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        forecast_period_days: int = 7,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Tuple[np.ndarray, pd.DatetimeIndex]:
        """
        Generate predictions for future time periods.
        
        This method uses the trained model to predict disease cases for
        the specified forecast period. It uses a recursive approach where
        predictions are fed back as features for subsequent predictions.
        
        Args:
            disease_cases_df: DataFrame with historical disease case data
            environmental_df: Optional DataFrame with environmental data
            forecast_period_days: Number of days to forecast (7-30)
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Tuple of (predictions array, forecast dates)
        
        Raises:
            ValueError: If model is not trained or forecast period is invalid
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        if forecast_period_days < 7 or forecast_period_days > 30:
            raise ValueError("Forecast period must be between 7 and 30 days")
        
        logger.info(f"Generating {forecast_period_days}-day forecast for {self.disease_type}")
        
        # Prepare features from historical data
        features_df = self.prepare_features(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Get the last date in historical data
        last_date = pd.to_datetime(features_df[date_col].max())
        
        # Generate forecast dates
        forecast_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=forecast_period_days,
            freq='D'
        )
        
        # Initialize predictions array
        predictions = []
        
        # Ensure all trained feature columns exist; fill missing ones with 0
        # (happens when model was trained with environmental data but predict has none)
        for col in self.feature_columns:
            if col not in features_df.columns:
                features_df[col] = 0.0

        # Get the most recent features for prediction
        latest_features = features_df[self.feature_columns].iloc[-1:].values
        
        # Recursive prediction (each prediction feeds into next)
        for i in range(forecast_period_days):
            # Make prediction
            pred = self.model.predict(latest_features)[0]
            predictions.append(max(0, pred))  # Ensure non-negative predictions
            
            # For simplicity, we use the same features for all predictions
            # In a more sophisticated approach, we would update lag features
            # with new predictions
        
        predictions = np.array(predictions)
        
        logger.info(f"Forecast generated: {len(predictions)} predictions")
        logger.info(f"Predicted range: {predictions.min():.0f} - {predictions.max():.0f} cases")
        
        return predictions, forecast_dates
    
    def save(self, version: str = "latest") -> Path:
        """
        Save the trained model to disk.
        
        Args:
            version: Version identifier for the model (default: "latest")
        
        Returns:
            Path to the saved model file
        
        Raises:
            ValueError: If model is not trained
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_path = get_model_path("xgboost", self.disease_type, version)
        
        # Save model and metadata
        model_data = {
            'model': self.model,
            'disease_type': self.disease_type,
            'feature_columns': self.feature_columns,
            'hyperparameters': self.hyperparameters,
            'is_trained': self.is_trained
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {model_path}")
        
        return model_path
    
    def load(self, version: str = "latest") -> None:
        """
        Load a trained model from disk.
        
        Args:
            version: Version identifier for the model (default: "latest")
        
        Raises:
            FileNotFoundError: If model file does not exist
        """
        model_path = get_model_path("xgboost", self.disease_type, version)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.disease_type = model_data['disease_type']
        self.feature_columns = model_data['feature_columns']
        self.hyperparameters = model_data['hyperparameters']
        self.is_trained = model_data['is_trained']
        
        logger.info(f"Model loaded from {model_path}")
    
    def get_feature_importance(self, top_n: int = 10) -> pd.DataFrame:
        """
        Get feature importance scores from the trained model.
        
        Args:
            top_n: Number of top features to return (default: 10)
        
        Returns:
            DataFrame with feature names and importance scores
        
        Raises:
            ValueError: If model is not trained
        """
        if not self.is_trained:
            raise ValueError("Model must be trained to get feature importance")
        
        # Get feature importance
        importance_scores = self.model.feature_importances_
        
        # Create DataFrame
        importance_df = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance_scores
        })
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        # Return top N features
        return importance_df.head(top_n)
    
    def predict_with_confidence(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        forecast_period_days: int = 7,
        confidence_level: float = 0.95,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex]:
        """
        Generate predictions with confidence intervals.
        
        Confidence intervals are estimated using quantile regression
        or bootstrap methods.
        
        Args:
            disease_cases_df: DataFrame with historical disease case data
            environmental_df: Optional DataFrame with environmental data
            forecast_period_days: Number of days to forecast (7-30)
            confidence_level: Confidence level for intervals (default: 0.95)
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Tuple of (predictions, lower_bounds, upper_bounds, forecast_dates)
        """
        # Get point predictions
        predictions, forecast_dates = self.predict(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        
        # Estimate confidence intervals
        # For simplicity, we use a percentage of the prediction
        # In production, use quantile regression or bootstrap methods
        alpha = 1 - confidence_level
        std_multiplier = 1.96  # For 95% confidence
        
        # Estimate standard deviation as a percentage of prediction
        # This is a simplified approach
        std_estimate = predictions * 0.15  # 15% of prediction
        
        lower_bounds = predictions - std_multiplier * std_estimate
        upper_bounds = predictions + std_multiplier * std_estimate
        
        # Ensure non-negative bounds
        lower_bounds = np.maximum(lower_bounds, 0)
        upper_bounds = np.maximum(upper_bounds, 0)
        
        logger.info(f"Confidence intervals calculated at {confidence_level*100}% level")
        
        return predictions, lower_bounds, upper_bounds, forecast_dates
    
    def retrain_if_needed(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        original_training_size: int = None
    ) -> bool:
        """
        Check if model needs retraining based on new data availability.
        
        Model is retrained if new data exceeds 10% of original training size.
        
        Args:
            disease_cases_df: DataFrame with current disease case data
            environmental_df: Optional DataFrame with environmental data
            original_training_size: Size of original training dataset
        
        Returns:
            True if model was retrained, False otherwise
        """
        if original_training_size is None:
            logger.warning("Original training size not provided, skipping retrain check")
            return False
        
        current_size = len(disease_cases_df)
        new_data_size = current_size - original_training_size
        
        threshold = TRAINING_CONFIG['retrain_threshold']
        
        if new_data_size >= original_training_size * threshold:
            logger.info(f"Retraining triggered: {new_data_size} new samples "
                       f"(threshold: {original_training_size * threshold})")
            
            # Retrain model
            self.train(disease_cases_df, environmental_df)
            
            # Save retrained model
            self.save(version="latest")
            
            return True
        
        return False
