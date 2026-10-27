from sqlalchemy import BigInteger
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), comment="stripe subscription id")
    stripe_subscription_status = Column(String(255), comment="stripe subscription status")
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, comment="1=cancel at period end, 0=not cancel at period end")
    cancel_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Integer, default=1, comment="0=inactive, 1=active, 2: expired, 3: cancelled")
    transaction_id = Column(BigInteger, ForeignKey("transactions.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    # relations
    user = relationship("User", back_populates="user_subscriptions")
    subscription = relationship("Subscription", back_populates="user_subscriptions")
    transaction = relationship("Transaction", back_populates="user_subscription")