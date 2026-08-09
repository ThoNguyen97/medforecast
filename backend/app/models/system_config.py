"""System Config model."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SystemConfig(Base):
    """System configuration key-value store."""
    
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    description = Column(Text)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    updater = relationship("User")
