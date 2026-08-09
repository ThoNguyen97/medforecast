"""Disease Supply Norm model - Định mức thuốc/vật tư theo bệnh và mức độ."""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class DiseaseSupplyNorm(Base):
    """Định mức số lượng thuốc/vật tư cần dùng cho 1 ca bệnh theo mức độ.
    
    Ví dụ: J20 (Viêm phế quản cấp) mức độ nặng cần 10 gói N-acetylcysteine.
    """
    
    __tablename__ = "disease_supply_norms"
    __table_args__ = (
        UniqueConstraint("icd_code", "severity", "supply_id", name="uq_disease_severity_supply"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Bệnh
    icd_code = Column(String(20), nullable=False, index=True)  # J20, J06, J02, J01
    disease_name = Column(String(200), nullable=False)
    
    # Mức độ
    severity = Column(String(20), nullable=False, index=True)  # mild, moderate, severe
    
    # Thuốc/vật tư
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    
    # Định mức (số lượng cho 1 ca bệnh)
    quantity_per_case = Column(Integer, nullable=False, default=0)
    
    # Metadata
    updated_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supply = relationship("MedicalSupply", backref="disease_norms")
