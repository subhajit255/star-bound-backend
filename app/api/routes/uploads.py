from fastapi import APIRouter, Depends, File, UploadFile, status, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.upload import Upload
from pathlib import Path
from uuid import uuid4
from detection.pipeline import sanitize_image_bytes
from app.schemas.analysis import UploadResponse

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
def create_upload(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported",
        )

    content = image.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
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
        db.add(upload)
        db.commit()
        db.refresh(upload)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise

    return {
        "upload_id": upload.id,
        "url": f"/uploads/analysis/{user_identifier}/{path.name}"
    }