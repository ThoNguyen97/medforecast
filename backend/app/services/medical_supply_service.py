"""Medical Supply service layer."""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.medical_supply import MedicalSupply
from app.models.audit_log import AuditLog
from app.schemas.base import MedicalSupplyCreate, MedicalSupplyUpdate

logger = logging.getLogger(__name__)


class MedicalSupplyService:
    """Service for managing medical supplies."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_supply(
        self,
        supply_data: MedicalSupplyCreate,
        created_by_user_id: int,
        ip_address: str
    ) -> MedicalSupply:
        """Create a new medical supply."""
        # Check if supply with same name already exists
        existing = self.db.query(MedicalSupply).filter(
            MedicalSupply.name == supply_data.name
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medical supply with name '{supply_data.name}' already exists"
            )
        
        # Create new supply
        new_supply = MedicalSupply(**supply_data.model_dump())
        self.db.add(new_supply)
        self.db.flush()
        
        # Log the action
        audit_log = AuditLog(
            user_id=created_by_user_id,
            action="CREATE_MEDICAL_SUPPLY",
            table_name="medical_supplies",
            record_id=new_supply.id,
            new_value=supply_data.model_dump(),
            ip_address=ip_address
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(new_supply)
        
        logger.info(f"Created medical supply: {new_supply.name} (ID: {new_supply.id})")
        return new_supply
    
    def get_supplies(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[MedicalSupply]:
        """Get list of medical supplies with optional filtering."""
        query = self.db.query(MedicalSupply)
        
        # Filter by category
        if category:
            query = query.filter(MedicalSupply.category == category)
        
        # Search by name
        if search:
            query = query.filter(MedicalSupply.name.ilike(f"%{search}%"))
        
        supplies = query.offset(skip).limit(limit).all()
        return supplies
    
    def get_supply_by_id(self, supply_id: int) -> Optional[MedicalSupply]:
        """Get medical supply by ID."""
        supply = self.db.query(MedicalSupply).filter(
            MedicalSupply.id == supply_id
        ).first()
        
        if not supply:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medical supply with ID {supply_id} not found"
            )
        
        return supply
    
    def update_supply(
        self,
        supply_id: int,
        supply_data: MedicalSupplyUpdate,
        updated_by_user_id: int,
        ip_address: str
    ) -> MedicalSupply:
        """Update medical supply information."""
        supply = self.get_supply_by_id(supply_id)
        
        # Store old values for audit
        old_values = {
            "name": supply.name,
            "category": supply.category,
            "unit": supply.unit,
            "unit_price": float(supply.unit_price) if supply.unit_price else None,
            "minimum_order_quantity": supply.minimum_order_quantity,
            "lead_time_days": supply.lead_time_days,
            "storage_capacity": supply.storage_capacity,
            "description": supply.description
        }
        
        # Update fields
        update_data = supply_data.model_dump(exclude_unset=True)
        
        # Check if name is being changed and if it conflicts
        if "name" in update_data and update_data["name"] != supply.name:
            existing = self.db.query(MedicalSupply).filter(
                MedicalSupply.name == update_data["name"],
                MedicalSupply.id != supply_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Medical supply with name '{update_data['name']}' already exists"
                )
        
        for field, value in update_data.items():
            setattr(supply, field, value)
        
        # Log the action
        audit_log = AuditLog(
            user_id=updated_by_user_id,
            action="UPDATE_MEDICAL_SUPPLY",
            table_name="medical_supplies",
            record_id=supply.id,
            old_value=old_values,
            new_value=update_data,
            ip_address=ip_address
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(supply)
        
        logger.info(f"Updated medical supply ID: {supply.id}")
        return supply
    
    def delete_supply(
        self,
        supply_id: int,
        deleted_by_user_id: int,
        ip_address: str
    ) -> None:
        """Delete medical supply."""
        supply = self.get_supply_by_id(supply_id)
        
        # Store values for audit
        old_values = {
            "name": supply.name,
            "category": supply.category,
            "unit": supply.unit
        }
        
        # Log the action before deletion
        audit_log = AuditLog(
            user_id=deleted_by_user_id,
            action="DELETE_MEDICAL_SUPPLY",
            table_name="medical_supplies",
            record_id=supply.id,
            old_value=old_values,
            ip_address=ip_address
        )
        self.db.add(audit_log)
        
        # Delete the supply
        self.db.delete(supply)
        self.db.commit()
        
        logger.info(f"Deleted medical supply ID: {supply_id}")
    
    def get_categories(self) -> List[str]:
        """Get list of unique categories."""
        categories = self.db.query(MedicalSupply.category).distinct().all()
        return [cat[0] for cat in categories if cat[0]]
