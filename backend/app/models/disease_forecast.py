"""Model kết quả dự báo số ca bệnh."""
from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DiseaseForecast(Base):
    """Dự báo số ca theo nhóm ICD hô hấp, đầu ra của ensemble chuỗi thời gian (Tầng 1)."""
    
    __tablename__ = "disease_forecasts"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_month = Column(Date, nullable=False, index=True)  # Tháng dự báo (ngày đầu tháng)
    forecast_date = Column(Date, nullable=False, index=True)  # Ngày tạo dự báo
    
    icd_code = Column(String(20), nullable=False, index=True)  # mã ICD 3 ký tự hoặc mã nhóm (J00-J06…)
    disease_name = Column(String(200), nullable=False, index=True)
    disease_type = Column(String(100), index=True)  # respiratory
    
    predicted_cases = Column(Integer, nullable=False)
    
    predicted_mild = Column(Integer)
    predicted_moderate = Column(Integer)
    predicted_severe = Column(Integer)
    
    # Khoảng dự báo thực nghiệm (walk-forward)
    confidence_lower = Column(Integer)
    confidence_upper = Column(Integer)
    
    model_used = Column(String(50))  # ensemble | top_down | cung_ky …
    model_accuracy_mae = Column(Numeric(10, 2))
    model_accuracy_rmse = Column(Numeric(10, 2))
    model_accuracy_mape = Column(Numeric(5, 2))
    forecast_period_days = Column(Integer, default=30)
    
    risk_level = Column(String(20))  # 'low' | 'medium' | 'high' | 'very_high'
    baseline_cases = Column(Integer)  # TB cùng kỳ các năm
    weather_factor = Column(Numeric(5, 3))
    trend_factor = Column(Numeric(5, 3))
    explanation = Column(String(1000))
    
    location = Column(String(100), index=True)
    
    actual_cases = Column(Integer)
    deviation_pct = Column(Numeric(7, 2))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(100))
