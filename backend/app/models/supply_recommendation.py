"""Supply Recommendation model - Đề xuất nhập kho."""
from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SupplyRecommendation(Base):
    """Kết quả tính toán nhu cầu và đề xuất nhập kho thuốc/vật tư.
    
    Được tính từ: dự báo số ca → phân bổ mức độ → nhân định mức → cộng dự phòng → so sánh tồn kho.
    """
    
    __tablename__ = "supply_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Tháng dự báo
    forecast_month = Column(Date, nullable=False, index=True)
    
    # Bệnh
    icd_code = Column(String(20), nullable=False, index=True)
    disease_name = Column(String(200), nullable=False)
    
    # Thuốc/vật tư
    supply_id = Column(Integer, ForeignKey("medical_supplies.id"), nullable=False, index=True)
    drug_code = Column(String(100), index=True)
    ten_hoat_chat = Column(String(200))
    
    # Dự báo số ca
    predicted_cases = Column(Integer, nullable=False)
    predicted_mild = Column(Integer)
    predicted_moderate = Column(Integer)
    predicted_severe = Column(Integer)
    
    # Tính toán nhu cầu
    need_before_buffer = Column(Integer, nullable=False)  # Nhu cầu trước dự phòng
    buffer_rate = Column(Numeric(5, 2), default=15.0)  # Hệ số dự phòng (%)
    predicted_need = Column(Integer, nullable=False)  # Nhu cầu cuối = need_before_buffer × (1 + buffer_rate/100)
    
    # Tồn kho
    current_stock = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)  # Ngưỡng an toàn
    
    # Đề xuất nhập
    suggested_import = Column(Integer, nullable=False)  # max(0, predicted_need + safety_stock - current_stock)
    
    # Trạng thái
    status = Column(String(20), default="pending")  # pending, approved, ordered, completed
    
    # Metadata
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supply = relationship("MedicalSupply", backref="recommendations")
