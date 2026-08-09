"""Inventory model."""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Inventory(Base):
    """Inventory tracking for medical supplies."""
    
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    current_stock = Column(Integer, nullable=False)
    safety_stock = Column(Integer, nullable=False)
    location = Column(String(100))
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    supply = relationship("MedicalSupply", backref="inventory_items")
    updater = relationship("User")
