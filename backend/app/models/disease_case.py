"""Disease Case model."""
from sqlalchemy import Column, Integer, String, DateTime, Text, Date
from sqlalchemy.sql import func
from app.database import Base


class DiseaseCase(Base):
    """Disease case records (epidemiological data) - 4 bệnh hô hấp."""
    
    __tablename__ = "disease_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    recorded_date = Column(Date, index=True)  # Ngày ghi nhận (để group theo tháng)
    
    # Thông tin bệnh - sử dụng mã ICD
    icd_code = Column(String(20), nullable=False, index=True)  # J20, J06, J02, J01
    disease_name = Column(String(200), nullable=False, index=True)  # Viêm phế quản cấp...
    # Nhóm ICD (TM_ICD.PHANNHOM): 'J00-J06' / 'J09-J18' / 'J20-J22'.
    # Góc nhìn mặc định của mọi màn hình là NHÓM (đề cương: dự báo cấp nhóm rồi
    # phân bổ về mã) — cột này cho phép lọc/gộp theo nhóm ngay trên bảng nghiệp
    # vụ. Cầu nối trong SyncService tự ALTER thêm cột nếu DB cũ chưa có.
    disease_group = Column(String(20), index=True)
    disease_type = Column(String(100), index=True)  # respiratory (để tương thích code cũ)
    
    # Thông tin ca bệnh
    case_count = Column(Integer, nullable=False, default=1)
    severity = Column(String(20), index=True)  # mild, moderate, severe (nhẹ, trung bình, nặng)
    
    # Thông tin để phân loại mức độ tự động (dùng sau này)
    length_of_stay = Column(Integer)  # Số ngày nằm viện
    sub_icd_count = Column(Integer)  # Số bệnh kèm theo
    
    # Địa điểm
    location = Column(String(100), nullable=False, index=True)  # Tỉnh/Thành
    
    # Metadata
    data_source = Column(String(100))
    note = Column(Text)
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
