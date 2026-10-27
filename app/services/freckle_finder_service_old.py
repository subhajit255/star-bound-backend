from pathlib import Path
import time
from uuid import uuid4
import io

from fastapi import HTTPException, UploadFile, status, Depends
from sqlalchemy.orm import Session
from PIL import Image

from app.api.deps import get_db
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.upload import Upload
from app.models.user import User
from detection.pipeline import detect_image


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024

def sanitize_image_bytes(content: bytes) -> tuple[bytes, str]:
    """
    Validates image bytes, converts non-RGB formats to RGB,
    and returns JPEG bytes along with the mime type.
    """
    try:
        # Verify the file is actually an image
        img = Image.open(io.BytesIO(content))
        img.verify()
        
        # Load it properly for conversion
        img = Image.open(io.BytesIO(content))
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=95)
        return out.getvalue(), "image/jpeg"
    except Exception as exc:
        raise ValueError("Invalid image content or unsupported format.") from exc


class FreckleFinderService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def process_freckle_image(
        self,
        image: UploadFile,
        current_user: User,
    ):
        """Store an image and return its automatically detected skin points."""
        if image.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG, PNG, and WebP images are supported")

        content = image.file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image must be 10 MB or smaller")
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is empty")

        try:
            sanitized_content, stored_type = sanitize_image_bytes(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        directory = Path("uploads/analysis") / str(current_user.id)
        directory.mkdir(parents=True, exist_ok=True)
        unique_filename = f"{int(time.time() * 1000)}.jpg"
        path = directory / unique_filename
        counter = 1
        while path.exists():
            unique_filename = f"{int(time.time() * 1000)}_{counter}.jpg"
            path = directory / unique_filename
            counter += 1

        path.write_bytes(sanitized_content)

        upload = Upload(
            user_id=current_user.id,
            file_name=unique_filename,
            file_path=str(path),
            file_type=stored_type,
        )
        self.db.add(upload)
        self.db.flush()

        try:
            result = detect_image(path)
        except ValueError as exc:
            self.db.rollback()
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        detections = [
            Detection(
                upload_id=upload.id,
                x=point.x,
                y=point.y,
                radius=point.radius,
                score=point.score,
                source=point.source,
            )
            for point in result.points
        ]
        self.db.add_all(detections)
        self.db.add(
            PointSet(
                upload_id=upload.id,
                n_points=len(detections),
                bbox=f"0,0,{result.width},{result.height}",
            )
        )
        self.db.commit()

        return {
            "upload_id": upload.id,
            "image": {"width": result.width, "height": result.height},
            "n_points": len(detections),
            "points": [
                {
                    "x": point.x,
                    "y": point.y,
                    "radius": point.radius,
                    "score": point.score,
                    "source": point.source,
                }
                for point in result.points
            ],
            "status": "detected",
        }
