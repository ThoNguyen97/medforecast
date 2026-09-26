"""Nghiệp vụ dữ liệu môi trường (thời tiết, chất lượng không khí): kiểm tra, nhập tay, truy vấn."""
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from app.models.environmental_data import EnvironmentalData
from app.models.audit_log import AuditLog
from app.schemas.base import EnvironmentalDataCreate
from app.utils.province_alias import ten_chuan

logger = logging.getLogger(__name__)


class EnvironmentalDataService:
    """Quản lý dữ liệu môi trường."""
    
    # Miền giá trị hợp lệ.
    TEMP_MIN = -50.0  # °C
    TEMP_MAX = 60.0   # °C
    HUMIDITY_MIN = 0.0  # %
    HUMIDITY_MAX = 100.0  # %
    RAINFALL_MIN = 0.0  # mm
    RAINFALL_MAX = 1000.0  # mm/ngày
    AQI_MIN = 0
    AQI_MAX = 500
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_environmental_data(self, data: EnvironmentalDataCreate) -> None:
        """Kiểm tra miền giá trị; HTTP 400 kèm danh sách lỗi nếu không hợp lệ."""
        errors = []
        
        if data.temperature is not None:
            if not (self.TEMP_MIN <= data.temperature <= self.TEMP_MAX):
                errors.append(
                    f"Temperature must be between {self.TEMP_MIN}°C and {self.TEMP_MAX}°C"
                )
        
        if data.humidity is not None:
            if not (self.HUMIDITY_MIN <= data.humidity <= self.HUMIDITY_MAX):
                errors.append(
                    f"Humidity must be between {self.HUMIDITY_MIN}% and {self.HUMIDITY_MAX}%"
                )
        
        if data.rainfall is not None:
            if not (self.RAINFALL_MIN <= data.rainfall <= self.RAINFALL_MAX):
                errors.append(
                    f"Rainfall must be between {self.RAINFALL_MIN}mm and {self.RAINFALL_MAX}mm"
                )
        
        if data.air_quality_index is not None:
            if not (self.AQI_MIN <= data.air_quality_index <= self.AQI_MAX):
                errors.append(
                    f"Air Quality Index must be between {self.AQI_MIN} and {self.AQI_MAX}"
                )
        
        # Cần ít nhất một chỉ số đo.
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
        """Danh sách dữ liệu môi trường, lọc tuỳ chọn theo địa điểm."""
        query = self.db.query(EnvironmentalData).order_by(
            desc(EnvironmentalData.recorded_at)
        )
        
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
        """Tạo bản ghi môi trường (chuẩn hoá tên tỉnh) và ghi audit log."""
        self.validate_environmental_data(data)
        
        env_data = EnvironmentalData(
            recorded_at=data.recorded_at,
            location=ten_chuan(data.location),
            temperature=data.temperature,
            humidity=data.humidity,
            rainfall=data.rainfall,
            air_quality_index=data.air_quality_index,
            pm25=data.pm25,
            data_source=data.data_source or "manual"
        )
        
        self.db.add(env_data)
        self.db.flush()
        
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
        """Bản ghi môi trường mới nhất; 404 nếu không có."""
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
        """Dữ liệu môi trường trong khoảng ngày."""
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
