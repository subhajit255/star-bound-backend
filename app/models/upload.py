from sqlalchemy import BigInteger, Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class Upload(Base):
    __tablename__ = "uploads"


    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    file_name = Column(String(255))
    file_path = Column(String(1024))
    file_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)


    user = relationship("User", back_populates="uploads")
    detections = relationship("Detection", back_populates="upload")
    point_sets = relationship("PointSet", back_populates="upload")
    matches = relationship("Match", back_populates="upload")
    analysis_runs = relationship("AnalysisRun", back_populates="upload")

