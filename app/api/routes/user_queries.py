from typing import List, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, Query, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user_query import (
    UserQueryResponse,
    UserQueryReplyRequest
)
from app.services.user_query_service import UserQueryService

router = APIRouter()


@router.post(
    "/",
    response_model=UserQueryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new user query / issue with optional attachment"
)
@router.post(
    "/add",
    response_model=UserQueryResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def add_query(
    subject: str = Form(..., description="Subject of the issue / query"),
    message: str = Form(..., description="Detailed message explaining the issue"),
    attachment: Optional[UploadFile] = File(None, description="Optional attachment file (saved to uploads/queries/)"),
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Submit a new user query / issue report.
    - Requires authenticated user.
    - Uploaded file is stored inside `uploads/queries/`.
    """
    return service.create_query(
        current_user=current_user,
        subject=subject,
        message=message,
        attachment=attachment
    )


@router.get(
    "/me",
    response_model=List[UserQueryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get queries submitted by the authenticated user"
)
def get_my_queries(
    status_code: Optional[int] = Query(None, alias="status", description="Filter by status (0=pending, 1=replied, 2=closed)"),
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Retrieve all queries submitted by the logged-in user.
    """
    return service.get_my_queries(current_user=current_user, status_filter=status_code)


@router.get(
    "/",
    response_model=List[UserQueryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all user queries (Admin only)"
)
def get_all_queries(
    status_code: Optional[int] = Query(None, alias="status", description="Filter by status (0=pending, 1=replied, 2=closed)"),
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Admin: Retrieve all queries in the system.
    """
    return service.get_all_queries(current_user=current_user, status_filter=status_code)


@router.get(
    "/{query_id}",
    response_model=UserQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get query detail by ID"
)
def get_query(
    query_id: int,
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Get a single query by ID. Accessible by the author or an admin.
    """
    return service.get_query_by_id(query_id=query_id, current_user=current_user)


@router.post(
    "/{query_id}/reply",
    response_model=UserQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Reply to user query and notify user (Admin only)"
)
@router.put(
    "/{query_id}/reply",
    response_model=UserQueryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
def reply_query(
    query_id: int,
    payload: UserQueryReplyRequest,
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Admin: Reply to a user query.
    - Sets query status to replied (or custom status).
    - Automatically sends in-app notification & push notification to the user.
    """
    return service.reply_to_query(
        query_id=query_id,
        reply_text=payload.reply,
        current_user=current_user,
        new_status=payload.status if payload.status is not None else 1
    )


@router.delete(
    "/{query_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a query by ID"
)
def delete_query(
    query_id: int,
    current_user: User = Depends(get_current_user),
    service: UserQueryService = Depends()
):
    """
    Delete a query by ID (author or admin). Unlinks attachment file from disk if present.
    """
    return service.delete_query(query_id=query_id, current_user=current_user)

