from sqlalchemy import BigInteger, Column, Float, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base


class Detection(Base):
    
    __tablename__ = "detections"

    id = Column(BigInteger, primary_key=True, index=True)
    upload_id = Column(BigInteger, ForeignKey("uploads.id"), nullable=False, index=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    radius = Column(Float, comment="Detected blob radius in pixels")
    score = Column(Float, comment="Detector confidence for this point")
    kept = Column(BigInteger, default=1, comment="1=kept, 0=removed by user")
    source = Column(String(20), default="auto", comment="'auto' or 'user_added'")

    # Relationships
    upload = relationship("Upload", back_populates="detections")
