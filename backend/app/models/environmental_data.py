"""Model dữ liệu môi trường (thời tiết, chất lượng không khí)."""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class EnvironmentalData(Base):
    """Dữ liệu môi trường theo tháng và địa bàn."""
    
    __tablename__ = "environmental_data"
    # SQLite coi các NULL khác nhau nên khoá thực thi nằm ở UNIQUE INDEX trên IFNULL(district_ward, '')
    __table_args__ = (
        UniqueConstraint("recorded_at", "location", "district_ward",
                         name="uq_env_thang_diaban"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)  # Tỉnh/Thành
    district_ward = Column(String(100), index=True)  # Quận/Huyện hoặc Phường/Xã
    temperature = Column(Numeric(5, 2))  # °C
    humidity = Column(Numeric(5, 2))  # %
    rainfall = Column(Numeric(7, 2))  # mm
    air_quality_index = Column(Integer)
    pm25 = Column(Numeric(7, 2))  # µg/m³
    data_source = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
