"""Alert model."""
from sqlalchemy import Column, Integer, String, Date, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Alert(Base):
    """Shortage alerts for medical supplies."""
    
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # critical, high, medium
    current_stock = Column(Integer)
    required_stock = Column(Integer)
    shortage_date = Column(Date)
    message = Column(Text)
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    supply = relationship("MedicalSupply", backref="alerts")
