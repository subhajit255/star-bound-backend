from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.alias_generators import to_camel
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.config import settings

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    # phone: str = Field(..., min_length=7, max_length=15, pattern=r"^\+?[\d\s\-]+$", description="User's phone number")
    # phone_code: str = Field(..., min_length=1, max_length=5, pattern=r"^\+\d+$", description="User's phone code")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password")
    fcm_token: Optional[str] = Field(None, description="Firebase Cloud Messaging device token")

    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "user@example.com",
                "password": "Password123!",
                "fcm_token": "dK1y...device_fcm_token"
            }
        }
    )

class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=1, description="User's password")
    fcm_token: Optional[str] = Field(None, description="Firebase Cloud Messaging device token")
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "Password123!",
                "fcm_token": "dK1y...device_fcm_token"
            }
        }
    )

class UserForgetPasswordOtp(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class AuthProvider(str, Enum):
    email = "email"
    google = "google"
    apple = "apple"
    facebook = "facebook"

class SocialLoginRequest(BaseModel):
    provider: Optional[AuthProvider] = Field(default=None, description="The social provider being used (optional, inferred from token)")
    token: str = Field(..., description="The Firebase ID token retrieved from the client SDK (e.g. user.getIdToken())")
    fcm_token: Optional[str] = Field(None, description="Firebase Cloud Messaging device token")
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJSUzI1NiIs...",
                "fcm_token": "dK1y...device_fcm_token"
            }
        }
    )

class UserForgetPassword(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    otp: int = Field(..., description="OTP")
    password: str = Field(..., min_length=8, description="User's password")
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, description="User's full name")
    phone: Optional[str] = Field(None, description="User's phone number")
    phone_code: Optional[str] = Field(None, description="User's phone code")
    fcm_token: Optional[str] = Field(None, description="Firebase Cloud Messaging device token")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class UpdateFcmTokenRequest(BaseModel):
    fcm_token: str = Field(..., description="Firebase Cloud Messaging device token")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class RoleResponse(BaseModel):
    id: int
    name: str
    slug: str
    
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

class UserResponse(UserBase):
    id: int
    role: Optional[RoleResponse] = None
    user_name: str = Field(description="Unique username for the user")
    profile_image: Optional[str] = None
    stripe_acc_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    is_active: bool = Field(description="1=Active, 0=Inactive")
    fcm_token: Optional[str] = Field(None, description="Firebase Cloud Messaging device token")
    is_verified: bool = Field(description="1=Verified, 0=Not Verified")
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('profile_image')
    @classmethod
    def prepend_image_path(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if v.startswith('http'):
            return v
        filename = v.split('/')[-1]
        return f"{settings.BASE_URL.rstrip('/')}/uploads/profile/{filename}"

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

class UserResponseWithToken(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class UserPaginatedResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    size: int
    total_pages: int
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
