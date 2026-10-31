from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel
from app.config import settings


class UserQueryBase(BaseModel):
    subject: str = Field(..., max_length=255, description="Subject of the query / issue")
    message: str = Field(..., description="Detailed message explaining the issue or query")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserQueryCreate(UserQueryBase):
    """Schema for creating a query with an optional attachment file path string."""
    attachment: Optional[str] = Field(None, max_length=255, description="Attachment file path or URL")


class UserQueryReplyRequest(BaseModel):
    """Schema for admin replying to a query."""
    reply: str = Field(..., description="Reply message from support / admin")
    status: Optional[int] = Field(default=1, description="Status: 1=Replied, 2=Closed")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserQueryStatusUpdateRequest(BaseModel):
    """Schema for updating query status."""
    status: int = Field(..., description="Status: 0=Pending, 1=Replied, 2=Closed")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserQueryResponse(BaseModel):
    """Schema for user query response."""
    id: int
    user_id: int
    subject: Optional[str] = None
    message: Optional[str] = None
    file: Optional[str] = None
    reply: Optional[str] = None
    replied_by: Optional[int] = None
    replied_at: Optional[datetime] = None
    status: int = Field(default=0, description="0=Pending, 1=Replied, 2=Closed")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    @property
    def file_url(self) -> Optional[str]:
        if not self.file:
            return None
        if self.file.startswith("http://") or self.file.startswith("https://"):
            return self.file
        clean_path = self.file.lstrip("/")
        return f"{settings.BASE_URL.rstrip('/')}/{clean_path}"

    @computed_field
    @property
    def status_text(self) -> str:
        status_map = {0: "Pending", 1: "Replied", 2: "Closed"}
        return status_map.get(self.status, "Pending")

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

