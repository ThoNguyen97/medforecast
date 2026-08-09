"""Schema DB trung gian 3 tầng: STAGING → CLEAN (dim/fact) → MART.

Tất cả bảng prefix rõ tầng để dễ đọc:
  stg_*   : dữ liệu thô vừa nạp (landing), gần như nguyên trạng nguồn
  dim_*   : bảng chiều đã chuẩn hóa (ICD phân cấp, vật tư, địa bàn)
  fact_*  : bảng sự kiện đã làm sạch (ca bệnh, tiêu thụ vật tư, tồn kho)
  mart_*  : bảng tổng hợp sẵn dùng cho mô hình & báo cáo
  sync_state : mốc đồng bộ (watermark) + nhật ký mỗi lần chạy
"""
from __future__ import annotations

from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, Date, DateTime, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.sql import func

from .db import Base

# PK tự tăng chạy được cả SQLite lẫn Postgres. Dùng Integer cho tương thích
# (SQLite chỉ auto-increment với INTEGER PRIMARY KEY; Postgres -> SERIAL).
PK = Integer


# ───────────────────────── STAGING ─────────────────────────
class StgCaseSupply(Base):
    """Landing: mỗi dòng = tháng × bệnh × địa bàn × vật tư (denormalized từ nguồn)."""
    __tablename__ = "stg_case_supply"
    id = Column(PK, primary_key=True, autoincrement=True)
    month = Column(String(7), index=True)          # 'MM/YYYY' nguyên trạng
    disease_code = Column(String(20))
    disease_name = Column(String(255))
    region = Column(String(120))
    cases = Column(Integer)
    supply_code = Column(String(60))
    supply_name = Column(String(400))
    supply_quantity = Column(Float)
    supply_unit = Column(String(40))
    supply_category = Column(String(255))
    note = Column(String(255))
    row_hash = Column(String(64), index=True)       # khử trùng
    source = Column(String(40))
    loaded_at = Column(DateTime(timezone=True), server_default=func.now())


class StgInventory(Base):
    """Landing: snapshot tồn kho."""
    __tablename__ = "stg_inventory"
    id = Column(PK, primary_key=True, autoincrement=True)
    supply_code = Column(String(60), index=True)
    drug_code = Column(String(60))
    ten_hoat_chat = Column(String(255))
    unit = Column(String(40))
    group_name = Column(String(255))
    category = Column(String(80))
    stock_quantity = Column(Integer)
    description = Column(Text)
    source = Column(String(40))
    loaded_at = Column(DateTime(timezone=True), server_default=func.now())


# ───────────────────────── DIMENSIONS ─────────────────────────
class DimIcd(Base):
    """Danh mục ICD phân cấp Mã → Nhóm → Chương (từ TM_ICD)."""
    __tablename__ = "dim_icd"
    icd_code = Column(String(20), primary_key=True)
    icd_name = Column(String(400))
    block_code = Column(String(20), index=True)     # PHANNHOM, vd 'J00-J06'
    block_name = Column(String(255))
    chapter_code = Column(String(20), index=True)   # vd 'J00-J99'
    chapter_name = Column(String(255))
    is_target = Column(Boolean, default=False, index=True)  # thuộc 3 nhóm dự báo


class DimSupply(Base):
    """Danh mục vật tư/thuốc."""
    __tablename__ = "dim_supply"
    supply_code = Column(String(60), primary_key=True)
    drug_code = Column(String(60))
    name = Column(String(400))
    unit = Column(String(40))
    group_name = Column(String(255))
    category = Column(String(80))


class DimRegion(Base):
    __tablename__ = "dim_region"
    region = Column(String(120), primary_key=True)


# ───────────────────────── FACTS ─────────────────────────
class FactDiseaseCase(Base):
    """Số ca theo tháng × mã ICD × địa bàn (đã khử trùng số ca lặp theo vật tư)."""
    __tablename__ = "fact_disease_case"
    id = Column(PK, primary_key=True, autoincrement=True)
    period = Column(String(7), index=True)          # 'YYYY-MM'
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    recorded_date = Column(Date)                    # ngày 01 của tháng
    icd_code = Column(String(20), index=True)
    block_code = Column(String(20), index=True)
    region = Column(String(120), index=True)
    cases = Column(Integer)
    is_covid = Column(Boolean, default=False)       # 2020–2021
    is_complete = Column(Boolean, default=True)     # tháng đã trọn vẹn
    __table_args__ = (
        UniqueConstraint("period", "icd_code", "region", name="uq_fact_case"),
    )


