import os
import time
import uuid
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException, status, UploadFile, Depends

from app.api.deps import get_db
from app.models.user_query import UserQuery
from app.models.user import User
from app.models.role import Role
from app.traits.push_notification_trait import PushNotificationTrait

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
QUERIES_UPLOAD_DIR = Path("uploads/queries")


class UserQueryService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
        QUERIES_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def check_admin(self, current_user: Optional[User]) -> None:
        """Verify if user has admin or super-admin role."""
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        admin_role_ids = [r.id for r in admin_roles]
        if admin_role_ids and current_user.role_id not in admin_role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to perform this operation"
            )

    def save_attachment(self, attachment: UploadFile) -> str:
        """Saves an attachment into uploads/queries/ and returns relative path."""
        content = attachment.file.read(MAX_ATTACHMENT_SIZE + 1)
        if len(content) > MAX_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Attachment must be 10 MB or smaller."
            )
        if not content:
            return None

        # Determine file extension
        orig_suffix = Path(attachment.filename).suffix if attachment.filename else ".jpg"
        unique_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{orig_suffix}"
        target_path = QUERIES_UPLOAD_DIR / unique_name

        target_path.write_bytes(content)
        return f"uploads/queries/{unique_name}"

    def create_query(
        self,
        current_user: User,
        subject: str,
        message: str,
        attachment: Optional[UploadFile] = None
    ) -> UserQuery:
        """Create and persist a new user query with optional attachment."""
        if not subject or not subject.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject is required."
            )
        if not message or not message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is required."
            )

        file_path = None
        if attachment and attachment.filename:
            file_path = self.save_attachment(attachment)

        query = UserQuery(
            user_id=current_user.id,
            subject=subject.strip(),
            message=message.strip(),
            file=file_path,
            status=0
        )
        self.db.add(query)
        self.db.commit()
        self.db.refresh(query)
        return query

    # CamelCase alias
    createQuery = create_query

    def get_my_queries(
        self,
        current_user: User,
        status_filter: Optional[int] = None
    ) -> List[UserQuery]:
        """Fetch all queries created by the current user."""
        query = self.db.query(UserQuery).filter(UserQuery.user_id == current_user.id)
        if status_filter is not None:
            query = query.filter(UserQuery.status == status_filter)
        return query.order_by(UserQuery.id.desc()).all()

    getMyQueries = get_my_queries

    def get_query_by_id(
        self,
        query_id: int,
        current_user: User
    ) -> UserQuery:
        """Fetch a single query by ID (author or admin)."""
        query = self.db.query(UserQuery).filter(UserQuery.id == query_id).first()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query with ID {query_id} not found."
            )

        # Allow if user is the author or admin
        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        admin_ids = [r.id for r in admin_roles]

        if query.user_id != current_user.id and current_user.role_id not in admin_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this query."
            )
        return query

    getQueryById = get_query_by_id

    def get_all_queries(
        self,
        current_user: User,
        status_filter: Optional[int] = None
    ) -> List[UserQuery]:
        """Admin endpoint: Fetch all queries in the system."""
        self.check_admin(current_user)
        query = self.db.query(UserQuery)
        if status_filter is not None:
            query = query.filter(UserQuery.status == status_filter)
        return query.order_by(UserQuery.id.desc()).all()

    getAllQueries = get_all_queries

    def reply_to_query(
        self,
        query_id: int,
        reply_text: str,
        current_user: User,
        new_status: int = 1
    ) -> UserQuery:
        """Admin endpoint: Reply to user query and notify user via PushNotificationTrait."""
        self.check_admin(current_user)

        query = self.db.query(UserQuery).filter(UserQuery.id == query_id).first()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query with ID {query_id} not found."
            )

        if not reply_text or not reply_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reply message cannot be empty."
            )

        query.reply = reply_text.strip()
        query.replied_by = current_user.id
        query.replied_at = func.now()
        query.status = new_status

        self.db.commit()
        self.db.refresh(query)

        # Send in-app notification & push notification to the user
        try:
            PushNotificationTrait.notify_user(
                db=self.db,
                user_id=query.user_id,
                title="Query Update",
                body=f"Your query '{query.subject}' has received a reply: {query.reply[:80]}",
                notification_type="user_query",
                redirection_id=query.id,
                redirection_table="user_queries"
            )
        except Exception:
            pass

        return query

    replyToQuery = reply_to_query

    def delete_query(
        self,
        query_id: int,
        current_user: User
    ) -> dict:
        """Delete a query (author or admin)."""
        query = self.db.query(UserQuery).filter(UserQuery.id == query_id).first()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query with ID {query_id} not found."
            )

        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        admin_ids = [r.id for r in admin_roles]

        if query.user_id != current_user.id and current_user.role_id not in admin_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this query."
            )

        # Unlink file if it exists
        if query.file:
            file_on_disk = Path(query.file)
            if file_on_disk.exists():
                try:
                    file_on_disk.unlink()
                except OSError:
                    pass

        self.db.delete(query)
        self.db.commit()
        return {"message": "Query deleted successfully", "id": query_id}

    deleteQuery = delete_query

