from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from typing import Optional
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate, UserLogin, UserResponseWithToken, UserUpdate, UserForgetPassword, SocialLoginRequest, UserForgetPasswordOtp
from app.services.user_service import UserService

router = APIRouter()

@router.post("/register", response_model=UserResponseWithToken, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, user_service: UserService = Depends()):
    return user_service.register(user_in.model_dump(by_alias=True))

@router.post("/login", response_model=UserResponseWithToken, status_code=status.HTTP_200_OK)
def login(user_in: UserLogin, user_service: UserService = Depends()):
    return user_service.login(user_in.model_dump(by_alias=True))

@router.get("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/update-profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_profile(
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    phone_code: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends()
):
    user_in = UserUpdate(name=name, phone=phone, phone_code=phone_code)
    return user_service.update_profile(
        current_user=current_user, 
        payload=user_in.model_dump(exclude_unset=True),
        profile_image=profile_image
    )

@router.post("/forget-password-otp", status_code=status.HTTP_200_OK)
def forget_password(user_in: UserForgetPasswordOtp, user_service: UserService = Depends()):
    return user_service.forgetPasswordOtp(user_in.model_dump(by_alias=True))

@router.post("/social-login", response_model=UserResponseWithToken, status_code=status.HTTP_200_OK)
def social_login(user_in: SocialLoginRequest, user_service: UserService = Depends()):
    return user_service.socialLogin(user_in.model_dump(by_alias=True))

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(user_in: UserForgetPassword, user_service: UserService = Depends()):
    return user_service.resetPassword(user_in.model_dump(by_alias=True))
