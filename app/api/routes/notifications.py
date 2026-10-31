from fastapi import APIRouter, Depends, Query, Path, Request, status
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationPaginatedResponse,
    MarkAllReadResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get(
    "/",
    response_model=NotificationPaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notifications for authenticated user",
    description="Retrieve paginated notifications for the current authenticated user, ordered by newest first. Includes image URL resolved from `redirection_foreign_id`."
)
def get_notifications(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(),
):
    base_url = str(request.base_url).rstrip("/") if request else None
    return notification_service.getUserNotifications(
        currentUser=current_user,
        page=page,
        size=size,
        unread_only=unread_only,
        base_url=base_url
    )


@router.get(
    "/me",
    response_model=NotificationPaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my notifications (alias)",
    description="Alias for `GET /api/v1/notifications`."
)
def get_my_notifications(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(),
):
    base_url = str(request.base_url).rstrip("/") if request else None
    return notification_service.getUserNotifications(
        currentUser=current_user,
        page=page,
        size=size,
        unread_only=unread_only,
        base_url=base_url
    )


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Mark the specified notification as read (`is_read = 1`) and return the updated notification with its resolved image."
)
def mark_notification_as_read(
    request: Request,
    notification_id: int = Path(..., ge=1, description="The ID of the notification to mark as read"),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(),
):
    base_url = str(request.base_url).rstrip("/") if request else None
    return notification_service.markAsRead(
        currentUser=current_user,
        notification_id=notification_id,
        base_url=base_url
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read (PATCH alias)",
    description="PATCH alias for `PUT /api/v1/notifications/{notification_id}/read`."
)
def patch_notification_as_read(
    request: Request,
    notification_id: int = Path(..., ge=1, description="The ID of the notification to mark as read"),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(),
):
    base_url = str(request.base_url).rstrip("/") if request else None
    return notification_service.markAsRead(
        currentUser=current_user,
        notification_id=notification_id,
        base_url=base_url
    )


@router.put(
    "/read-all",
    response_model=MarkAllReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark all unread notifications of the current authenticated user as read (`is_read = 1`)."
)
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(),
):
    return notification_service.markAllAsRead(currentUser=current_user)

