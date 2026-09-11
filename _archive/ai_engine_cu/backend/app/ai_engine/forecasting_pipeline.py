"""
Forecasting Pipeline for Medical Supply Forecasting System

This module implements the main forecasting pipeline that orchestrates
the entire forecasting workflow including data retrieval, feature engineering,
model training, forecast generation, and automatic retraining.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.models.disease_forecast import DiseaseForecast
from app.models.supply_requirement import SupplyRequirement
from app.models.conversion_ratio import ConversionRatio

from .ensemble_forecaster import EnsembleForecaster
from .xgboost_forecaster import XGBoostForecaster
from .prophet_forecaster import ProphetForecaster
from .feature_engineering import prepare_features_for_forecasting
from .model_evaluation import calculate_all_metrics
from .conversion_module import ConversionModule
from .config import TRAINING_CONFIG, DISEASE_TYPES


# Configure logging
logger = logging.getLogger(__name__)


class ForecastingPipeline:
    """
    Main forecasting pipeline that orchestrates the complete forecasting workflow.
    
    This class handles:
    - Data retrieval from database (90 days minimum)
    - Feature engineering pipeline
    - Model training orchestration
    - Forecast generation
    - Automatic model retraining (when data exceeds 10% threshold)
    - Error handling and logging
    
    Attributes:
        db: Database session
        disease_type: Type of disease being forecasted
        ensemble_forecaster: Ensemble model combining XGBoost, LSTM, Prophet
        xgboost_forecaster: XGBoost model
        prophet_forecaster: Prophet model
        original_training_size: Size of original training dataset
        last_training_date: Date of last model training
    
    Example:
        >>> pipeline = ForecastingPipeline(db_session, disease_type="dengue_fever")
        >>> pipeline.train_models()
        >>> forecast_result = pipeline.generate_forecast(forecast_period_days=7)
    """
    
    def __init__(
        self,
        db: Session,
        disease_type: str,
        use_ensemble: bool = True
    ):
        """
        Initialize the forecasting pipeline.
        
        Args:
            db: Database session
            disease_type: Type of disease (dengue_fever, seasonal_flu, respiratory_disease)
            use_ensemble: Whether to use ensemble model (default: True)
        
        Raises:
            ValueError: If disease_type is not valid
        """
        if disease_type not in DISEASE_TYPES:
            raise ValueError(
                f"Invalid disease type: {disease_type}. "
                f"Must be one of {DISEASE_TYPES}"
            )
        
        self.db = db
        self.disease_type = disease_type
        self.use_ensemble = use_ensemble
        
        # Initialize models
        if use_ensemble:
            self.ensemble_forecaster = EnsembleForecaster(disease_type=disease_type)
            self.forecaster = self.ensemble_forecaster
        else:
            # Use XGBoost as default single model
            self.xgboost_forecaster = XGBoostForecaster(disease_type=disease_type)
            self.forecaster = self.xgboost_forecaster
        
        # Initialize conversion module
        self.conversion_module = ConversionModule(db)
        
        # Training metadata
        self.original_training_size: Optional[int] = None
        self.last_training_date: Optional[datetime] = None
        
        logger.info(f"Initialized ForecastingPipeline for {disease_type}")
        logger.info(f"Using {'ensemble' if use_ensemble else 'single'} model")
    
    def retrieve_historical_data(
        self,
        min_days: int = 90,
        location: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Retrieve historical data from database.
        
        Retrieves disease case data and environmental data for the specified
        disease type. Ensures minimum 90 days of data are available.
        
        Args:
            min_days: Minimum number of days of historical data required (default: 90)
            location: Optional location filter
        
        Returns:
            Tuple of (disease_cases_df, environmental_df)
        
        Raises:
            ValueError: If insufficient historical data is available
        """
        logger.info(f"Retrieving historical data for {self.disease_type}")
        logger.info(f"Minimum required days: {min_days}")
        
        try:
            # Calculate date threshold
            date_threshold = datetime.now() - timedelta(days=min_days * 2)  # Get extra data for safety
            
            # Query disease cases
            query = self.db.query(DiseaseCase).filter(
                DiseaseCase.disease_type == self.disease_type,
                DiseaseCase.recorded_at >= date_threshold
            )
            
            if location:
                query = query.filter(DiseaseCase.location == location)
            
            disease_cases = query.order_by(DiseaseCase.recorded_at).all()
            
            # Convert to DataFrame
            disease_cases_df = pd.DataFrame([
                {
                    'recorded_at': case.recorded_at,
                    'disease_type': case.disease_type,
                    'case_count': case.case_count,
                    'location': case.location,
                    'severity': case.severity,
                    'data_source': case.data_source
                }
                for case in disease_cases
            ])
            
            # Check if we have enough data
            if len(disease_cases_df) < min_days:
                raise ValueError(
                    f"Insufficient historical data. Required: {min_days} days, "
                    f"Available: {len(disease_cases_df)} days"
                )
            
            logger.info(f"Retrieved {len(disease_cases_df)} disease case records")
            
            # Query environmental data
            env_query = self.db.query(EnvironmentalData).filter(
                EnvironmentalData.recorded_at >= date_threshold
            )
            
            if location:
                env_query = env_query.filter(EnvironmentalData.location == location)
            
            environmental_data = env_query.order_by(EnvironmentalData.recorded_at).all()
            
            # Convert to DataFrame (may be empty if no environmental data)
            environmental_df = pd.DataFrame([
                {
                    'recorded_at': env.recorded_at,
                    'location': env.location,
                    'temperature': float(env.temperature) if env.temperature else None,
                    'humidity': float(env.humidity) if env.humidity else None,
                    'rainfall': float(env.rainfall) if env.rainfall else None,
                    'air_quality_index': env.air_quality_index,
                    'data_source': env.data_source
                }
                for env in environmental_data
            ]) if environmental_data else None
            
            logger.info(f"Retrieved {len(environmental_df) if environmental_df is not None else 0} environmental records")
            
            return disease_cases_df, environmental_df
            
        except Exception as e:
            logger.error(f"Error retrieving historical data: {str(e)}")
            raise
    
    def engineer_features(
        self,
        disease_cases_df: pd.DataFrame,
        environmental_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Apply feature engineering pipeline.
        
        Creates lag features, rolling statistics, seasonality features,
        trend features, and environmental features.
        
        Args:
            disease_cases_df: DataFrame with disease case data
            environmental_df: DataFrame with environmental data
        
        Returns:
            DataFrame with engineered features
        """
        logger.info("Engineering features")
        
        try:
            features_df = prepare_features_for_forecasting(
                disease_cases_df=disease_cases_df,
                environmental_df=environmental_df,
                date_col='recorded_at',
                target_col='case_count'
            )
            
            logger.info(f"Features engineered: {features_df.shape[0]} samples, "
                       f"{features_df.shape[1]} features")
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error engineering features: {str(e)}")
            raise
    
    def train_models(
        self,
        min_days: int = 90,
        location: Optional[str] = None,
        force_retrain: bool = False
    ) -> Dict[str, float]:
        """
        Train all models in the pipeline.
        
        Retrieves historical data, engineers features, and trains models.
        Stores training metadata for automatic retraining.
        
        Args:
            min_days: Minimum number of days of historical data required (default: 90)
            location: Optional location filter
            force_retrain: Force retraining even if models are already trained
        
        Returns:
            Dictionary containing training metrics
        
        Raises:
            ValueError: If insufficient training data is available
        """
        logger.info(f"Training models for {self.disease_type}")
        
        try:
            # Retrieve historical data
            disease_cases_df, environmental_df = self.retrieve_historical_data(
                min_days=min_days,
                location=location
            )
            
            # Store original training size for retraining logic
            self.original_training_size = len(disease_cases_df)
            self.last_training_date = datetime.now()
            
            # Train models
            if self.use_ensemble:
                metrics = self.ensemble_forecaster.train(
                    disease_cases_df=disease_cases_df,
                    environmental_df=environmental_df,
                    date_col='recorded_at',
                    target_col='case_count'
                )
                
                # Save trained models
                self.ensemble_forecaster.save(version="latest")
                
                logger.info("Ensemble models trained and saved")
                
            else:
                metrics = self.xgboost_forecaster.train(
                    disease_cases_df=disease_cases_df,
                    environmental_df=environmental_df,
                    date_col='recorded_at',
                    target_col='case_count'
                )
                
                # Save trained model
                self.xgboost_forecaster.save(version="latest")
                
                logger.info("XGBoost model trained and saved")
            
            logger.info(f"Training completed. Metrics: {metrics}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error training models: {str(e)}")
            raise
    
    def generate_forecast(
        self,
        forecast_period_days: int = 7,
        location: Optional[str] = None,
        save_to_db: bool = True
    ) -> Dict:
        """
        Generate forecast for the specified period.
        
        Retrieves historical data, generates predictions using trained models,
        calculates confidence intervals, and optionally saves to database.
        
        Args:
            forecast_period_days: Number of days to forecast (7-30)
            location: Optional location filter
            save_to_db: Whether to save forecast to database (default: True)
        
        Returns:
            Dictionary containing:
            - forecast_dates: List of forecast dates
            - predictions: Array of predicted case counts
            - confidence_lower: Array of lower confidence bounds
            - confidence_upper: Array of upper confidence bounds
            - model_used: Name of model used
            - metrics: Model accuracy metrics
        
        Raises:
            ValueError: If models are not trained or forecast period is invalid
        """
        logger.info(f"Generating {forecast_period_days}-day forecast for {self.disease_type}")
        
        try:
            # Validate forecast period
            if forecast_period_days < 7 or forecast_period_days > 30:
                raise ValueError("Forecast period must be between 7 and 30 days")
            
            # Check if automatic retraining is needed
            self._check_and_retrain_if_needed(location=location)
            
            # Retrieve historical data
            disease_cases_df, environmental_df = self.retrieve_historical_data(
                min_days=90,
                location=location
            )
            
            # Generate predictions with confidence intervals
            predictions, lower_bounds, upper_bounds, forecast_dates = \
                self.forecaster.predict_with_confidence(
                    disease_cases_df=disease_cases_df,
                    environmental_df=environmental_df,
                    forecast_period_days=forecast_period_days,
                    date_col='recorded_at',
                    target_col='case_count'
                )
            
            # Get model performance metrics
            if self.use_ensemble:
                metrics = self.ensemble_forecaster.performance_metrics
                model_used = "ensemble"
            else:
                # For single model, we don't have stored metrics, use placeholder
                metrics = {'xgboost': {'mae': 0, 'rmse': 0, 'mape': 0}}
                model_used = "xgboost"
            
            # Calculate average metrics for ensemble
            if self.use_ensemble and metrics:
                avg_mae = np.mean([m['mae'] for m in metrics.values()])
                avg_rmse = np.mean([m['rmse'] for m in metrics.values()])
                avg_mape = np.mean([m['mape'] for m in metrics.values()])
            else:
                avg_mae = metrics.get('xgboost', {}).get('mae', 0)
                avg_rmse = metrics.get('xgboost', {}).get('rmse', 0)
                avg_mape = metrics.get('xgboost', {}).get('mape', 0)
            
            logger.info(f"Forecast generated: {len(predictions)} predictions")
            logger.info(f"Predicted range: {predictions.min():.0f} - {predictions.max():.0f} cases")
            
            # Save to database if requested
            if save_to_db:
                self._save_forecast_to_db(
                    forecast_dates=forecast_dates,
                    predictions=predictions,
                    lower_bounds=lower_bounds,
                    upper_bounds=upper_bounds,
                    model_used=model_used,
                    avg_mae=avg_mae,
                    avg_rmse=avg_rmse,
                    avg_mape=avg_mape,
                    forecast_period_days=forecast_period_days
                )
            
            # Prepare result
            result = {
                'forecast_dates': forecast_dates.tolist(),
                'predictions': predictions.tolist(),
                'confidence_lower': lower_bounds.tolist(),
                'confidence_upper': upper_bounds.tolist(),
                'model_used': model_used,
                'metrics': {
                    'mae': float(avg_mae),
                    'rmse': float(avg_rmse),
                    'mape': float(avg_mape)
                },
                'forecast_period_days': forecast_period_days,
                'disease_type': self.disease_type
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise
    
    def _save_forecast_to_db(
        self,
        forecast_dates: pd.DatetimeIndex,
        predictions: np.ndarray,
        lower_bounds: np.ndarray,
        upper_bounds: np.ndarray,
        model_used: str,
        avg_mae: float,
        avg_rmse: float,
        avg_mape: float,
        forecast_period_days: int
    ) -> None:
        """
        Save forecast results to database.
        
        Args:
            forecast_dates: Array of forecast dates
            predictions: Array of predicted case counts
            lower_bounds: Array of lower confidence bounds
            upper_bounds: Array of upper confidence bounds
            model_used: Name of model used
            avg_mae: Average MAE across models
            avg_rmse: Average RMSE across models
            avg_mape: Average MAPE across models
            forecast_period_days: Number of days forecasted
        """
        try:
            logger.info("Saving forecast to database")
            
            # Create forecast records
            for i, date in enumerate(forecast_dates):
                forecast = DiseaseForecast(
                    forecast_date=date.date(),
                    disease_type=self.disease_type,
                    predicted_cases=int(predictions[i]),
                    confidence_lower=int(lower_bounds[i]),
                    confidence_upper=int(upper_bounds[i]),
                    model_used=model_used,
                    model_accuracy_mae=float(avg_mae),
                    model_accuracy_rmse=float(avg_rmse),
                    model_accuracy_mape=float(avg_mape),
                    forecast_period_days=forecast_period_days
                )
                self.db.add(forecast)
            
            self.db.commit()
            
            logger.info(f"Saved {len(forecast_dates)} forecast records to database")
            
        except Exception as e:
            logger.error(f"Error saving forecast to database: {str(e)}")
            self.db.rollback()
            raise
    
    def _check_and_retrain_if_needed(
        self,
        location: Optional[str] = None
    ) -> bool:
        """
        Check if automatic retraining is needed and retrain if necessary.
        
        Model is retrained if new data exceeds 10% of original training size.
        
        Args:
            location: Optional location filter
        
        Returns:
            True if model was retrained, False otherwise
        """
        if self.original_training_size is None:
            logger.info("No training metadata available, skipping retrain check")
            return False
        
        try:
            # Get current data size
            disease_cases_df, environmental_df = self.retrieve_historical_data(
                min_days=90,
                location=location
            )
            
            current_size = len(disease_cases_df)
            new_data_size = current_size - self.original_training_size
            
            threshold = TRAINING_CONFIG['retrain_threshold']
            retrain_threshold_size = int(self.original_training_size * threshold)
            
            logger.info(f"Retrain check: current_size={current_size}, "
                       f"original_size={self.original_training_size}, "
                       f"new_data={new_data_size}, threshold={retrain_threshold_size}")
            
            if new_data_size >= retrain_threshold_size:
                logger.info(f"Retraining triggered: {new_data_size} new samples "
                           f"(threshold: {retrain_threshold_size})")
                
                # Retrain models
                self.train_models(location=location, force_retrain=True)
                
                return True
            
            logger.info("No retraining needed")
            return False
            
        except Exception as e:
            logger.error(f"Error checking retrain status: {str(e)}")
            # Don't raise, just log and continue
            return False
    
    def calculate_supply_requirements(
        self,
        forecast_id: Optional[int] = None,
        predictions: Optional[np.ndarray] = None,
        forecast_dates: Optional[pd.DatetimeIndex] = None
    ) -> List[Dict]:
        """
        Calculate supply requirements based on disease forecasts.
        
        Uses ConversionModule to convert predicted case counts to required
        supply quantities using conversion ratios from database or defaults.
        
        Args:
            forecast_id: Optional forecast ID from database
            predictions: Optional array of predicted case counts
            forecast_dates: Optional array of forecast dates
        
        Returns:
            List of dictionaries containing supply requirements
        """
        logger.info("Calculating supply requirements using ConversionModule")
        
        try:
            # Load conversion ratios from database
            self.conversion_module.load_conversion_ratios()
            
            # Calculate requirements for all forecast dates
            requirements = self.conversion_module.calculate_requirements_for_forecast(
                disease_type=self.disease_type,
                predictions=predictions,
                forecast_dates=forecast_dates
            )
            
            # Add forecast_id to each requirement if provided
            if forecast_id is not None:
                for req in requirements:
                    req['forecast_id'] = forecast_id
            
            logger.info(f"Calculated {len(requirements)} supply requirements")
            
            return requirements
            
        except Exception as e:
            logger.error(f"Error calculating supply requirements: {str(e)}")
            raise
    
    def load_trained_models(self, version: str = "latest") -> None:
        """
        Load previously trained models from disk.
        
        Args:
            version: Version identifier for the models (default: "latest")
        
        Raises:
            FileNotFoundError: If model files do not exist
        """
        logger.info(f"Loading trained models (version: {version})")
        
        try:
            if self.use_ensemble:
                self.ensemble_forecaster.load(version=version)
            else:
                self.xgboost_forecaster.load(version=version)
            
            logger.info("Models loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            raise
    
    def get_model_performance(self) -> Dict:
        """
        Get performance metrics for trained models.
        
        Returns:
            Dictionary containing model performance metrics
        
        Raises:
            ValueError: If models are not trained
        """
        if self.use_ensemble:
            if not self.ensemble_forecaster.is_trained:
                raise ValueError("Ensemble models are not trained")
            
            return {
                'model_type': 'ensemble',
                'disease_type': self.disease_type,
                'performance_metrics': self.ensemble_forecaster.performance_metrics,
                'weights': self.ensemble_forecaster.weights,
                'last_training_date': self.last_training_date.isoformat() if self.last_training_date else None
            }
        else:
            if not self.xgboost_forecaster.is_trained:
                raise ValueError("XGBoost model is not trained")
            
            return {
                'model_type': 'xgboost',
                'disease_type': self.disease_type,
                'last_training_date': self.last_training_date.isoformat() if self.last_training_date else None
            }
