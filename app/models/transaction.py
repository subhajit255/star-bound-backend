from sqlalchemy import BigInteger
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    payment_type = Column(String(255), comment="1=subscription, 2=one time")
    transaction_ref = Column(String(255), comment="stripe transaction id")
    amount = Column(Float, nullable=False)
    currency = Column(String(255), nullable=False)
    payment_status = Column(String(255), comment="1=success, 2=failed, 3=pending")
    payment_method = Column(String(255), comment="stripe, razorpay")
    transaction_status = Column(String(255), comment="stripe transaction status")
    idempotency_key = Column(String(255), unique=True, index=True)
    payment_details = Column(JSON, comment="payment details in json format")
    description = Column(String(255), comment="description of the transaction")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    # relations
    user = relationship("User", back_populates="transactions")
    user_subscription = relationship("UserSubscription", back_populates="transaction")
    

    