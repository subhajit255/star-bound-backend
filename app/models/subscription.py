from sqlalchemy import BigInteger
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT as LongText, DECIMAL as Decimal
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class Subscription(Base): 

    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255))
    slug = Column(String(255))
    description = Column(LongText)
    features = Column(LongText)
    price = Column(Decimal)
    currency = Column(String(255))
    interval = Column(String(255))
    interval_count = Column(Integer)
    status = Column(Integer, default=1, comment="1=active, 0=inactive")
    is_default = Column(Boolean, default=False, comment="1=default, 0=not default")
    stripe_product_id = Column(String(255), comment="stripe product id")
    stripe_price_id = Column(String(255), comment="stripe price id")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user_subscriptions = relationship("UserSubscription", back_populates="subscription")
