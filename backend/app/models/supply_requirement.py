"""Supply Requirement model."""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SupplyRequirement(Base):
    """Supply requirements calculated from disease forecasts."""
    
    __tablename__ = "supply_requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_id = Column(Integer, ForeignKey("disease_forecasts.id"), index=True)
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    required_quantity = Column(Integer, nullable=False)
    requirement_date = Column(Date, nullable=False, index=True)
    disease_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    forecast = relationship("DiseaseForecast", backref="supply_requirements")
    supply = relationship("MedicalSupply", backref="requirements")
