"""Forecast service for managing disease forecasts."""
import logging
from datetime import datetime, date
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.disease_forecast import DiseaseForecast
from app.models.supply_requirement import SupplyRequirement
from app.models.medical_supply import MedicalSupply
from app.ai_engine.forecasting_pipeline import ForecastingPipeline
from app.schemas.base import DiseaseType

logger = logging.getLogger(__name__)


def _auto_generate_supply_requirements(db: Session, forecast_id: int) -> None:
    """Trigger supply requirement auto-generation for a newly created forecast.

    Runs as a best-effort operation — failures are logged but do not abort
    the forecast creation response.
    """
    try:
        from app.services.supply_requirement_service import SupplyRequirementService

        service = SupplyRequirementService(db)
        reqs = service.generate_requirements_for_forecast(forecast_id)
        logger.info(
            f"Auto-generated {len(reqs)} supply requirements for forecast_id={forecast_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to auto-generate supply requirements for forecast_id={forecast_id}: {e}"
        )


class ForecastService:
    """Service for managing disease forecasts."""
    
    def __init__(self, db: Session):
        """Initialize forecast service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def generate_forecast(
        self,
        disease_type: DiseaseType,
        forecast_period_days: int,
        location: Optional[str] = None
    ) -> Dict:
        """Generate a new disease forecast.
        
        Args:
            disease_type: Type of disease to forecast
            forecast_period_days: Number of days to forecast (7-30)
            location: Optional location filter
        
        Returns:
            Dictionary containing forecast results
        
        Raises:
            ValueError: If forecast parameters are invalid
        """
        logger.info(f"Generating forecast for {disease_type.value}, period: {forecast_period_days} days")
        
        try:
            # Initialize forecasting pipeline
            pipeline = ForecastingPipeline(
                db=self.db,
                disease_type=disease_type.value,
                use_ensemble=True
            )
            
            # Try to load existing trained models
            try:
                pipeline.load_trained_models(version="latest")
                logger.info("Loaded existing trained models")
            except FileNotFoundError:
                logger.info("No existing models found, training new models")
                pipeline.train_models(location=location)
            
            # Generate forecast
            forecast_result = pipeline.generate_forecast(
                forecast_period_days=forecast_period_days,
                location=location,
                save_to_db=True
            )
            
            logger.info(f"Forecast generated successfully: {len(forecast_result['predictions'])} predictions")
            
            # Auto-generate supply requirements for the newest forecasts
            # The pipeline saves one DiseaseForecast row per forecast date; we
            # find the most recently created batch and trigger requirements for
            # the first (root) record — the service will handle the whole batch.
            latest = (
                self.db.query(DiseaseForecast)
                .filter(DiseaseForecast.disease_type == disease_type.value)
                .order_by(desc(DiseaseForecast.id))
                .first()
            )
            if latest:
                _auto_generate_supply_requirements(self.db, latest.id)
            
            return forecast_result
            
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise
    
    def get_forecasts(
        self,
        disease_type: Optional[DiseaseType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DiseaseForecast]:
        """Get list of forecasts with optional filters.
        
        Args:
            disease_type: Optional disease type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of DiseaseForecast objects
        """
        query = self.db.query(DiseaseForecast)
        
        if disease_type:
            query = query.filter(DiseaseForecast.disease_type == disease_type.value)
        
        if start_date:
            query = query.filter(DiseaseForecast.forecast_date >= start_date)
        
        if end_date:
            query = query.filter(DiseaseForecast.forecast_date <= end_date)
        
        query = query.order_by(desc(DiseaseForecast.created_at))
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def get_forecast_by_id(self, forecast_id: int) -> Optional[DiseaseForecast]:
        """Get a specific forecast by ID.
        
        Args:
            forecast_id: Forecast ID
        
        Returns:
            DiseaseForecast object or None if not found
        """
        return self.db.query(DiseaseForecast).filter(
            DiseaseForecast.id == forecast_id
        ).first()
    
    def get_latest_forecast(
        self,
        disease_type: DiseaseType,
        location: Optional[str] = None
    ) -> Optional[DiseaseForecast]:
        """Get the most recent forecast for a disease type.
        
        Args:
            disease_type: Type of disease
            location: Optional location filter
        
        Returns:
            Most recent DiseaseForecast object or None
        """
        query = self.db.query(DiseaseForecast).filter(
            DiseaseForecast.disease_type == disease_type.value
        )
        
        # Note: location filtering would require adding location field to DiseaseForecast model
        # For now, we'll just get the latest by created_at
        
        return query.order_by(desc(DiseaseForecast.created_at)).first()
    
    def get_accuracy_metrics(
        self,
        disease_type: Optional[DiseaseType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """Get accuracy metrics for forecasts.
        
        Args:
            disease_type: Optional disease type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            Dictionary containing accuracy metrics (MAE, RMSE, MAPE)
        """
        query = self.db.query(DiseaseForecast)
        
        if disease_type:
            query = query.filter(DiseaseForecast.disease_type == disease_type.value)
        
        if start_date:
            query = query.filter(DiseaseForecast.forecast_date >= start_date)
        
        if end_date:
            query = query.filter(DiseaseForecast.forecast_date <= end_date)
        
        forecasts = query.all()
        
        if not forecasts:
            return {
                "count": 0,
                "mae": None,
                "rmse": None,
                "mape": None
            }
        
        # Calculate average metrics
        mae_values = [f.model_accuracy_mae for f in forecasts if f.model_accuracy_mae is not None]
        rmse_values = [f.model_accuracy_rmse for f in forecasts if f.model_accuracy_rmse is not None]
        mape_values = [f.model_accuracy_mape for f in forecasts if f.model_accuracy_mape is not None]
        
        return {
            "count": len(forecasts),
            "mae": sum(mae_values) / len(mae_values) if mae_values else None,
            "rmse": sum(rmse_values) / len(rmse_values) if rmse_values else None,
            "mape": sum(mape_values) / len(mape_values) if mape_values else None,
            "disease_type": disease_type.value if disease_type else "all",
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }
    
    def get_supply_requirements_for_forecast(
        self,
        forecast_id: int
    ) -> List[Dict]:
        """Get supply requirements associated with a forecast.
        
        Args:
            forecast_id: Forecast ID
        
        Returns:
            List of supply requirements with supply details
        """
        requirements = self.db.query(SupplyRequirement).filter(
            SupplyRequirement.forecast_id == forecast_id
        ).all()
        
        result = []
        for req in requirements:
            supply = self.db.query(MedicalSupply).filter(
                MedicalSupply.id == req.supply_id
            ).first()
            
            result.append({
                "id": req.id,
                "supply_id": req.supply_id,
                "supply_name": supply.name if supply else "Unknown",
                "required_quantity": req.required_quantity,
                "requirement_date": req.requirement_date,
                "disease_type": req.disease_type
            })
        
        return result
