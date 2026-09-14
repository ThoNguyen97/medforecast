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
                
                # Kiểm cả hai giá trị TRƯỚC khi gán: gán rồi mới `continue`
                # thì object đã dirty và commit cuối vẫn ghi nửa chừng.
                gia_tri = {}
                hop_le = True
                for cot in ("current_stock", "safety_stock"):
                    if cot not in update_item:
                        continue
                    try:
                        v = int(update_item[cot])
                    except (TypeError, ValueError):
                        hop_le = False
                        break
                    if v < 0:
                        hop_le = False
                        break
                    gia_tri[cot] = v
                if not hop_le:
                    logger.warning("Bỏ qua inventory %s: giá trị không hợp lệ %s", inventory_id, update_item)
                    continue
                for cot, v in gia_tri.items():
                    setattr(inventory, cot, v)
                
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
        
        logger.info(f"Batch updated {len(updated_items)} inventory items")
        return updated_items
    
    def get_low_stock_items(self, threshold_multiplier: float = 1.0) -> List[Inventory]:
        """Thuốc ĐANG HẾT HÀNG (tồn <= 0).

        Lưu ý phạm vi (sửa 09/09/2026):

        Điều kiện cũ là `current_stock <= safety_stock * threshold_multiplier`.
        Trong phạm vi DSS, Inventory.safety_stock đã bị vô hiệu hoá — 5.007/5.041
        dòng có giá trị 0 — nên vế phải luôn bằng 0 và hàm ÂM THẦM thoái hoá
        thành truy vấn "hết hàng", bất kể `threshold_multiplier` truyền vào là
        bao nhiêu. Tham số đó không còn tác dụng gì.

        Thay vì để một điều kiện nói dối về ý nghĩa của nó, hàm nay khai đúng
        việc nó làm. Phân loại "dưới ngưỡng" theo số ngày tồn phủ nhu cầu
        (DOI = tồn hữu dụng FEFO / nhu cầu trung bình ngày) thuộc tầng cảnh báo
        DSS — xem app/services/dss_alerts.py.
        """
        return (
            self.db.query(Inventory)
            .options(joinedload(Inventory.supply))
            .filter(Inventory.current_stock <= 0)
            .all()
        )
    
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
