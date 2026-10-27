from sqlalchemy import BigInteger
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    role_id = Column(BigInteger, ForeignKey("roles.id"), nullable=True, comment="1=super_admin, 2=admin, 3=user")
    name = Column(String(255))
    user_name = Column(String(255), comment="Unique username for the user")
    email = Column(String(255), unique=True, index=True)
    phone_code = Column(String(255))
    phone = Column(String(255))
    verification_code = Column(Integer, comment="Verification code for the user")
    password = Column(String(255), nullable=True)
    auth_provider = Column(String(50), default="email")
    provider_id = Column(String(255), nullable=True)
    last_login_ip = Column(String(255))
    profile_image = Column(String(255))
    stripe_acc_id = Column(String(255), nullable=True, comment="Stripe Connected Account ID")
    stripe_customer_id = Column(String(255), nullable=True, comment="Stripe Customer ID")
    is_active = Column(Boolean, default=True, comment="1=Active, 0=Inactive")
    fcm_token = Column(String(512), nullable=True, comment="Firebase Cloud Messaging device token")
    is_verified = Column(Boolean, default=False, comment="1=Verified, 0=Not Verified")
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False, comment="1=Deleted, 0=Not Deleted")
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    notifications = relationship("Notification", back_populates="user")
    uploads = relationship("Upload", back_populates="user")
    role = relationship("Role", back_populates="users")
    user_subscriptions = relationship("UserSubscription", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    
    
