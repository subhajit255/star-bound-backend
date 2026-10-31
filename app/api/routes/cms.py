from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.cms import CmsCreate, CmsUpdate, CmsResponse
from app.services.cms_service import CmsService

router = APIRouter()


@router.post("/", response_model=CmsResponse, status_code=status.HTTP_201_CREATED, summary="Create a new CMS page")
def create_cms(
    cms_in: CmsCreate,
    current_user: User = Depends(get_current_user),
    cms_service: CmsService = Depends()
):
    """
    Create a new CMS page (Admin only).
    - If `slug` is omitted or empty, it is automatically generated from `title`.
    """
    return cms_service.create_cms(payload=cms_in, current_user=current_user)


@router.put("/{cms_id}", response_model=CmsResponse, status_code=status.HTTP_200_OK, summary="Update an existing CMS page by ID")
def update_cms(
    cms_id: int,
    cms_in: CmsUpdate,
    current_user: User = Depends(get_current_user),
    cms_service: CmsService = Depends()
):
    """
    Update an existing CMS page by ID (Admin only).
    - Accepts partial updates.
    """
    return cms_service.update_cms(cms_id=cms_id, payload=cms_in, current_user=current_user)


@router.get("/", response_model=List[CmsResponse], status_code=status.HTTP_200_OK, summary="List all CMS pages")
def get_cms_list(
    status: Optional[bool] = Query(None, description="Filter by status (true for active only, false for inactive)"),
    cms_service: CmsService = Depends()
):
    """
    Retrieve all CMS pages (public).
    """
    return cms_service.get_cms_list(status=status)


@router.get("/{identifier}", response_model=CmsResponse, status_code=status.HTTP_200_OK, summary="Get CMS page by ID or slug")
def get_cms(
    identifier: str,
    cms_service: CmsService = Depends()
):
    """
    Get a single CMS page by either its numeric ID or URL slug (e.g. 'terms-conditions').
    """
    return cms_service.get_cms_by_identifier(identifier=identifier)


@router.delete("/{cms_id}", status_code=status.HTTP_200_OK, summary="Delete an existing CMS page by ID")
def delete_cms(
    cms_id: int,
    current_user: User = Depends(get_current_user),
    cms_service: CmsService = Depends()
):
    """
    Delete a CMS page by ID (Admin only).
    """
    return cms_service.delete_cms(cms_id=cms_id, current_user=current_user)

