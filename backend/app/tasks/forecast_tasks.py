"""Celery tasks for forecast generation."""
import logging
from typing import Dict

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.forecast_service import ForecastService
from app.schemas.base import DiseaseType

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_forecast_async", bind=True)
def generate_forecast_async(
    self,
    disease_type: str,
    forecast_period_days: int,
    location: str = None
) -> Dict:
    """Generate forecast asynchronously using Celery.
    
    Args:
        self: Celery task instance (bound)
        disease_type: Type of disease to forecast
        forecast_period_days: Number of days to forecast (7-30)
        location: Optional location filter
    
    Returns:
        Dictionary containing forecast results
    """
    logger.info(f"Starting async forecast generation: {disease_type}, {forecast_period_days} days")
    
    # Update task state to STARTED
    self.update_state(state="STARTED", meta={"status": "Initializing forecast generation"})
    
    db = SessionLocal()
    try:
        # Convert string to DiseaseType enum
        disease_type_enum = DiseaseType(disease_type)
        
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Loading models and data"})
        
        # Create forecast service
        forecast_service = ForecastService(db)
        
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Generating predictions"})
        
        # Generate forecast
        result = forecast_service.generate_forecast(
            disease_type=disease_type_enum,
            forecast_period_days=forecast_period_days,
            location=location
        )
        
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "Saving results"})
        
        logger.info(f"Async forecast generation completed: {len(result['predictions'])} predictions")
        
        return {
            "status": "completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error in async forecast generation: {str(e)}")
        # Update task state to FAILURE
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Failed",
                "error": str(e)
            }
        )
        raise
    finally:
        db.close()
