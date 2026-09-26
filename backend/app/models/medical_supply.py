"""Model danh mục thuốc/vật tư y tế."""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from app.database import Base


class MedicalSupply(Base):
    """Danh mục thuốc/vật tư y tế dùng cho nhóm bệnh hô hấp."""
    
    __tablename__ = "medical_supplies"
    
    id = Column(Integer, primary_key=True, index=True)
    supply_code = Column(String(50), unique=True, nullable=False, index=True)  # VT001…
    drug_code = Column(String(100), nullable=False, index=True)  # Mã thuốc HIS (DrugCode)
    ten_hoat_chat = Column(String(500), nullable=False, index=True)  # hoạt chất phối hợp có thể > 200 ký tự
    unit = Column(String(50), nullable=False)
    group_name = Column(String(100), nullable=False, index=True)
    
    category = Column(String(100), index=True)  # medicine | medical_supply
    unit_price = Column(Numeric(10, 2))
    # MOQ và lead time giữ trong CSDL, không đưa ra API/UI (ngoài phạm vi DSS)
    minimum_order_quantity = Column(Integer)
    lead_time_days = Column(Integer)
    storage_capacity = Column(Integer)
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @hybrid_property
    def name(self):
        """Bí danh của ten_hoat_chat."""
        return self.ten_hoat_chat
    
    @name.expression
    def name(cls):
        """Biểu thức SQL cho MedicalSupply.name."""
        return cls.ten_hoat_chat
