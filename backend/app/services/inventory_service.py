"""Inventory service layer."""
import logging
from typing import List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.audit_log import AuditLog
from app.schemas.base import InventoryUpdate

logger = logging.getLogger(__name__)


def _trigger_alert_check(db: Session, supply_id: int) -> None:
    """
    Re-evaluate alerts for a supply after an inventory update.

    Imported lazily to avoid circular imports between inventory_service and
    alert_service.
    """
    try:
        from app.services.alert_service import AlertModule

        module = AlertModule(db)
        resolved = module.check_and_resolve_alerts_for_supply(supply_id)
        if resolved:
            logger.info(
                f"Auto-resolved alert for supply_id={supply_id} "
                "after inventory update"
            )
    except Exception as exc:
        # Alert check failures should not break inventory updates
        logger.warning(
            f"Alert check failed for supply_id={supply_id} "
            f"after inventory update: {exc}"
        )


class InventoryService:
    """Service for managing inventory."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_inventory_items(
        self,
        skip: int = 0,
        limit: int = 100,
        supply_id: Optional[int] = None,
        location: Optional[str] = None
    ) -> List[Inventory]:
        """Get list of inventory items with optional filtering."""
        query = self.db.query(Inventory).options(joinedload(Inventory.supply))
        
        # Filter by supply_id
        if supply_id:
            query = query.filter(Inventory.supply_id == supply_id)
        
        # Filter by location
        if location:
            query = query.filter(Inventory.location == location)
        
        items = query.offset(skip).limit(limit).all()
        return items
    
    def get_inventory_by_id(self, inventory_id: int) -> Inventory:
        """Get inventory item by ID."""
        inventory = self.db.query(Inventory).options(
            joinedload(Inventory.supply)
        ).filter(Inventory.id == inventory_id).first()
        
        if not inventory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory item with ID {inventory_id} not found"
            )
        
        return inventory
    
    def update_inventory(
        self,
        inventory_id: int,
        inventory_data: InventoryUpdate,
        updated_by_user_id: int,
        ip_address: str
    ) -> Inventory:
        """Update inventory stock levels."""
        inventory = self.get_inventory_by_id(inventory_id)
        
        # Store old values for audit
        old_values = {
            "current_stock": inventory.current_stock,
            "safety_stock": inventory.safety_stock,
            "location": inventory.location
        }
        
        # Update fields
        update_data = inventory_data.model_dump(exclude_unset=True)
        
        # Validate non-negative quantities
        if "current_stock" in update_data and update_data["current_stock"] < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current stock cannot be negative"
            )
        
        if "safety_stock" in update_data and update_data["safety_stock"] < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Safety stock cannot be negative"
            )
        
        for field, value in update_data.items():
            setattr(inventory, field, value)
        
        inventory.updated_by = updated_by_user_id
        
        # Log the action
        audit_log = AuditLog(
            user_id=updated_by_user_id,
            action="UPDATE_INVENTORY",
            table_name="inventory",
            record_id=inventory.id,
            old_value=old_values,
            new_value=update_data,
            ip_address=ip_address
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(inventory)

        # Auto-resolve alerts if stock is now sufficient
        _trigger_alert_check(self.db, inventory.supply_id)

        logger.info(f"Updated inventory ID: {inventory.id} for supply: {inventory.supply.name}")
        return inventory
    
    def batch_update_inventory(
        self,
        updates: List[dict],
        updated_by_user_id: int,
        ip_address: str
    ) -> List[Inventory]:
        """Batch update multiple inventory items."""
        updated_items = []
        
        for update_item in updates:
            inventory_id = update_item.get("inventory_id")
            if not inventory_id:
                continue
            
            try:
                inventory = self.get_inventory_by_id(inventory_id)
                
                # Store old values
                old_values = {
                    "current_stock": inventory.current_stock,
                    "safety_stock": inventory.safety_stock
                }
                
                # Update stock levels
                if "current_stock" in update_item:
                    if update_item["current_stock"] < 0:
                        logger.warning(f"Skipping inventory {inventory_id}: negative stock")
                        continue
                    inventory.current_stock = update_item["current_stock"]
                
                if "safety_stock" in update_item:
                    if update_item["safety_stock"] < 0:
                        logger.warning(f"Skipping inventory {inventory_id}: negative safety stock")
                        continue
                    inventory.safety_stock = update_item["safety_stock"]
                
                inventory.updated_by = updated_by_user_id
                
                # Log the action
                audit_log = AuditLog(
                    user_id=updated_by_user_id,
                    action="BATCH_UPDATE_INVENTORY",
                    table_name="inventory",
                    record_id=inventory.id,
                    old_value=old_values,
                    new_value=update_item,
                    ip_address=ip_address
                )
                self.db.add(audit_log)
                
                updated_items.append(inventory)
                
            except HTTPException:
                logger.warning(f"Inventory item {inventory_id} not found, skipping")
                continue
        
        self.db.commit()
        
        # Refresh all items
        for item in updated_items:
            self.db.refresh(item)
        
        # Auto-resolve alerts for each updated supply
        updated_supply_ids = {item.supply_id for item in updated_items}
        for supply_id in updated_supply_ids:
            _trigger_alert_check(self.db, supply_id)

        logger.info(f"Batch updated {len(updated_items)} inventory items")
        return updated_items
    
    def get_low_stock_items(self, threshold_multiplier: float = 1.0) -> List[Inventory]:
        """
        Get inventory items with low stock.
        
        Low stock is defined as current_stock <= safety_stock * threshold_multiplier
        """
        items = self.db.query(Inventory).options(
            joinedload(Inventory.supply)
        ).filter(
            Inventory.current_stock <= Inventory.safety_stock * threshold_multiplier
        ).all()
        
        return items
    
    def get_expiring_items(self, days_threshold: int = 30) -> List[Inventory]:
        """
        Get inventory items expiring within the specified number of days.
        """
        threshold_date = date.today() + timedelta(days=days_threshold)
        
        items = self.db.query(Inventory).options(
            joinedload(Inventory.supply)
        ).filter(
            Inventory.expiry_date.isnot(None),
            Inventory.expiry_date <= threshold_date,
            Inventory.expiry_date >= date.today()
        ).order_by(Inventory.expiry_date).all()
        
        return items
    
    def get_inventory_by_supply(self, supply_id: int) -> List[Inventory]:
        """Get all inventory items for a specific supply."""
        # Verify supply exists
        supply = self.db.query(MedicalSupply).filter(
            MedicalSupply.id == supply_id
        ).first()
        
        if not supply:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medical supply with ID {supply_id} not found"
            )
        
        items = self.db.query(Inventory).options(
            joinedload(Inventory.supply)
        ).filter(Inventory.supply_id == supply_id).all()
        
        return items
    
    def get_total_stock_by_supply(self, supply_id: int) -> dict:
        """Get total stock across all locations for a supply."""
        result = self.db.query(
            func.sum(Inventory.current_stock).label("total_stock"),
            func.sum(Inventory.safety_stock).label("total_safety_stock")
        ).filter(Inventory.supply_id == supply_id).first()
        
        return {
            "supply_id": supply_id,
            "total_stock": result.total_stock or 0,
            "total_safety_stock": result.total_safety_stock or 0
        }
    
    def create_inventory_item(
        self,
        supply_id: int,
        current_stock: int,
        safety_stock: int,
        location: Optional[str] = None,
        batch_number: Optional[str] = None,
        expiry_date: Optional[date] = None,
        created_by_user_id: int = None,
        ip_address: str = None
    ) -> Inventory:
        """Create a new inventory item."""
        # Verify supply exists
        supply = self.db.query(MedicalSupply).filter(
            MedicalSupply.id == supply_id
        ).first()
        
        if not supply:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medical supply with ID {supply_id} not found"
            )
        
        # Validate quantities
        if current_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current stock cannot be negative"
            )
        
        if safety_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Safety stock cannot be negative"
            )
        
        # Create inventory item
        inventory = Inventory(
            supply_id=supply_id,
            current_stock=current_stock,
            safety_stock=safety_stock,
            location=location,
            batch_number=batch_number,
            expiry_date=expiry_date,
            updated_by=created_by_user_id
        )
        
        self.db.add(inventory)
        self.db.flush()
        
        # Log the action
        if created_by_user_id and ip_address:
            audit_log = AuditLog(
                user_id=created_by_user_id,
                action="CREATE_INVENTORY",
                table_name="inventory",
                record_id=inventory.id,
                new_value={
                    "supply_id": supply_id,
                    "current_stock": current_stock,
                    "safety_stock": safety_stock,
                    "location": location
                },
                ip_address=ip_address
            )
            self.db.add(audit_log)
        
        self.db.commit()
        self.db.refresh(inventory)
        
        logger.info(f"Created inventory item ID: {inventory.id} for supply: {supply.name}")
        return inventory
