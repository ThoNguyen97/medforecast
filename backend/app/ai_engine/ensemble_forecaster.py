"""
Ensemble Forecaster for Medical Supply Forecasting System

This module implements the ensemble forecasting model that combines predictions
from XGBoost, LSTM, and Prophet models to produce more accurate and robust forecasts.
"""

import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .config import MODEL_CONFIG, TRAINING_CONFIG, get_model_path
from .xgboost_forecaster import XGBoostForecaster
from .prophet_forecaster import ProphetForecaster
from .model_evaluation import calculate_all_metrics, compare_models


# Configure logging
logger = logging.getLogger(__name__)


class EnsembleForecaster:
    """
    Ensemble forecaster combining XGBoost, LSTM, and Prophet models.
    
    This class implements an ensemble approach that combines predictions from
    multiple models using weighted averaging. The weights can be configured
    or dynamically adjusted based on validation performance.
    
    Default weights:
    - XGBoost: 0.4 (good for non-linear patterns)
    - LSTM: 0.35 (good for temporal dependencies)
    - Prophet: 0.25 (good for seasonality)
    
    Attributes:
        disease_type: Type of disease being forecasted
        xgboost_model: XGBoost forecaster instance
        lstm_model: LSTM forecaster instance (placeholder for now)
        prophet_model: Prophet forecaster instance
        weights: Dictionary of model weights
        is_trained: Whether all models have been trained
        performance_metrics: Performance metrics for each model
    
    Example:
        >>> ensemble = EnsembleForecaster(disease_type="dengue_fever")
        >>> ensemble.train(disease_cases_df, environmental_df)
        >>> predictions = ensemble.predict(forecast_period_days=7)
    """
    
    def __init__(
        self,
        disease_type: str,
        weights: Optional[Dict[str, float]] = None,
        auto_adjust_weights: bool = False
    ):
        """
        Initialize Ensemble forecaster.
        
        Args:
            disease_type: Type of disease (dengue_fever, seasonal_flu, respiratory_disease)
            weights: Optional custom weights for models (uses defaults if not provided)
            auto_adjust_weights: Whether to automatically adjust weights based on validation performance
        """
        self.disease_type = disease_type
        self.auto_adjust_weights = auto_adjust_weights
        self.is_trained = False
        self.performance_metrics: Dict[str, Dict[str, float]] = {}
        
        # Set weights
        if weights is None:
            self.weights = MODEL_CONFIG['ensemble']['weights'].copy()
        else:
            self.weights = weights
            
        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if not np.isclose(weight_sum, 1.0):
            logger.warning(f"Weights sum to {weight_sum}, normalizing to 1.0")
            self.weights = {k: v / weight_sum for k, v in self.weights.items()}
        
        # Initialize individual models
        self.xgboost_model = XGBoostForecaster(disease_type=disease_type)
        self.prophet_model = ProphetForecaster(disease_type=disease_type)
        # LSTM model placeholder - will be implemented in future tasks
        self.lstm_model = None
        
        logger.info(f"Initialized EnsembleForecaster for {disease_type}")
        logger.info(f"Model weights: XGBoost={self.weights['xgboost']:.2f}, "
                   f"LSTM={self.weights['lstm']:.2f}, Prophet={self.weights['prophet']:.2f}")
    
    def train(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count',
        test_size: float = None,
        validation_split: float = 0.2
    ) -> Dict[str, Dict[str, float]]:
        """
        Train all models in the ensemble.
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: Optional DataFrame with environmental data
            date_col: Name of the date column
            target_col: Name of the target column (case count)
            test_size: Proportion of data for testing (uses config default if None)
            validation_split: Proportion of training data for validation
        
        Returns:
            Dictionary containing training metrics for each model
        
        Raises:
            ValueError: If insufficient training data is provided
        """
        logger.info(f"Training ensemble models for {self.disease_type}")
        
        # Train XGBoost model
        logger.info("Training XGBoost model...")
        xgb_metrics = self.xgboost_model.train(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col,
            test_size=test_size,
            validation_split=validation_split
        )
        self.performance_metrics['xgboost'] = xgb_metrics
        logger.info(f"XGBoost training completed. MAE: {xgb_metrics['mae']:.2f}")
        
        # Train Prophet model
        logger.info("Training Prophet model...")
        prophet_metrics = self.prophet_model.train(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        self.performance_metrics['prophet'] = prophet_metrics
        logger.info(f"Prophet training completed. MAE: {prophet_metrics['mae']:.2f}")
        
        # LSTM model training placeholder
        # TODO: Implement LSTM model training when LSTM forecaster is available
        if self.lstm_model is not None:
            logger.info("Training LSTM model...")
            lstm_metrics = self.lstm_model.train(
                disease_cases_df=disease_cases_df,
                environmental_df=environmental_df,
                date_col=date_col,
                target_col=target_col,
                test_size=test_size,
                validation_split=validation_split
            )
            self.performance_metrics['lstm'] = lstm_metrics
            logger.info(f"LSTM training completed. MAE: {lstm_metrics['mae']:.2f}")
        else:
            logger.warning("LSTM model not available, using placeholder metrics")
            # Use average of XGBoost and Prophet as placeholder
            self.performance_metrics['lstm'] = {
                'mae': (xgb_metrics['mae'] + prophet_metrics['mae']) / 2,
                'rmse': (xgb_metrics['rmse'] + prophet_metrics['rmse']) / 2,
                'mape': (xgb_metrics['mape'] + prophet_metrics['mape']) / 2,
                'smape': (xgb_metrics.get('smape', 0) + prophet_metrics.get('smape', 0)) / 2,
                'r2': (xgb_metrics.get('r2', 0) + prophet_metrics.get('r2', 0)) / 2
            }
        
        # Adjust weights based on validation performance if enabled
        if self.auto_adjust_weights:
            self._adjust_weights_by_performance()
        
        self.is_trained = True
        
        logger.info("Ensemble training completed")
        logger.info(f"Final weights: XGBoost={self.weights['xgboost']:.2f}, "
                   f"LSTM={self.weights['lstm']:.2f}, Prophet={self.weights['prophet']:.2f}")
        
        return self.performance_metrics
    
    def _adjust_weights_by_performance(self) -> None:
        """
        Dynamically adjust model weights based on validation performance.
        
        Uses inverse MAE as the basis for weight calculation:
        - Models with lower MAE get higher weights
        - Weights are normalized to sum to 1.0
        """
        logger.info("Adjusting weights based on validation performance")
        
        # Calculate inverse MAE for each model
        inverse_mae = {}
        for model_name, metrics in self.performance_metrics.items():
            mae = metrics['mae']
            if mae > 0:
                inverse_mae[model_name] = 1.0 / mae
            else:
                inverse_mae[model_name] = 1.0
        
        # Normalize to get weights
        total_inverse_mae = sum(inverse_mae.values())
        new_weights = {
            model: inv_mae / total_inverse_mae
            for model, inv_mae in inverse_mae.items()
        }
        
        logger.info(f"Old weights: {self.weights}")
        logger.info(f"New weights: {new_weights}")
        
        self.weights = new_weights
    
    def predict(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        forecast_period_days: int = 7,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Tuple[np.ndarray, pd.DatetimeIndex]:
        """
        Generate ensemble predictions for future time periods.
        
        This method combines predictions from all models using weighted averaging.
        
        Args:
            disease_cases_df: DataFrame with historical disease case data
            environmental_df: Optional DataFrame with environmental data
            forecast_period_days: Number of days to forecast (7-30)
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Tuple of (predictions array, forecast dates)
        
        Raises:
            ValueError: If models are not trained or forecast period is invalid
        """
        if not self.is_trained:
            raise ValueError("Models must be trained before making predictions")
        
        if forecast_period_days < 7 or forecast_period_days > 30:
            raise ValueError("Forecast period must be between 7 and 30 days")
        
        logger.info(f"Generating {forecast_period_days}-day ensemble forecast for {self.disease_type}")
        
        # Get predictions from XGBoost
        xgb_pred, forecast_dates = self.xgboost_model.predict(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        logger.info(f"XGBoost predictions: {xgb_pred.min():.0f} - {xgb_pred.max():.0f} cases")
        
        # Get predictions from Prophet
        prophet_pred, _ = self.prophet_model.predict(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        logger.info(f"Prophet predictions: {prophet_pred.min():.0f} - {prophet_pred.max():.0f} cases")
        
        # Get predictions from LSTM (placeholder)
        if self.lstm_model is not None:
            lstm_pred, _ = self.lstm_model.predict(
                disease_cases_df=disease_cases_df,
                environmental_df=environmental_df,
                forecast_period_days=forecast_period_days,
                date_col=date_col,
                target_col=target_col
            )
            logger.info(f"LSTM predictions: {lstm_pred.min():.0f} - {lstm_pred.max():.0f} cases")
        else:
            # Use average of XGBoost and Prophet as placeholder
            lstm_pred = (xgb_pred + prophet_pred) / 2
            logger.warning("LSTM model not available, using average of XGBoost and Prophet")
        
        # Combine predictions using weighted average
        ensemble_pred = (
            self.weights['xgboost'] * xgb_pred +
            self.weights['lstm'] * lstm_pred +
            self.weights['prophet'] * prophet_pred
        )
        
        # Ensure non-negative predictions
        ensemble_pred = np.maximum(ensemble_pred, 0)
        
        logger.info(f"Ensemble forecast generated: {len(ensemble_pred)} predictions")
        logger.info(f"Predicted range: {ensemble_pred.min():.0f} - {ensemble_pred.max():.0f} cases")
        
        return ensemble_pred, forecast_dates
    
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
        Generate ensemble predictions with confidence intervals.
        
        Confidence intervals are calculated by combining the uncertainty
        from individual models and the variance between model predictions.
        
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
        if not self.is_trained:
            raise ValueError("Models must be trained before making predictions")
        
        logger.info(f"Generating {forecast_period_days}-day ensemble forecast with confidence intervals")
        
        # Get predictions with confidence intervals from each model
        xgb_pred, xgb_lower, xgb_upper, forecast_dates = self.xgboost_model.predict_with_confidence(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            confidence_level=confidence_level,
            date_col=date_col,
            target_col=target_col
        )
        
        prophet_pred, prophet_lower, prophet_upper, _ = self.prophet_model.predict_with_confidence(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        
        # LSTM placeholder
        if self.lstm_model is not None:
            lstm_pred, lstm_lower, lstm_upper, _ = self.lstm_model.predict_with_confidence(
                disease_cases_df=disease_cases_df,
                environmental_df=environmental_df,
                forecast_period_days=forecast_period_days,
                confidence_level=confidence_level,
                date_col=date_col,
                target_col=target_col
            )
        else:
            # Use average as placeholder
            lstm_pred = (xgb_pred + prophet_pred) / 2
            lstm_lower = (xgb_lower + prophet_lower) / 2
            lstm_upper = (xgb_upper + prophet_upper) / 2
        
        # Combine predictions using weighted average
        ensemble_pred = (
            self.weights['xgboost'] * xgb_pred +
            self.weights['lstm'] * lstm_pred +
            self.weights['prophet'] * prophet_pred
        )
        
        # Combine confidence intervals
        # Method 1: Weighted average of individual intervals
        ensemble_lower_weighted = (
            self.weights['xgboost'] * xgb_lower +
            self.weights['lstm'] * lstm_lower +
            self.weights['prophet'] * prophet_lower
        )
        
        ensemble_upper_weighted = (
            self.weights['xgboost'] * xgb_upper +
            self.weights['lstm'] * lstm_upper +
            self.weights['prophet'] * prophet_upper
        )
        
        # Method 2: Account for variance between models
        # Calculate standard deviation of predictions across models
        all_predictions = np.array([xgb_pred, lstm_pred, prophet_pred])
        model_variance = np.std(all_predictions, axis=0)
        
        # Combine both sources of uncertainty
        alpha = 1 - confidence_level
        z_score = 1.96  # For 95% confidence
        
        # Adjust intervals based on model disagreement
        interval_adjustment = z_score * model_variance
        
        ensemble_lower = ensemble_lower_weighted - interval_adjustment * 0.5
        ensemble_upper = ensemble_upper_weighted + interval_adjustment * 0.5
        
        # Ensure non-negative bounds
        ensemble_pred = np.maximum(ensemble_pred, 0)
        ensemble_lower = np.maximum(ensemble_lower, 0)
        ensemble_upper = np.maximum(ensemble_upper, 0)
        
        logger.info(f"Confidence intervals calculated at {confidence_level*100}% level")
        logger.info(f"Average interval width: {np.mean(ensemble_upper - ensemble_lower):.1f} cases")
        
        return ensemble_pred, ensemble_lower, ensemble_upper, forecast_dates
    
    def get_model_performance_comparison(self) -> pd.DataFrame:
        """
        Get performance comparison of all models in the ensemble.
        
        Returns:
            DataFrame with metrics for each model, sorted by MAE
        
        Raises:
            ValueError: If models are not trained
        
        Example:
            >>> comparison = ensemble.get_model_performance_comparison()
            >>> print(comparison)
            >>> # Shows MAE, RMSE, MAPE for XGBoost, LSTM, Prophet
        """
        if not self.is_trained:
            raise ValueError("Models must be trained to get performance comparison")
        
        # Create DataFrame from performance metrics
        results = []
        for model_name, metrics in self.performance_metrics.items():
            row = {
                'model': model_name,
                'weight': self.weights[model_name],
                'mae': metrics['mae'],
                'rmse': metrics['rmse'],
                'mape': metrics['mape'],
                'smape': metrics.get('smape', 0),
                'r2': metrics.get('r2', 0)
            }
            results.append(row)
        
        df = pd.DataFrame(results)
        
        # Sort by MAE (lower is better)
        df = df.sort_values('mae')
        
        logger.info("Model performance comparison:")
        logger.info(f"\n{df.to_string()}")
        
        return df
    
    def set_weights(self, weights: Dict[str, float]) -> None:
        """
        Manually set model weights.
        
        Args:
            weights: Dictionary of model weights (must sum to 1.0)
        
        Raises:
            ValueError: If weights don't sum to approximately 1.0
        
        Example:
            >>> ensemble.set_weights({'xgboost': 0.5, 'lstm': 0.3, 'prophet': 0.2})
        """
        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0, atol=0.01):
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")
        
        # Normalize to ensure exact sum of 1.0
        self.weights = {k: v / weight_sum for k, v in weights.items()}
        
        logger.info(f"Weights updated: XGBoost={self.weights['xgboost']:.2f}, "
                   f"LSTM={self.weights['lstm']:.2f}, Prophet={self.weights['prophet']:.2f}")
    
    def save(self, version: str = "latest") -> Path:
        """
        Save the ensemble model to disk.
        
        Args:
            version: Version identifier for the model (default: "latest")
        
        Returns:
            Path to the saved model file
        
        Raises:
            ValueError: If models are not trained
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained ensemble")
        
        # Save individual models
        self.xgboost_model.save(version)
        self.prophet_model.save(version)
        if self.lstm_model is not None:
            self.lstm_model.save(version)
        
        # Save ensemble metadata
        model_path = get_model_path("ensemble", self.disease_type, version)
        
        ensemble_data = {
            'disease_type': self.disease_type,
            'weights': self.weights,
            'auto_adjust_weights': self.auto_adjust_weights,
            'is_trained': self.is_trained,
            'performance_metrics': self.performance_metrics
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(ensemble_data, f)
        
        logger.info(f"Ensemble model saved to {model_path}")
        
        return model_path
    
    def load(self, version: str = "latest") -> None:
        """
        Load an ensemble model from disk.
        
        Args:
            version: Version identifier for the model (default: "latest")
        
        Raises:
            FileNotFoundError: If model file does not exist
        """
        # Load individual models
        self.xgboost_model.load(version)
        self.prophet_model.load(version)
        if self.lstm_model is not None:
            try:
                self.lstm_model.load(version)
            except FileNotFoundError:
                logger.warning("LSTM model file not found, continuing without LSTM")
        
        # Load ensemble metadata
        model_path = get_model_path("ensemble", self.disease_type, version)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Ensemble model file not found: {model_path}")
        
        with open(model_path, 'rb') as f:
            ensemble_data = pickle.load(f)
        
        self.disease_type = ensemble_data['disease_type']
        self.weights = ensemble_data['weights']
        self.auto_adjust_weights = ensemble_data['auto_adjust_weights']
        self.is_trained = ensemble_data['is_trained']
        self.performance_metrics = ensemble_data['performance_metrics']
        
        logger.info(f"Ensemble model loaded from {model_path}")
        logger.info(f"Weights: XGBoost={self.weights['xgboost']:.2f}, "
                   f"LSTM={self.weights['lstm']:.2f}, Prophet={self.weights['prophet']:.2f}")
    
    def get_individual_predictions(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        forecast_period_days: int = 7,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Dict[str, np.ndarray]:
        """
        Get predictions from each individual model separately.
        
        Useful for comparing model outputs and understanding ensemble behavior.
        
        Args:
            disease_cases_df: DataFrame with historical disease case data
            environmental_df: Optional DataFrame with environmental data
            forecast_period_days: Number of days to forecast (7-30)
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Dictionary mapping model names to prediction arrays
        
        Example:
            >>> predictions = ensemble.get_individual_predictions(df, env_df, 7)
            >>> print(f"XGBoost: {predictions['xgboost']}")
            >>> print(f"Prophet: {predictions['prophet']}")
        """
        if not self.is_trained:
            raise ValueError("Models must be trained before making predictions")
        
        predictions = {}
        
        # XGBoost predictions
        xgb_pred, _ = self.xgboost_model.predict(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        predictions['xgboost'] = xgb_pred
        
        # Prophet predictions
        prophet_pred, _ = self.prophet_model.predict(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            forecast_period_days=forecast_period_days,
            date_col=date_col,
            target_col=target_col
        )
        predictions['prophet'] = prophet_pred
        
        # LSTM predictions (placeholder)
        if self.lstm_model is not None:
            lstm_pred, _ = self.lstm_model.predict(
                disease_cases_df=disease_cases_df,
                environmental_df=environmental_df,
                forecast_period_days=forecast_period_days,
                date_col=date_col,
                target_col=target_col
            )
            predictions['lstm'] = lstm_pred
        else:
            predictions['lstm'] = (xgb_pred + prophet_pred) / 2
        
        return predictions
