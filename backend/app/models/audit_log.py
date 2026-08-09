"""Audit Log model."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class AuditLog(Base):
    """Audit logs for tracking data modifications."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    action = Column(String(100), nullable=False, index=True)
    table_name = Column(String(100), index=True)
    record_id = Column(Integer)
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User")
