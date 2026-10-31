import math
import os
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status, Depends

from app.api.deps import get_db
from app.config import settings
from app.models.user import User
from app.models.notification import Notification
from app.models.analysis_run import AnalysisRun
from app.models.upload import Upload
from app.models.match import Match
from app.schemas.notification import (
    NotificationResponse,
    NotificationPaginatedResponse,
    MarkNotificationReadResponse,
    MarkAllReadResponse,
)


class NotificationService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def getUserNotifications(
        self,
        currentUser: User,
        page: int = 1,
        size: int = 20,
        unread_only: bool = False,
        base_url: Optional[str] = None
    ) -> NotificationPaginatedResponse:
        """
        Fetch paginated notifications for the authenticated user,
        ordered from newest to oldest, and resolve the associated image
        as per `redirection_foreign_id` and `redirection_foreign_table`.
        """
        base_url = (base_url or settings.BASE_URL).rstrip("/")

        query = self.db.query(Notification).filter(Notification.user_id == currentUser.id)
        if unread_only:
            query = query.filter(Notification.is_read == 0)

        total = query.count()
        unread_count = (
            self.db.query(Notification)
            .filter(Notification.user_id == currentUser.id, Notification.is_read == 0)
            .count()
        )

        offset = max(0, (page - 1) * size)
        notifications = (
            query.order_by(Notification.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        total_pages = math.ceil(total / size) if size > 0 and total > 0 else (1 if total == 0 else 0)

        # Batch resolve images for all notifications on the current page
        images_map = self._resolve_images_batch(notifications, base_url)

        items: List[NotificationResponse] = []
        for notif in notifications:
            img_url, star_pattern_url = images_map.get(notif.id, (None, None))
            item = NotificationResponse(
                id=notif.id,
                user_id=notif.user_id,
                title=notif.title,
                description=notif.description,
                type=notif.type,
                is_read=notif.is_read,
                redirection_foreign_id=notif.redirection_foreign_id,
                redirection_foreign_table=notif.redirection_foreign_table,
                image=img_url,
                image_url=img_url,
                star_pattern_url=star_pattern_url,
                created_at=notif.created_at,
                updated_at=notif.updated_at,
            )
            items.append(item)

        return NotificationPaginatedResponse(
            items=items,
            total=total,
            unread_count=unread_count,
            page=page,
            size=size,
            total_pages=total_pages
        )

    def markAsRead(
        self,
        currentUser: User,
        notification_id: int,
        base_url: Optional[str] = None
    ) -> NotificationResponse:
        """
        Mark a single notification as read (is_read = 1) for the authenticated user
        and return the updated notification with its resolved image.
        """
        base_url = (base_url or settings.BASE_URL).rstrip("/")

        notif = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found."
            )

        if notif.user_id != currentUser.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this notification."
            )

        if notif.is_read != 1:
            notif.is_read = 1
            self.db.commit()
            self.db.refresh(notif)

        img_url, star_pattern_url = self.resolve_notification_image(notif, base_url)

        return NotificationResponse(
            id=notif.id,
            user_id=notif.user_id,
            title=notif.title,
            description=notif.description,
            type=notif.type,
            is_read=notif.is_read,
            redirection_foreign_id=notif.redirection_foreign_id,
            redirection_foreign_table=notif.redirection_foreign_table,
            image=img_url,
            image_url=img_url,
            star_pattern_url=star_pattern_url,
            created_at=notif.created_at,
            updated_at=notif.updated_at,
        )

    def markAllAsRead(self, currentUser: User) -> MarkAllReadResponse:
        """
        Mark all unread notifications for the authenticated user as read.
        """
        unread_notifications = (
            self.db.query(Notification)
            .filter(Notification.user_id == currentUser.id, Notification.is_read == 0)
            .all()
        )

        marked_count = len(unread_notifications)
        for n in unread_notifications:
            n.is_read = 1

        if marked_count > 0:
            self.db.commit()

        return MarkAllReadResponse(
            message="All notifications marked as read.",
            marked_count=marked_count
        )

    # Aliases for snake_case callers
    get_user_notifications = getUserNotifications
    mark_as_read = markAsRead
    mark_all_as_read = markAllAsRead

    def resolve_notification_image(
        self,
        notif: Notification,
        base_url: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves image URL and optional star pattern URL for a single notification
        using `redirection_foreign_id` and `redirection_foreign_table`.
        """
        base_url = (base_url or settings.BASE_URL).rstrip("/")
        ref_id = notif.redirection_foreign_id
        ref_table = (notif.redirection_foreign_table or "").strip().lower()

        if not ref_id:
            return None, None

        if ref_table in ("analysis_runs", "analysis_run", "analyses", "analysis"):
            run = (
                self.db.query(AnalysisRun)
                .filter(AnalysisRun.id == ref_id)
                .options(joinedload(AnalysisRun.upload))
                .first()
            )
            if run and run.upload and run.upload.file_path:
                return (
                    self._build_image_url(run.upload.file_path, base_url),
                    self._build_star_pattern_url(run.upload.file_path, base_url)
                )

        elif ref_table in ("uploads", "upload"):
            upload = self.db.query(Upload).filter(Upload.id == ref_id).first()
            if upload and upload.file_path:
                return (
                    self._build_image_url(upload.file_path, base_url),
                    self._build_star_pattern_url(upload.file_path, base_url)
                )

        elif ref_table in ("matches", "match"):
            match = (
                self.db.query(Match)
                .filter(Match.id == ref_id)
                .options(joinedload(Match.upload))
                .first()
            )
            if match and match.upload and match.upload.file_path:
                return (
                    self._build_image_url(match.upload.file_path, base_url),
                    self._build_star_pattern_url(match.upload.file_path, base_url)
                )

        elif ref_table in ("users", "user"):
            user = self.db.query(User).filter(User.id == ref_id).first()
            if user and user.profile_image:
                return self._build_profile_image_url(user.profile_image, base_url), None

        # Fallback if table name was unspecified but redirection_foreign_id is set
        run = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.id == ref_id)
            .options(joinedload(AnalysisRun.upload))
            .first()
        )
        if run and run.upload and run.upload.file_path:
            return (
                self._build_image_url(run.upload.file_path, base_url),
                self._build_star_pattern_url(run.upload.file_path, base_url)
            )

        upload = self.db.query(Upload).filter(Upload.id == ref_id).first()
        if upload and upload.file_path:
            return (
                self._build_image_url(upload.file_path, base_url),
                self._build_star_pattern_url(upload.file_path, base_url)
            )

        return None, None

    def _resolve_images_batch(
        self,
        notifications: List[Notification],
        base_url: str
    ) -> Dict[int, Tuple[Optional[str], Optional[str]]]:
        """
        Batch resolves images for a list of notifications to avoid N+1 queries.
        Returns a dictionary mapping notification.id to (image_url, star_pattern_url).
        """
        results: Dict[int, Tuple[Optional[str], Optional[str]]] = {}
        if not notifications:
            return results

        analysis_run_ids = set()
        upload_ids = set()
        match_ids = set()
        user_ids = set()
        unknown_ids = set()

        for n in notifications:
            if not n.redirection_foreign_id:
                results[n.id] = (None, None)
                continue

            table = (n.redirection_foreign_table or "").strip().lower()
            if table in ("analysis_runs", "analysis_run", "analyses", "analysis"):
                analysis_run_ids.add(n.redirection_foreign_id)
            elif table in ("uploads", "upload"):
                upload_ids.add(n.redirection_foreign_id)
            elif table in ("matches", "match"):
                match_ids.add(n.redirection_foreign_id)
            elif table in ("users", "user"):
                user_ids.add(n.redirection_foreign_id)
            else:
                unknown_ids.add(n.redirection_foreign_id)

        # Batch query AnalysisRuns
        runs_map: Dict[int, Optional[str]] = {}
        if analysis_run_ids or unknown_ids:
            target_ids = analysis_run_ids | unknown_ids
            runs = (
                self.db.query(AnalysisRun)
                .filter(AnalysisRun.id.in_(target_ids))
                .options(joinedload(AnalysisRun.upload))
                .all()
            )
            for r in runs:
                if r.upload and r.upload.file_path:
                    runs_map[r.id] = r.upload.file_path

        # Batch query Uploads
        uploads_map: Dict[int, Optional[str]] = {}
        if upload_ids or unknown_ids:
            target_ids = upload_ids | unknown_ids
            ups = self.db.query(Upload).filter(Upload.id.in_(target_ids)).all()
            for u in ups:
                if u.file_path:
                    uploads_map[u.id] = u.file_path

        # Batch query Matches
        matches_map: Dict[int, Optional[str]] = {}
        if match_ids:
            mts = (
                self.db.query(Match)
                .filter(Match.id.in_(match_ids))
                .options(joinedload(Match.upload))
                .all()
            )
            for m in mts:
                if m.upload and m.upload.file_path:
                    matches_map[m.id] = m.upload.file_path

        # Batch query Users
        users_map: Dict[int, Optional[str]] = {}
        if user_ids:
            usrs = self.db.query(User).filter(User.id.in_(user_ids)).all()
            for u in usrs:
                if u.profile_image:
                    users_map[u.id] = u.profile_image

        for n in notifications:
            if not n.redirection_foreign_id:
                results[n.id] = (None, None)
                continue

            ref_id = n.redirection_foreign_id
            table = (n.redirection_foreign_table or "").strip().lower()

            if table in ("analysis_runs", "analysis_run", "analyses", "analysis"):
                fpath = runs_map.get(ref_id)
                results[n.id] = (
                    self._build_image_url(fpath, base_url),
                    self._build_star_pattern_url(fpath, base_url)
                )
            elif table in ("uploads", "upload"):
                fpath = uploads_map.get(ref_id)
                results[n.id] = (
                    self._build_image_url(fpath, base_url),
                    self._build_star_pattern_url(fpath, base_url)
                )
            elif table in ("matches", "match"):
                fpath = matches_map.get(ref_id)
                results[n.id] = (
                    self._build_image_url(fpath, base_url),
                    self._build_star_pattern_url(fpath, base_url)
                )
            elif table in ("users", "user"):
                pimg = users_map.get(ref_id)
                results[n.id] = (self._build_profile_image_url(pimg, base_url), None)
            else:
                # Fallback for unknown table
                fpath = runs_map.get(ref_id) or uploads_map.get(ref_id)
                results[n.id] = (
                    self._build_image_url(fpath, base_url),
                    self._build_star_pattern_url(fpath, base_url)
                )

        return results

    def _build_image_url(self, file_path: Optional[str], base_url: str) -> Optional[str]:
        if not file_path:
            return None
        file_path = file_path.strip()
        if file_path.startswith("http://") or file_path.startswith("https://"):
            return file_path
        clean_path = file_path.lstrip("/")
        return f"{base_url}/{clean_path}"

    def _build_profile_image_url(self, profile_image: Optional[str], base_url: str) -> Optional[str]:
        if not profile_image:
            return None
        profile_image = profile_image.strip()
        if profile_image.startswith("http://") or profile_image.startswith("https://"):
            return profile_image
        filename = profile_image.split("/")[-1]
        return f"{base_url}/uploads/profile/{filename}"

    def _build_star_pattern_url(self, file_path: Optional[str], base_url: str) -> Optional[str]:
        if not file_path:
            return None
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        svg_rel_path = f"uploads/star-pattern/{name_without_ext}.svg"
        if os.path.exists(svg_rel_path):
            return f"{base_url}/{svg_rel_path}"
        return None

