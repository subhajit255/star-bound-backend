import re
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


def slugify(text: str) -> str:
    """Generate a clean, URL-friendly slug from text."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


class CmsBase(BaseModel):
    title: str = Field(..., max_length=255, description="CMS page title")
    slug: Optional[str] = Field(None, max_length=255, description="URL-friendly slug (auto-generated from title if omitted)")
    description: Optional[str] = Field(None, description="Page content or description (HTML/Markdown/Text)")
    file: Optional[str] = Field(None, max_length=255, description="Banner image or attachment file URL/path")
    meta_title: Optional[str] = Field(None, max_length=255, description="SEO meta title")
    meta_description: Optional[str] = Field(None, max_length=255, description="SEO meta description")
    meta_keywords: Optional[str] = Field(None, max_length=255, description="SEO meta keywords (comma-separated)")
    status: Optional[bool] = Field(default=True, description="Page status (True=active, False=inactive)")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CmsCreate(CmsBase):
    """Schema for creating a new CMS page."""

    @model_validator(mode="before")
    @classmethod
    def auto_generate_slug(cls, data: Any) -> Any:
        if isinstance(data, dict):
            slug = data.get("slug")
            title = data.get("title")
            # If slug is not provided or empty string, generate from title
            if (slug is None or (isinstance(slug, str) and not slug.strip())) and title:
                data["slug"] = slugify(title)
            elif isinstance(slug, str) and slug.strip():
                data["slug"] = slugify(slug)
        return data


class CmsUpdate(BaseModel):
    """Schema for updating an existing CMS page (all fields optional)."""
    title: Optional[str] = Field(None, max_length=255, description="CMS page title")
    slug: Optional[str] = Field(None, max_length=255, description="URL-friendly slug")
    description: Optional[str] = Field(None, description="Page content or description (HTML/Markdown/Text)")
    file: Optional[str] = Field(None, max_length=255, description="Banner image or attachment file URL/path")
    meta_title: Optional[str] = Field(None, max_length=255, description="SEO meta title")
    meta_description: Optional[str] = Field(None, max_length=255, description="SEO meta description")
    meta_keywords: Optional[str] = Field(None, max_length=255, description="SEO meta keywords")
    status: Optional[bool] = Field(None, description="Page status (True=active, False=inactive)")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def format_slug(cls, data: Any) -> Any:
        if isinstance(data, dict):
            slug = data.get("slug")
            if isinstance(slug, str) and slug.strip():
                data["slug"] = slugify(slug)
        return data


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
