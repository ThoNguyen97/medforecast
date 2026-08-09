"""Case Supply Usage model — chi tiết số lượng thuốc đã sử dụng cho 1 ca bệnh."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class CaseSupplyUsage(Base):
    """Lưu số lượng thực tế từng loại thuốc/vật tư đã dùng cho 1 ca bệnh.

    Một ca bệnh có thể dùng nhiều loại thuốc; mỗi (case_id, supply_id) là một dòng.
    """

    __tablename__ = "case_supply_usage"
    __table_args__ = (UniqueConstraint("case_id", "supply_id", name="uq_case_supply"),)

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(
        Integer,
        ForeignKey("disease_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supply_id = Column(
        Integer,
        ForeignKey("medical_supplies.id"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supply = relationship("MedicalSupply", lazy="joined")
