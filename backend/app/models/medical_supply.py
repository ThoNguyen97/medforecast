"""Medical Supply model."""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from app.database import Base


class MedicalSupply(Base):
    """Medical supplies master data - 15 thuốc/vật tư cho 4 bệnh hô hấp."""
    
    __tablename__ = "medical_supplies"
    
    id = Column(Integer, primary_key=True, index=True)
    supply_code = Column(String(50), unique=True, nullable=False, index=True)  # VT001, VT002...
    drug_code = Column(String(100), nullable=False, index=True)  # Mã từ cột DrugCode (A2A210200000133...)
    ten_hoat_chat = Column(String(500), nullable=False, index=True)  # Tên từ cột TenHoatChat (một số tên hoạt chất phối hợp dài >200 ký tự)
    unit = Column(String(50), nullable=False)  # Viên, Gói, Lọ, Chai, Cái, Ống
    group_name = Column(String(100), nullable=False, index=True)  # Thuốc hạ sốt, Kháng sinh, Vật tư y tế...
    
    # Thông tin bổ sung
    category = Column(String(100), index=True)  # medicine, medical_supply
    unit_price = Column(Numeric(10, 2))
    minimum_order_quantity = Column(Integer)
    lead_time_days = Column(Integer)
    storage_capacity = Column(Integer)
    description = Column(Text)  # Ghi chú quy cách đại diện
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @hybrid_property
    def name(self):
        """Alias để tương thích code cũ - trả về ten_hoat_chat."""
        return self.ten_hoat_chat
    
    @name.expression
    def name(cls):
        """SQL expression cho query MedicalSupply.name."""
        return cls.ten_hoat_chat