class FactSupplyUsage(Base):
    """Tiêu thụ vật tư theo tháng × mã ICD × địa bàn × vật tư."""
    __tablename__ = "fact_supply_usage"
    id = Column(PK, primary_key=True, autoincrement=True)
    period = Column(String(7), index=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    icd_code = Column(String(20), index=True)
    block_code = Column(String(20), index=True)
    region = Column(String(120), index=True)
    supply_code = Column(String(60), index=True)
    quantity = Column(Float)
    __table_args__ = (
        UniqueConstraint("period", "icd_code", "region", "supply_code", name="uq_fact_usage"),
    )


class FactInventorySnapshot(Base):
    __tablename__ = "fact_inventory_snapshot"
    id = Column(PK, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, index=True)
    supply_code = Column(String(60), index=True)
    stock_quantity = Column(Integer)
    __table_args__ = (
        UniqueConstraint("snapshot_date", "supply_code", name="uq_inv_snapshot"),
    )


# ───────────────────────── MARTS ─────────────────────────
class MartMonthlyCasesByBlock(Base):
    """Tổng số ca theo tháng × NHÓM ICD — đầu vào huấn luyện (dự báo phân cấp B1)."""
    __tablename__ = "mart_monthly_cases_by_block"
    id = Column(PK, primary_key=True, autoincrement=True)
    period = Column(String(7), index=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    block_code = Column(String(20), index=True)
    block_name = Column(String(255))
    region = Column(String(120), index=True)        # 'TOAN_QUOC' = gộp toàn quốc
    cases = Column(Integer)
    is_covid = Column(Boolean, default=False)
    is_complete = Column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("period", "block_code", "region", name="uq_mart_block"),
    )


class MartIcdShareInBlock(Base):
    """Tỷ trọng từng mã trong nhóm — dùng để chia ngược (dự báo phân cấp B2/B3)."""
    __tablename__ = "mart_icd_share_in_block"
    id = Column(PK, primary_key=True, autoincrement=True)
    block_code = Column(String(20), index=True)
    icd_code = Column(String(20), index=True)
    region = Column(String(120), index=True)
    share = Column(Float)                            # 0..1
    n_cases = Column(Integer)
    __table_args__ = (
        UniqueConstraint("block_code", "icd_code", "region", name="uq_mart_share"),
    )


class MartInventory(Base):
    """Snapshot tồn kho mới nhất — phục vụ báo cáo tồn kho."""
    __tablename__ = "mart_inventory"
    supply_code = Column(String(60), primary_key=True)
    name = Column(String(400))
    drug_code = Column(String(60))
    unit = Column(String(40))
    group_name = Column(String(255))
    category = Column(String(80))
    stock_quantity = Column(Integer)
    snapshot_date = Column(Date)


class MartMonthlyWeather(Base):
    """Thời tiết trung bình theo tháng × địa bàn (từ environmental_data / Open-Meteo).

    Biến ngoại sinh cho mô hình dự báo (dùng có độ trễ). region='TOAN_QUOC' lấy
    TP.HCM làm đại diện môi trường cho chuỗi ca gộp toàn quốc.
    """
    __tablename__ = "mart_monthly_weather"
    id = Column(PK, primary_key=True, autoincrement=True)
    period = Column(String(7), index=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    region = Column(String(120), index=True)
    temp = Column(Float)
    humidity = Column(Float)
    rainfall = Column(Float)
    __table_args__ = (
        UniqueConstraint("period", "region", name="uq_mart_weather"),
    )


# ───────────────────────── SYNC STATE ─────────────────────────
class SyncState(Base):
    """Watermark + nhật ký mỗi lần đồng bộ (để nạp tăng dần & truy vết)."""
    __tablename__ = "sync_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(40), index=True)
    last_period = Column(String(7))                 # tháng lớn nhất đã nạp 'YYYY-MM'
    rows_ingested = Column(Integer, default=0)
    rows_rejected = Column(Integer, default=0)
    status = Column(String(20))                     # ok / failed
    message = Column(Text)
    run_at = Column(DateTime(timezone=True), server_default=func.now())
# end of models
