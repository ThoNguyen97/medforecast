"""Disease Case service layer."""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException, status

from app.models.disease_case import DiseaseCase
from app.models.audit_log import AuditLog
from app.schemas.base import DiseaseCaseCreate, DiseaseType

logger = logging.getLogger(__name__)


class DiseaseCaseService:
    """Service for managing disease case data."""
    
    # 4 bệnh hô hấp được chọn để dự báo
    VALID_DISEASE_TYPES = [
        DiseaseType.J20.value,  # Viêm phế quản cấp
        DiseaseType.J06.value,  # Nhiễm trùng đường hô hấp trên cấp
        DiseaseType.J02.value,  # Viêm họng cấp
        DiseaseType.J01.value,  # Viêm xoang cấp
    ]
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_disease_case_data(self, data: DiseaseCaseCreate) -> None:
        """
        Validate disease case data.
        
        Raises HTTPException if validation fails.
        """
        errors = []
        
        # Validate non-negative case count
        if data.case_count < 0:
            errors.append("Case count must be non-negative")
        
        # Validate ICD code (mã bệnh)
        if data.icd_code not in self.VALID_DISEASE_TYPES:
            errors.append(
                f"Invalid ICD code. Must be one of: {', '.join(self.VALID_DISEASE_TYPES)}"
            )
        
        # Validate location is not empty
        if not data.location or not data.location.strip():
            errors.append("Location must not be empty")
        
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid disease case data", "errors": errors}
            )
    
    def get_disease_cases(
        self,
        skip: int = 0,
        limit: int = 100,
        icd_code: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[DiseaseCase]:
        """Get list of disease case records with optional filtering."""
        query = self.db.query(DiseaseCase).order_by(
            desc(DiseaseCase.recorded_at)
        )
        
        # Filter by ICD code
        if icd_code:
            query = query.filter(DiseaseCase.icd_code == icd_code)
        
        # Filter by location
        if location:
            query = query.filter(DiseaseCase.location == location)
        
        cases = query.offset(skip).limit(limit).all()
        return cases
    
    def create_disease_case(
        self,
        data: DiseaseCaseCreate,
        created_by_user_id: int,
        ip_address: str
    ) -> DiseaseCase:
        """Create a new disease case record."""
        # Validate data
        self.validate_disease_case_data(data)
        
        # Create record
        disease_case = DiseaseCase(
            recorded_at=data.recorded_at,
            icd_code=data.icd_code,
            disease_name=data.disease_name,
            disease_type=data.disease_type or "respiratory",
            case_count=data.case_count,
            location=data.location,
            district_ward=data.district_ward,
            severity=data.severity,
            length_of_stay=data.length_of_stay,
            sub_icd_count=data.sub_icd_count,
            data_source=data.data_source or "manual",
            note=data.note,
        )
        
        self.db.add(disease_case)
        self.db.flush()
        
        # Log the action
        audit_log = AuditLog(
            user_id=created_by_user_id,
            action="CREATE_DISEASE_CASE",
            table_name="disease_cases",
            record_id=disease_case.id,
            new_value={
                "icd_code": data.icd_code,
                "disease_name": data.disease_name,
                "case_count": data.case_count,
                "location": data.location,
                "recorded_at": data.recorded_at.isoformat()
            },
            ip_address=ip_address
        )
        self.db.add(audit_log)
        
        self.db.commit()
        self.db.refresh(disease_case)
        
        logger.info(
            f"Created disease case ID: {disease_case.id} for {disease_case.icd_code} - "
            f"{disease_case.disease_name} at {disease_case.location}"
        )
        return disease_case
    
    def get_statistics(
        self,
        location: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get statistics by ICD code.
        
        Returns total case counts grouped by ICD code.
        """
        query = self.db.query(
            DiseaseCase.icd_code,
            DiseaseCase.disease_name,
            func.sum(DiseaseCase.case_count).label("total_cases"),
            func.count(DiseaseCase.id).label("record_count"),
            func.max(DiseaseCase.recorded_at).label("latest_record")
        ).group_by(DiseaseCase.icd_code, DiseaseCase.disease_name)
        
        # Apply filters
        if location:
            query = query.filter(DiseaseCase.location == location)
        
        if start_date:
            query = query.filter(DiseaseCase.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(DiseaseCase.recorded_at <= end_date)
        
        results = query.all()
        
        # Format results
        statistics = []
        for row in results:
            statistics.append({
                "icd_code": row.icd_code,
                "disease_name": row.disease_name,
                "total_cases": int(row.total_cases) if row.total_cases else 0,
                "record_count": row.record_count,
                "latest_record": row.latest_record.isoformat() if row.latest_record else None
            })
        
        return statistics
    
    def get_trends(
        self,
        icd_code: Optional[str] = None,
        location: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get trend data (time series) for disease cases.
        
        Returns case counts over time, optionally filtered by ICD code and location.
        """
        query = self.db.query(
            func.date(DiseaseCase.recorded_at).label("date"),
            DiseaseCase.icd_code,
            DiseaseCase.disease_name,
            DiseaseCase.location,
            func.sum(DiseaseCase.case_count).label("total_cases")
        ).group_by(
            func.date(DiseaseCase.recorded_at),
            DiseaseCase.icd_code,
            DiseaseCase.disease_name,
            DiseaseCase.location
        ).order_by(desc(func.date(DiseaseCase.recorded_at)))
        
        # Apply filters
        if icd_code:
            query = query.filter(DiseaseCase.icd_code == icd_code)
        
        if location:
            query = query.filter(DiseaseCase.location == location)
        
        if start_date:
            query = query.filter(DiseaseCase.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(DiseaseCase.recorded_at <= end_date)
        
        results = query.limit(limit).all()
        
        # Format results
        trends = []
        for row in results:
            # SQLite's func.date() returns a string, not a date object
            date_str = row.date if isinstance(row.date, str) else (row.date.isoformat() if row.date else None)
            trends.append({
                "date": date_str,
                "icd_code": row.icd_code,
                "disease_name": row.disease_name,
                "location": row.location,
                "total_cases": int(row.total_cases) if row.total_cases else 0
            })
        
        return trends
