"""Nghiệp vụ tồn kho (bảng inventory): truy vấn, cập nhật đơn lẻ/hàng loạt kèm audit log."""
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
    """Quản lý tồn kho."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_inventory_items(
        self,
        skip: int = 0,
        limit: int = 100,
        supply_id: Optional[int] = None,
        location: Optional[str] = None
    ) -> List[Inventory]:
        """Danh sách tồn kho, lọc tuỳ chọn theo supply_id và vị trí."""
        query = self.db.query(Inventory).options(joinedload(Inventory.supply))
        
        if supply_id:
            query = query.filter(Inventory.supply_id == supply_id)
        
        if location:
            query = query.filter(Inventory.location == location)
        
        items = query.offset(skip).limit(limit).all()
        return items
    
    def get_inventory_by_id(self, inventory_id: int) -> Inventory:
        """Một dòng tồn kho theo ID; 404 nếu không có."""
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
        """Cập nhật số lượng tồn và ghi audit log."""
        inventory = self.get_inventory_by_id(inventory_id)
        
        old_values = {
            "current_stock": inventory.current_stock,
            "safety_stock": inventory.safety_stock,
            "location": inventory.location
        }
        
        update_data = inventory_data.model_dump(exclude_unset=True)
        
        # Số lượng không được âm.
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
        """Cập nhật hàng loạt; bỏ qua dòng không tồn tại hoặc giá trị không hợp lệ."""
        updated_items = []
        
        for update_item in updates:
            inventory_id = update_item.get("inventory_id")
            if not inventory_id:
                continue
            
            try:
                inventory = self.get_inventory_by_id(inventory_id)
                
                old_values = {
                    "current_stock": inventory.current_stock,
                    "safety_stock": inventory.safety_stock
                }
                
                # Kiểm cả hai giá trị trước khi gán, tránh object dirty rồi commit dở dang.
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
        
        for item in updated_items:
            self.db.refresh(item)
        
        logger.info(f"Batch updated {len(updated_items)} inventory items")
        return updated_items
    
    def get_low_stock_items(self, threshold_multiplier: float = 1.0) -> List[Inventory]:
        """Các dòng tồn kho hết hàng (current_stock <= 0); `threshold_multiplier` không dùng vì safety_stock hầu như bằng 0."""
        return (
            self.db.query(Inventory)
            .options(joinedload(Inventory.supply))
            .filter(Inventory.current_stock <= 0)
            .all()
        )
    
    def get_expiring_items(self, days_threshold: int = 30) -> List[Inventory]:
        """Các dòng tồn kho hết hạn trong vòng `days_threshold` ngày tới."""
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
        """Mọi dòng tồn kho của một vật tư; 404 nếu vật tư không tồn tại."""
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
        """Tổng tồn và tổng tồn an toàn của một vật tư trên mọi vị trí."""
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
        """Tạo dòng tồn kho và ghi audit log (khi có người thực hiện)."""
        supply = self.db.query(MedicalSupply).filter(
            MedicalSupply.id == supply_id
        ).first()
        
        if not supply:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medical supply with ID {supply_id} not found"
            )
        
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
