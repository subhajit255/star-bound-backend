import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def slugify(text: str) -> str:
    """Generate a clean, URL-friendly slug from text."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


class CmsBase(BaseModel):
    title: str = Field(..., max_length=255, description="CMS page title")
    description: Optional[str] = Field(None, description="Page content or description (HTML/Markdown/Text)")
    file: Optional[str] = Field(None, max_length=255, description="Banner image or attachment file URL/path")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CmsCreate(CmsBase):
    """Schema for creating a new CMS page."""

    pass


class CmsUpdate(BaseModel):
    """Schema for updating an existing CMS page (all fields optional)."""
    title: Optional[str] = Field(None, max_length=255, description="CMS page title")
    description: Optional[str] = Field(None, description="Page content or description (HTML/Markdown/Text)")
    file: Optional[str] = Field(None, max_length=255, description="Banner image or attachment file URL/path")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CmsResponse(BaseModel):
    """Schema for returning CMS page data to clients."""
    id: int
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    file: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    status: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
