from sqlalchemy import BigInteger, Column, Float, Integer, String, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.db import Base


class Match(Base):

    __tablename__ = "matches"

    id = Column(BigInteger, primary_key=True, index=True)
    upload_id = Column(BigInteger, ForeignKey("uploads.id"), nullable=False, index=True)
    rank = Column(Integer, nullable=False, comment="1 = best match")
    ra = Column(Float, comment="Right ascension of the matched region, degrees")
    dec = Column(Float, comment="Declination of the matched region, degrees")
    roll = Column(Float, comment="Rotation of the fitted transform, degrees")
    scale = Column(Float, comment="Scale factor of the fitted similarity transform")
    parity = Column(Integer, comment="+1 or -1 -- which mirror orientation matched")
    n_matched = Column(Integer, comment="How many detected points landed on a catalogue star")
    log_odds = Column(Float, comment="Raw Bayesian log-odds score, pre-calibration")
    confidence_pct = Column(Float, comment="Calibrated confidence, from the null-distribution percentile")
    star_ids = Column(JSON, comment="Catalogue star_idx values that were matched")
    constellation = Column(String(100), comment="IAU constellation the matched region falls inside")
    asterism_name = Column(String(255), comment="User-chosen name for their discovered constellation")
    asterism_meaning = Column(String(500), comment="User-chosen meaning for their constellation")
    story = Column(Text, comment="Generated mythology story for the constellation")

    # Relationships
    upload = relationship("Upload", back_populates="matches")
