from typing import List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status, Depends

from app.api.deps import get_db
from app.models.cms import Cms
from app.models.user import User
from app.models.role import Role
from app.schemas.cms import CmsCreate, CmsUpdate, slugify


class CmsService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def check_admin(self, current_user: Optional[User] = None) -> None:
        """Verify if current_user has admin or super-admin role."""
        if not current_user:
            return
        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        admin_role_ids = [r.id for r in admin_roles]
        if admin_role_ids and current_user.role_id not in admin_role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage CMS pages"
            )

    def create_cms(self, payload: Union[CmsCreate, dict], current_user: Optional[User] = None) -> Cms:
        """Create a new CMS page."""
        self.check_admin(current_user)

        data = payload.model_dump(exclude_unset=True) if isinstance(payload, CmsCreate) else dict(payload)

        title = data.get("title")
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title is required to create a CMS page."
            )

        slug = slugify(title)
        data["slug"] = slug

        # Check slug uniqueness
        existing_page = self.db.query(Cms).filter(Cms.slug == slug).first()
        if existing_page:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A CMS page with slug '{slug}' already exists."
            )

        new_cms = Cms(**data)
        self.db.add(new_cms)
        self.db.commit()
        self.db.refresh(new_cms)
        return new_cms

    # CamelCase alias
    createCms = create_cms

    def update_cms(self, cms_id: int, payload: Union[CmsUpdate, dict], current_user: Optional[User] = None) -> Cms:
        """Update an existing CMS page by ID."""
        self.check_admin(current_user)

        cms = self.db.query(Cms).filter(Cms.id == cms_id).first()
        if not cms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CMS page with ID {cms_id} not found."
            )

        data = payload.model_dump(exclude_unset=True) if isinstance(payload, CmsUpdate) else dict(payload)

        # A title change also changes the URL slug.
        data.pop("slug", None)
        new_title = data.get("title")
        if new_title is not None:
            new_slug = slugify(new_title)
            data["slug"] = new_slug
            if new_slug != cms.slug:
                existing_slug = self.db.query(Cms).filter(
                    Cms.slug == new_slug,
                    Cms.id != cms_id
                ).first()
                if existing_slug:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"A CMS page with slug '{new_slug}' already exists."
                    )

        for key, value in data.items():
            if hasattr(cms, key) and value is not None:
                setattr(cms, key, value)

        self.db.commit()
        self.db.refresh(cms)
        return cms

    # CamelCase alias
    updateCms = update_cms

    def get_cms_list(self, status: Optional[bool] = None) -> List[Cms]:
        """List all CMS pages, with optional status filter."""
        query = self.db.query(Cms)
        if status is not None:
            query = query.filter(Cms.status == status)
        return query.order_by(Cms.id.desc()).all()

    # CamelCase alias
    getCmsList = get_cms_list

    def get_cms_by_id(self, cms_id: int) -> Cms:
        """Get a single CMS page by numerical ID."""
        cms = self.db.query(Cms).filter(Cms.id == cms_id).first()
        if not cms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CMS page with ID {cms_id} not found."
            )
        return cms

    getCmsById = get_cms_by_id

    def get_cms_by_slug(self, slug: str) -> Cms:
        """Get a single CMS page by URL slug."""
        cms = self.db.query(Cms).filter(Cms.slug == slug).first()
        if not cms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CMS page with slug '{slug}' not found."
            )
        return cms

    getCmsBySlug = get_cms_by_slug

    def get_cms_by_identifier(self, identifier: str) -> Cms:
        """Get CMS page by either ID (if numeric) or slug."""
        if identifier.isdigit():
            cms = self.db.query(Cms).filter(Cms.id == int(identifier)).first()
            if cms:
                return cms
        return self.get_cms_by_slug(identifier)

    getCmsByIdentifier = get_cms_by_identifier

    def delete_cms(self, cms_id: int, current_user: Optional[User] = None) -> dict:
        """Delete an existing CMS page by ID."""
        self.check_admin(current_user)

        cms = self.db.query(Cms).filter(Cms.id == cms_id).first()
        if not cms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CMS page with ID {cms_id} not found."
            )

        self.db.delete(cms)
        self.db.commit()
        return {
            "message": "CMS page deleted successfully",
            "id": cms_id
        }

    deleteCms = delete_cms
