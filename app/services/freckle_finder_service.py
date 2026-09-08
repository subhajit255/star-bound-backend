from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.upload import Upload
from app.models.user import User
from app.models.analysis_run import AnalysisRun
from detection.pipeline import sanitize_image_bytes
from workers.tasks.analysis_tasks import process_detection_job


class FreckleFinderService:
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_BYTES = 10 * 1024 * 1024

    def __init__(self, db: Session):
        self.db = db

    def process_freckle_image(
        self,
        image: UploadFile,
        current_user: User,
    ) -> dict:
        if image.content_type not in self.ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only JPEG, PNG, and WebP images are supported",
            )

        content = image.file.read(self.MAX_BYTES + 1)
        if len(content) > self.MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image must be 10 MB or smaller",
            )
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image is empty",
            )

        try:
            sanitized_content, stored_type = sanitize_image_bytes(content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        user_identifier = current_user.user_name if current_user.user_name else str(current_user.id)
        directory = Path("uploads/analysis") / user_identifier
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4().hex}.jpg"
        path.write_bytes(sanitized_content)

        try:
            upload = Upload(
                user_id=current_user.id,
                file_name=image.filename or path.name,
                file_path=str(path),
                file_type=stored_type,
            )
            self.db.add(upload)
            self.db.flush()
            
            analysis_run = AnalysisRun(
                upload_id=upload.id,
                status="queued"
            )
            self.db.add(analysis_run)
            self.db.commit()
            
            # Enqueue Celery task
            process_detection_job.delay(analysis_run.id)
            
        except Exception:
            self.db.rollback()
            path.unlink(missing_ok=True)
            raise

        return {
            "upload_id": upload.id,
            "analysis_id": analysis_run.id,
            "status": "queued",
        }