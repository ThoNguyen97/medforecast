"""Supply Requirements API endpoints."""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.base import (
    SupplyRequirementResponse,
    SupplyRequirementSummaryResponse,
)
from app.services.supply_requirement_service import SupplyRequirementService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["supply-requirements"])


@router.get("", response_model=List[SupplyRequirementResponse])
async def list_supply_requirements(
    forecast_id: Optional[int] = Query(None, description="Filter by forecast ID"),
    supply_id: Optional[int] = Query(None, description="Filter by supply ID"),
    disease_type: Optional[str] = Query(None, description="Filter by disease type"),
    start_date: Optional[date] = Query(None, description="Filter by requirement date (start)"),
    end_date: Optional[date] = Query(None, description="Filter by requirement date (end)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List supply requirements with optional filters.

    Returns requirements enriched with supply names and current stock
    comparison (shortage amounts).
    """
    logger.info(f"Listing supply requirements requested by user {current_user.username}")

    try:
        service = SupplyRequirementService(db)
        requirements = service.list_requirements(
            forecast_id=forecast_id,
            supply_id=supply_id,
            disease_type=disease_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return requirements

    except Exception as e:
        logger.error(f"Error listing supply requirements: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supply requirements")


@router.get("/summary", response_model=SupplyRequirementSummaryResponse)
async def get_supply_requirements_summary(
    disease_type: Optional[str] = Query(None, description="Filter by disease type"),
    category: Optional[str] = Query(None, description="Filter by supply category"),
    start_date: Optional[date] = Query(None, description="Filter by requirement date (start)"),
    end_date: Optional[date] = Query(None, description="Filter by requirement date (end)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a summary of supply requirements aggregated by supply type.

    Each item includes the total required quantity, current inventory stock,
    and the shortage amount (max(0, required - stock)).
    """
    logger.info(f"Supply requirements summary requested by user {current_user.username}")

    try:
        service = SupplyRequirementService(db)
        summary = service.get_summary(
            disease_type=disease_type,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
        return summary

    except Exception as e:
        logger.error(f"Error getting supply requirements summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supply requirements summary")


@router.get("/forecast/{forecast_id}", response_model=List[SupplyRequirementResponse])
async def get_requirements_for_forecast(
    forecast_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all supply requirements associated with a specific forecast.

    Args:
        forecast_id: The ID of the disease forecast.

    Returns:
        List of supply requirements for that forecast, including stock comparison.
    """
    logger.info(
        f"Getting supply requirements for forecast {forecast_id} "
        f"requested by user {current_user.username}"
    )

    try:
        service = SupplyRequirementService(db)

        # Verify forecast exists
        from app.models.disease_forecast import DiseaseForecast

        forecast = db.query(DiseaseForecast).filter(
            DiseaseForecast.id == forecast_id
        ).first()
        if not forecast:
            raise HTTPException(status_code=404, detail="Forecast not found")

        requirements = service.get_requirements_for_forecast(forecast_id)
        return requirements

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting supply requirements for forecast {forecast_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supply requirements")


@router.post("/generate/{forecast_id}", status_code=201)
async def generate_requirements_for_forecast(
    forecast_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger supply requirement generation for a forecast.

    Useful when requirements were not auto-generated or need to be refreshed.
    Requirements are calculated using the ConversionModule and stored in the
    database linked to the forecast.

    Args:
        forecast_id: The ID of the disease forecast.
    """
    logger.info(
        f"Manual supply requirement generation for forecast {forecast_id} "
        f"requested by user {current_user.username}"
    )

    try:
        from app.models.disease_forecast import DiseaseForecast

        forecast = db.query(DiseaseForecast).filter(
            DiseaseForecast.id == forecast_id
        ).first()
        if not forecast:
            raise HTTPException(status_code=404, detail="Forecast not found")

        service = SupplyRequirementService(db)
        requirements = service.generate_requirements_for_forecast(forecast_id)

        return {
            "message": f"Generated {len(requirements)} supply requirements for forecast {forecast_id}",
            "forecast_id": forecast_id,
            "requirements_count": len(requirements),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating supply requirements for forecast {forecast_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate supply requirements")
