"""Environmental Data service layer."""
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from app.models.environmental_data import EnvironmentalData
from app.models.audit_log import AuditLog
from app.schemas.base import EnvironmentalDataCreate

logger = logging.getLogger(__name__)


class EnvironmentalDataService:
    """Service for managing environmental data."""
    
    # Validation ranges for environmental data
    TEMP_MIN = -50.0  # Celsius
    TEMP_MAX = 60.0   # Celsius
    HUMIDITY_MIN = 0.0  # Percentage
    HUMIDITY_MAX = 100.0  # Percentage
    RAINFALL_MIN = 0.0  # mm
    RAINFALL_MAX = 1000.0  # mm (per day)
    AQI_MIN = 0
    AQI_MAX = 500
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_environmental_data(self, data: EnvironmentalDataCreate) -> None:
        """
        Validate environmental data for reasonable value ranges.
        
        Raises HTTPException if validation fails.
        """
        errors = []
        
        # Validate temperature
        if data.temperature is not None:
            if not (self.TEMP_MIN <= data.temperature <= self.TEMP_MAX):
                errors.append(
                    f"Temperature must be between {self.TEMP_MIN}°C and {self.TEMP_MAX}°C"
                )
        
        # Validate humidity
        if data.humidity is not None:
            if not (self.HUMIDITY_MIN <= data.humidity <= self.HUMIDITY_MAX):
                errors.append(
                    f"Humidity must be between {self.HUMIDITY_MIN}% and {self.HUMIDITY_MAX}%"
                )
        
        # Validate rainfall
        if data.rainfall is not None:
            if not (self.RAINFALL_MIN <= data.rainfall <= self.RAINFALL_MAX):
                errors.append(
                    f"Rainfall must be between {self.RAINFALL_MIN}mm and {self.RAINFALL_MAX}mm"
                )
        
        # Validate air quality index
        if data.air_quality_index is not None:
            if not (self.AQI_MIN <= data.air_quality_index <= self.AQI_MAX):
                errors.append(
                    f"Air Quality Index must be between {self.AQI_MIN} and {self.AQI_MAX}"
                )
        
        # Check if at least one measurement is provided
        if all(v is None for v in [
            data.temperature,
            data.humidity,
            data.rainfall,
            data.air_quality_index
        ]):
            errors.append("At least one environmental measurement must be provided")
        
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid environmental data", "errors": errors}
            )
    
    def get_environmental_data(
        self,
        skip: int = 0,
        limit: int = 100,
        location: Optional[str] = None
    ) -> List[EnvironmentalData]:
        """Get list of environmental data records with optional filtering."""
        query = self.db.query(EnvironmentalData).order_by(
            desc(EnvironmentalData.recorded_at)
        )
        
        # Filter by location
        if location:
            query = query.filter(EnvironmentalData.location == location)
        
        data = query.offset(skip).limit(limit).all()
        return data
    
    def create_environmental_data(
        self,
        data: EnvironmentalDataCreate,
        created_by_user_id: int,
        ip_address: str
    ) -> EnvironmentalData:
        """Create a new environmental data record."""
        # Validate data
        self.validate_environmental_data(data)
        
        # Create record
        env_data = EnvironmentalData(
            recorded_at=data.recorded_at,
            location=data.location,
            temperature=data.temperature,
            humidity=data.humidity,
            rainfall=data.rainfall,
            air_quality_index=data.air_quality_index,
            data_source=data.data_source or "manual"
        )
        
        self.db.add(env_data)
        self.db.flush()
        
        # Log the action
        audit_log = AuditLog(
            user_id=created_by_user_id,
            action="CREATE_ENVIRONMENTAL_DATA",
            table_name="environmental_data",
            record_id=env_data.id,
            new_value={
                "location": data.location,
                "temperature": data.temperature,
                "humidity": data.humidity,
                "rainfall": data.rainfall,
                "air_quality_index": data.air_quality_index,
                "recorded_at": data.recorded_at.isoformat()
            },
            ip_address=ip_address
        )
        self.db.add(audit_log)
        
        self.db.commit()
        self.db.refresh(env_data)
        
        logger.info(
            f"Created environmental data ID: {env_data.id} for location: {env_data.location}"
        )
        return env_data
    
    def get_latest_data(self, location: Optional[str] = None) -> EnvironmentalData:
        """Get the latest environmental data record."""
        query = self.db.query(EnvironmentalData).order_by(
            desc(EnvironmentalData.recorded_at)
        )
        
        if location:
            query = query.filter(EnvironmentalData.location == location)
        
        data = query.first()
        
        if not data:
            location_msg = f" for location '{location}'" if location else ""
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No environmental data found{location_msg}"
            )
        
        return data
    
    def get_data_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        location: Optional[str] = None
    ) -> List[EnvironmentalData]:
        """Get environmental data for a specific date range."""
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date"
            )
        
        query = self.db.query(EnvironmentalData).filter(
            EnvironmentalData.recorded_at >= start_date,
            EnvironmentalData.recorded_at <= end_date
        ).order_by(EnvironmentalData.recorded_at)
        
        if location:
            query = query.filter(EnvironmentalData.location == location)
        
        data = query.all()
        return data
