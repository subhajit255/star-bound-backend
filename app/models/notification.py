from sqlalchemy import Column, BigInteger, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), index=True)
    title = Column(String(255))
    description = Column(Text)
    type = Column(String(255))
    is_read = Column(Integer, default=0, comment="1=Read, 0=Unread")
    redirection_foreign_id = Column(BigInteger)
    redirection_foreign_table = Column(String(255))
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
    
    # Relationships
    user = relationship("User", back_populates="notifications")