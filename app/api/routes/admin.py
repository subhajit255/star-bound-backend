from fastapi import APIRouter, Depends, Query
from typing import List
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserPaginatedResponse, UserStatusChangeResponse
from app.services.user_service import UserService

router = APIRouter()

@router.get("/users", response_model=UserPaginatedResponse)
def get_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends()
):
    return user_service.getUsers(current_user, page, size)

@router.patch("/user/change-status/{user_id}", response_model=UserStatusChangeResponse)
def change_user_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends()
):
    return user_service.changeUserStatus(currentUser=current_user, user_id=user_id)
