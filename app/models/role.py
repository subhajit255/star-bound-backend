from sqlalchemy import BigInteger
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255))
    slug = Column(String(255))
    is_active = Column(Boolean, default=True, comment="1=Active, 0=Inactive")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"

    users = relationship("User", back_populates="role")
    