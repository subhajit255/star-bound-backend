from sqlalchemy import BigInteger, Column, Float, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class AnalysisRun(Base):
    
    __tablename__ = "analysis_runs"

    id = Column(BigInteger, primary_key=True, index=True)
    upload_id = Column(BigInteger, ForeignKey("uploads.id"), nullable=False, index=True)
    stage_timings_json = Column(Text, comment="JSON-encoded per-stage duration_ms, e.g. detection, matching")
    peak_rss_mb = Column(Float, comment="Peak resident memory for this run, from memray/profiling")
    pipeline_version = Column(String(50))
    model_version = Column(String(50), comment="Version of the rejection classifier model, if used")
    status = Column(String(20), comment="queued | processing | success | failed | no_match")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    upload = relationship("Upload", back_populates="analysis_runs")
