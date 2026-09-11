"""
Prophet Forecaster for Medical Supply Forecasting System

This module implements the Prophet-based forecasting model for predicting
disease case counts. Prophet is particularly effective for capturing seasonality
patterns and handling time series with strong seasonal effects.
"""

import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from prophet import Prophet

from .config import MODEL_CONFIG, TRAINING_CONFIG, get_model_path
from .feature_engineering import handle_missing_values
from .model_evaluation import calculate_all_metrics


# Configure logging
logger = logging.getLogger(__name__)


class ProphetForecaster:
    """
    Prophet-based forecaster for disease case prediction.
    
    This class implements Facebook Prophet for time series forecasting,
    using historical disease cases and environmental data to predict
    future case counts. Prophet is particularly good at handling
    seasonality and trend changes.
    
    Features used:
    - Historical case counts (time series)
    - Environmental regressors (temperature, humidity, rainfall, air_quality_index)
    - Automatic seasonality detection (yearly, weekly)
    - Trend changepoints
    
    Attributes:
        model: Prophet model instance
        disease_type: Type of disease being forecasted
        is_trained: Whether the model has been trained
        config: Prophet configuration parameters
    
    Example:
        >>> forecaster = ProphetForecaster(disease_type="dengue_fever")
        >>> forecaster.train(disease_cases_df, environmental_df)
        >>> predictions = forecaster.predict(forecast_period_days=7)
    """
    
    def __init__(
        self,
        disease_type: str,
        config: Optional[Dict] = None
    ):
        """
        Initialize Prophet forecaster.
        
        Args:
            disease_type: Type of disease (dengue_fever, seasonal_flu, respiratory_disease)
            config: Optional custom configuration (uses defaults if not provided)
        """
        self.disease_type = disease_type
        self.is_trained = False
        self.training_data: Optional[pd.DataFrame] = None
        
        # Set configuration
        if config is None:
            self.config = MODEL_CONFIG['prophet'].copy()
        else:
            self.config = config
        
        # Initialize Prophet model
        self.model = Prophet(
            yearly_seasonality=self.config['yearly_seasonality'],
            weekly_seasonality=self.config['weekly_seasonality'],
            daily_seasonality=self.config['daily_seasonality'],
            changepoint_prior_scale=self.config['changepoint_prior_scale'],
            seasonality_prior_scale=self.config['seasonality_prior_scale'],
            interval_width=self.config['interval_width']
        )
        
        # Add environmental regressors
        self.model.add_regressor('temperature')
        self.model.add_regressor('humidity')
        self.model.add_regressor('rainfall')
        self.model.add_regressor('air_quality_index')
        
        logger.info(f"Initialized ProphetForecaster for {disease_type}")
    
    def prepare_prophet_dataframe(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> pd.DataFrame:
        """
        Prepare data in Prophet's required format.
        
        Prophet requires a DataFrame with columns:
        - ds: date column
        - y: target variable
        - Additional columns for regressors
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: Optional DataFrame with environmental data
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            DataFrame in Prophet format
        """
        logger.info(f"Preparing Prophet dataframe for {self.disease_type}")
        
        # Create base dataframe with Prophet's required columns
        df = disease_cases_df.copy()
        df = df.rename(columns={date_col: 'ds', target_col: 'y'})
        
        # Ensure ds is datetime
        df['ds'] = pd.to_datetime(df['ds'])
        
        # Sort by date
        df = df.sort_values('ds').reset_index(drop=True)
        
        # Merge with environmental data if provided
        if environmental_df is not None:
            env_df = environmental_df.copy()
            env_df = env_df.rename(columns={date_col: 'ds'})
            env_df['ds'] = pd.to_datetime(env_df['ds'])
            
            # Merge on date
            df = df.merge(
                env_df[['ds', 'temperature', 'humidity', 'rainfall', 'air_quality_index']],
                on='ds',
                how='left'
            )
            
            # Handle missing environmental data
            for col in ['temperature', 'humidity', 'rainfall', 'air_quality_index']:
                if col in df.columns:
                    df[col] = df[col].fillna(df[col].mean())
                else:
                    # If column doesn't exist, fill with default values
                    if col == 'temperature':
                        df[col] = 30.0
                    elif col == 'humidity':
                        df[col] = 75.0
                    elif col == 'rainfall':
                        df[col] = 5.0
                    elif col == 'air_quality_index':
                        df[col] = 100.0
        else:
            # If no environmental data, use default values
            df['temperature'] = 30.0
            df['humidity'] = 75.0
            df['rainfall'] = 5.0
            df['air_quality_index'] = 100.0
        
        # Handle missing values in target
        df = handle_missing_values(df, strategy='forward_fill')
        
        # Drop any remaining NaN rows
        df = df.dropna(subset=['ds', 'y'])
        
        logger.info(f"Prophet dataframe prepared: {len(df)} samples")
        
        return df
    
    def train(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Dict[str, float]:
        """
        Train the Prophet model on historical data.
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: Optional DataFrame with environmental data
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Dictionary containing training metrics (MAE, RMSE, MAPE, etc.)
        
        Raises:
            ValueError: If insufficient training data is provided
        """
        logger.info(f"Training Prophet model for {self.disease_type}")
        
        # Prepare data in Prophet format
        prophet_df = self.prepare_prophet_dataframe(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Check minimum training samples
        min_samples = TRAINING_CONFIG['min_training_samples']
        if len(prophet_df) < min_samples:
            raise ValueError(
                f"Insufficient training data. Required: {min_samples} samples, "
                f"Got: {len(prophet_df)} samples"
            )
        
        # Store training data for later use in predictions
        self.training_data = prophet_df.copy()
        
        # Split data for evaluation (use last 20% as test set)
        test_size = TRAINING_CONFIG['test_size']
        split_idx = int(len(prophet_df) * (1 - test_size))
        
        train_df = prophet_df.iloc[:split_idx].copy()
        test_df = prophet_df.iloc[split_idx:].copy()
        
        logger.info(f"Training set: {len(train_df)} samples")
        logger.info(f"Test set: {len(test_df)} samples")
        
        # Train Prophet model
        self.model.fit(train_df)
        
        # Evaluate on test set
        # Create future dataframe for test period
        test_future = test_df[['ds', 'temperature', 'humidity', 'rainfall', 'air_quality_index']].copy()
        
        # Make predictions
        forecast = self.model.predict(test_future)
        
        # Extract predictions
        y_true = test_df['y'].values
        y_pred = forecast['yhat'].values
        
        # Ensure non-negative predictions
        y_pred = np.maximum(y_pred, 0)
        
        # Calculate metrics
        metrics = calculate_all_metrics(y_true, y_pred)
        
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
        
        # Prepare historical data
        prophet_df = self.prepare_prophet_dataframe(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Get the last date in historical data
        last_date = prophet_df['ds'].max()
        
        # Generate forecast dates
        forecast_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=forecast_period_days,
            freq='D'
        )
        
        # Create future dataframe
        future_df = pd.DataFrame({'ds': forecast_dates})
        
        # Add environmental regressors for future dates
        # For simplicity, use the mean values from historical data
        # In production, you would use actual forecasted environmental data
        if environmental_df is not None:
            for col in ['temperature', 'humidity', 'rainfall', 'air_quality_index']:
                if col in prophet_df.columns:
                    future_df[col] = prophet_df[col].mean()
                else:
                    # Use default values
                    if col == 'temperature':
                        future_df[col] = 30.0
                    elif col == 'humidity':
                        future_df[col] = 75.0
                    elif col == 'rainfall':
                        future_df[col] = 5.0
                    elif col == 'air_quality_index':
                        future_df[col] = 100.0
        else:
            future_df['temperature'] = 30.0
            future_df['humidity'] = 75.0
            future_df['rainfall'] = 5.0
            future_df['air_quality_index'] = 100.0
        
        # Make predictions
        forecast = self.model.predict(future_df)
        
        # Extract predictions
        predictions = forecast['yhat'].values
        
        # Ensure non-negative predictions
        predictions = np.maximum(predictions, 0)
        
        logger.info(f"Forecast generated: {len(predictions)} predictions")
        logger.info(f"Predicted range: {predictions.min():.0f} - {predictions.max():.0f} cases")
        
        return predictions, forecast_dates
    
    def predict_with_confidence(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        forecast_period_days: int = 7,
        date_col: str = 'recorded_at',
        target_col: str = 'case_count'
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex]:
        """
        Generate predictions with confidence intervals.
        
        Prophet automatically provides confidence intervals based on
        uncertainty in trend and seasonality.
        
        Args:
            disease_cases_df: DataFrame with historical disease case data
            environmental_df: Optional DataFrame with environmental data
            forecast_period_days: Number of days to forecast (7-30)
            date_col: Name of the date column
            target_col: Name of the target column (case count)
        
        Returns:
            Tuple of (predictions, lower_bounds, upper_bounds, forecast_dates)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        if forecast_period_days < 7 or forecast_period_days > 30:
            raise ValueError("Forecast period must be between 7 and 30 days")
        
        logger.info(f"Generating {forecast_period_days}-day forecast with confidence intervals")
        
        # Prepare historical data
        prophet_df = self.prepare_prophet_dataframe(
            disease_cases_df=disease_cases_df,
            environmental_df=environmental_df,
            date_col=date_col,
            target_col=target_col
        )
        
        # Get the last date in historical data
        last_date = prophet_df['ds'].max()
        
        # Generate forecast dates
        forecast_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=forecast_period_days,
            freq='D'
        )
        
        # Create future dataframe
        future_df = pd.DataFrame({'ds': forecast_dates})
        
        # Add environmental regressors
        if environmental_df is not None:
            for col in ['temperature', 'humidity', 'rainfall', 'air_quality_index']:
                if col in prophet_df.columns:
                    future_df[col] = prophet_df[col].mean()
                else:
                    if col == 'temperature':
                        future_df[col] = 30.0
                    elif col == 'humidity':
                        future_df[col] = 75.0
                    elif col == 'rainfall':
                        future_df[col] = 5.0
                    elif col == 'air_quality_index':
                        future_df[col] = 100.0
        else:
            future_df['temperature'] = 30.0
            future_df['humidity'] = 75.0
            future_df['rainfall'] = 5.0
            future_df['air_quality_index'] = 100.0
        
        # Make predictions
        forecast = self.model.predict(future_df)
        
        # Extract predictions and confidence intervals
        predictions = forecast['yhat'].values
        lower_bounds = forecast['yhat_lower'].values
        upper_bounds = forecast['yhat_upper'].values
        
        # Ensure non-negative values
        predictions = np.maximum(predictions, 0)
        lower_bounds = np.maximum(lower_bounds, 0)
        upper_bounds = np.maximum(upper_bounds, 0)
        
        logger.info(f"Confidence intervals calculated at {self.config['interval_width']*100}% level")
        
        return predictions, lower_bounds, upper_bounds, forecast_dates
    
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
        
        model_path = get_model_path("prophet", self.disease_type, version)
        
        # Save model and metadata
        model_data = {
            'model': self.model,
            'disease_type': self.disease_type,
            'config': self.config,
            'is_trained': self.is_trained,
            'training_data': self.training_data
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
        model_path = get_model_path("prophet", self.disease_type, version)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.disease_type = model_data['disease_type']
        self.config = model_data['config']
        self.is_trained = model_data['is_trained']
        self.training_data = model_data.get('training_data')
        
        logger.info(f"Model loaded from {model_path}")
    
    def get_seasonality_components(self) -> pd.DataFrame:
        """
        Get the seasonality components from the trained model.
        
        Returns:
            DataFrame with trend, yearly, and weekly seasonality components
        
        Raises:
            ValueError: If model is not trained
        """
        if not self.is_trained:
            raise ValueError("Model must be trained to get seasonality components")
        
        if self.training_data is None:
            raise ValueError("Training data not available")
        
        # Make predictions on training data to get components
        forecast = self.model.predict(self.training_data)
        
        # Extract components
        components_df = pd.DataFrame({
            'ds': forecast['ds'],
            'trend': forecast['trend'],
            'yearly': forecast.get('yearly', 0),
            'weekly': forecast.get('weekly', 0)
        })
        
        return components_df
    
    def retrain_if_needed(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: Optional[pd.DataFrame] = None,
        original_training_size: int = None
    ) -> bool:
        """
        Check if model needs retraining based on new data availability.
        
        Model is retrained if new data exceeds 10% of original training size.
        Prophet models can only be fit once, so we need to create a new instance.
        
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
            
            # Prophet can only be fit once, so create a new model instance
            self.model = Prophet(
                yearly_seasonality=self.config['yearly_seasonality'],
                weekly_seasonality=self.config['weekly_seasonality'],
                daily_seasonality=self.config['daily_seasonality'],
                changepoint_prior_scale=self.config['changepoint_prior_scale'],
                seasonality_prior_scale=self.config['seasonality_prior_scale'],
                interval_width=self.config['interval_width']
            )
            
            # Re-add environmental regressors
            self.model.add_regressor('temperature')
            self.model.add_regressor('humidity')
            self.model.add_regressor('rainfall')
            self.model.add_regressor('air_quality_index')
            
            # Reset training state
            self.is_trained = False
            
            # Retrain model
            self.train(disease_cases_df, environmental_df)
            
            # Save retrained model
            self.save(version="latest")
            
            return True
        
        return False
