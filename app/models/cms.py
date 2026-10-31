from sqlalchemy import BigInteger, Column, String, Boolean, DateTime
from sqlalchemy.dialects.mysql import LONGTEXT as LongText
from sqlalchemy.sql import func
from app.db import Base


class Cms(Base):
    __tablename__ = "cms"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=True, comment="page title")
    slug = Column(String(255), unique=True, index=True, nullable=True, comment="page slug")
    description = Column(LongText, nullable=True, comment="page description")
    file = Column(String(255), nullable=True, comment="page file")
    meta_title = Column(String(255), nullable=True, comment="meta title")
    meta_description = Column(String(255), nullable=True, comment="meta description")
    meta_keywords = Column(String(255), nullable=True, comment="meta keywords")
    status = Column(Boolean, nullable=True, default=True, comment="page status")
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Cms(id={self.id}, slug='{self.slug}')>"
