"""Model ca bệnh thực tế."""
from sqlalchemy import Column, Integer, String, DateTime, Text, Date
from sqlalchemy.sql import func
from app.database import Base


class DiseaseCase(Base):
    """Số ca bệnh hô hấp thực tế theo mã ICD, tháng và địa bàn."""
    
    __tablename__ = "disease_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    recorded_date = Column(Date, index=True)  # gộp theo tháng
    
    icd_code = Column(String(20), nullable=False, index=True)  # mã ICD 3 ký tự
    disease_name = Column(String(200), nullable=False, index=True)
    # Nhóm ICD (TM_ICD.PHANNHOM): 'J00-J06' | 'J09-J18' | 'J20-J22'; SyncService tự ALTER thêm cột nếu thiếu
    disease_group = Column(String(20), index=True)
    disease_type = Column(String(100), index=True)  # respiratory
    
    case_count = Column(Integer, nullable=False, default=1)
    severity = Column(String(20), index=True)  # mild | moderate | severe
    
    length_of_stay = Column(Integer)  # Số ngày nằm viện
    sub_icd_count = Column(Integer)  # Số bệnh kèm theo
    
    location = Column(String(100), nullable=False, index=True)  # Tỉnh/Thành
    
    data_source = Column(String(100))
    note = Column(Text)
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
