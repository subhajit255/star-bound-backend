from sqlalchemy import BigInteger, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class PointSet(Base):

    __tablename__ = "point_sets"

    id = Column(BigInteger, primary_key=True, index=True)
    upload_id = Column(BigInteger, ForeignKey("uploads.id"), nullable=False, index=True)
    n_points = Column(Integer, nullable=False)
    bbox = Column(String(100), comment="Bounding box of the point set, e.g. 'x_min,y_min,x_max,y_max'")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    upload = relationship("Upload", back_populates="point_sets")
