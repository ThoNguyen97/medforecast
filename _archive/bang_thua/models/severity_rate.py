"""Severity Rate model - Tỷ lệ phân bổ mức độ bệnh."""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class SeverityRate(Base):
    """Tỷ lệ phân bổ ca nhẹ/trung bình/nặng theo từng bệnh.
    
    Admin có thể cấu hình tỷ lệ này. Sau này có thể tự động tính từ dữ liệu lịch sử.
    """
    
    __tablename__ = "severity_rates"
    __table_args__ = (UniqueConstraint("icd_code", name="uq_severity_icd"),)
    
    id = Column(Integer, primary_key=True, index=True)
    icd_code = Column(String(20), nullable=False, unique=True, index=True)  # J20, J06, J02, J01
    disease_name = Column(String(200), nullable=False)
    
    # Tỷ lệ phần trăm (tổng = 100%)
    mild_rate = Column(Numeric(5, 2), nullable=False)  # Tỷ lệ nhẹ (0-100)
    moderate_rate = Column(Numeric(5, 2), nullable=False)  # Tỷ lệ trung bình (0-100)
    severe_rate = Column(Numeric(5, 2), nullable=False)  # Tỷ lệ nặng (0-100)
    
    # Ghi chú
    note = Column(String(500))
    
    # Metadata
    updated_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
