from sqlalchemy import BigInteger, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT as LongText
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base


class UserQuery(Base):
    __tablename__ = "user_queries"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(255), nullable=True, comment="query subject")
    message = Column(LongText, nullable=True, comment="query message")
    file = Column(String(255), nullable=True, comment="query file")
    reply = Column(LongText, nullable=True, comment="reply message")
    replied_by = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Integer, nullable=True, default=0, comment="query status 0-pending, 1-replied, 2-closed")
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now(), onupdate=func.now())

    # relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="user_queries")
    replied_user = relationship("User", foreign_keys=[replied_by], back_populates="user_queries_replied")

    def __repr__(self):
        return f"<UserQuery(id={self.id}, user_id={self.user_id}, subject='{self.subject}')>"
