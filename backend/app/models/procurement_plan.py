"""Procurement Plan model."""
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ProcurementPlan(Base):
    """Procurement plans for medical supplies."""
    
    __tablename__ = "procurement_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    order_quantity = Column(Integer, nullable=False)
    order_date = Column(Date, nullable=False, index=True)
    expected_delivery_date = Column(Date)
    estimated_cost = Column(Numeric(12, 2))
    priority = Column(String(20))
    status = Column(String(50), default="pending", index=True)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    supply = relationship("MedicalSupply", backref="procurement_plans")
    creator = relationship("User")
