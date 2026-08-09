"""System Log model."""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SystemLog(Base):
    """System logs for errors, warnings, and info messages."""
    
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(String(20), nullable=False, index=True)  # ERROR, WARNING, INFO
    module_name = Column(String(100), index=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
