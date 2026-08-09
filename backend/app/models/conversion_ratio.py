"""Conversion Ratio model."""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ConversionRatio(Base):
    """Conversion ratios from disease cases to supply requirements."""
    
    __tablename__ = "conversion_ratios"
    
    id = Column(Integer, primary_key=True, index=True)
    disease_type = Column(String(100), nullable=False, index=True)
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    ratio = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(50))
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supply = relationship("MedicalSupply", backref="conversion_ratios")
    updater = relationship("User")
