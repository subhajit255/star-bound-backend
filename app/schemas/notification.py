from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional, List
from datetime import datetime


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    type: Optional[str] = None
    is_read: int = Field(0, description="1=Read, 0=Unread")
    redirection_foreign_id: Optional[int] = None
    redirection_foreign_table: Optional[str] = None
    image: Optional[str] = Field(None, description="Image URL resolved from redirection_foreign_id and redirection_foreign_table")
    image_url: Optional[str] = Field(None, description="Alias for image URL")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)


class NotificationPaginatedResponse(BaseModel):
    items: List[NotificationResponse] = Field(..., description="List of notifications")
    total: int = Field(..., description="Total notifications count")
    unread_count: int = Field(0, description="Count of unread notifications")
    page: int = Field(1, description="Current page number")
    size: int = Field(20, description="Items per page")
    total_pages: int = Field(1, description="Total number of pages")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MarkNotificationReadResponse(BaseModel):
    message: str = "Notification marked as read"
    notification: NotificationResponse

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
