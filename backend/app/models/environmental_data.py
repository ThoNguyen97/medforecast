"""Environmental Data model."""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class EnvironmentalData(Base):
    """Environmental data for forecasting."""
    
    __tablename__ = "environmental_data"
    # Một tháng × một địa bàn chỉ được có MỘT dòng. Không có ràng buộc này thì
    # hai tên khác nhau của cùng một tỉnh nằm ở hai dòng (đã gặp với TP.HCM).
    # SQLite coi các NULL là khác nhau, mà district_ward cấp tỉnh đều NULL —
    # khoá thật nằm ở UNIQUE INDEX trên IFNULL(district_ward, ''), xem
    # scripts/gop_thoi_tiet_trung.py.
    __table_args__ = (
        UniqueConstraint("recorded_at", "location", "district_ward",
                         name="uq_env_thang_diaban"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)  # Tỉnh/Thành (legacy)
    district_ward = Column(String(100), index=True)  # Quận/Huyện hoặc Phường/Xã
    temperature = Column(Numeric(5, 2))  # Celsius (avg_temp)
    humidity = Column(Numeric(5, 2))  # Percentage
    rainfall = Column(Numeric(7, 2))  # mm
    air_quality_index = Column(Integer)
    pm25 = Column(Numeric(7, 2))  # PM2.5 µg/m³
    data_source = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
