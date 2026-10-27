from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import datetime
import re


def slugify(text: str) -> str:
    """Generate a URL-friendly slug from text."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


class SubscriptionCreate(BaseModel):
    id: Optional[int] = Field(None, description="Optional ID to update an existing subscription. If not provided, a new subscription is created.")
    name: Optional[str] = Field(None, description="Plan name (e.g. Pro Plan)")
    slug: Optional[str] = Field(None, description="Unique slug (e.g. pro-monthly). Auto-generated from name if not provided.")
    price: Optional[float] = Field(None, ge=0, description="Price amount")
    currency: Optional[str] = Field(default="usd", description="3-letter currency code (e.g. usd, eur, inr, jpy)")
    interval: Optional[str] = Field(default="month", description="Billing frequency: day, week, month, or year")
    interval_count: Optional[int] = Field(default=1, ge=1, description="Interval multiplier (e.g. 1 month, 3 months)")
    description: Optional[str] = Field(None, description="Plan description")
    tagline: Optional[str] = Field(None, description="Short marketing tagline")
    features: Optional[str] = Field(None, description="Comma-separated or JSON list of features")
    status: Optional[int] = Field(default=1, description="1=active, 0=inactive")
    is_default: Optional[bool] = Field(default=False, description="Whether this is the default plan")

    @model_validator(mode="before")
    @classmethod
    def auto_generate_slug(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If slug is not provided or empty/whitespace, auto-generate from name
            slug = data.get("slug")
            name = data.get("name")
            if (slug is None or (isinstance(slug, str) and not slug.strip())) and name:
                data["slug"] = slugify(name)
        return data


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    features: Optional[str] = None
    price: float
    currency: Optional[str] = "usd"
    interval: Optional[str] = "month"
    interval_count: Optional[int] = 1
    status: int = 1
    is_default: bool = False
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
