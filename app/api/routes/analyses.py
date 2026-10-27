from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.user import User
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from app.models.upload import Upload
from app.schemas.analysis import AnalysisCreate, PointsPatch, AnalysisCreateResponse, ConstellationItem, AnalysisResponse, PointsPatchResponse
from typing import List
from workers.tasks.analysis_tasks import process_detection_job
from workers.tasks.run_matching import process_matching_job

router = APIRouter()

@router.post("/", response_model=AnalysisCreateResponse)
def create_analysis(
    analysis_create: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    upload = db.query(Upload).filter(Upload.id == analysis_create.upload_id).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
        
    if upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    analysis_run = AnalysisRun(
        upload_id=upload.id,
        status="queued"
    )
    db.add(analysis_run)
    db.commit()
    db.refresh(analysis_run)
    
    # Enqueue Celery task
    process_detection_job.delay(analysis_run.id)
    
    return {
        "analysis_id": analysis_run.id,
        "status": "queued"
    }

@router.get("/me/constellations", response_model=List[ConstellationItem])
def get_my_constellations(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    matches = (
        db.query(Match, Upload)
        .join(Upload, Match.upload_id == Upload.id)
        .filter(Upload.user_id == current_user.id)
        .order_by(Match.id.desc())
        .all()
    )
    
    import os
    response = []
    base_url = str(request.base_url).rstrip("/") if request else settings.BASE_URL.rstrip("/")
    for match, upload in matches:
        base_name = os.path.basename(upload.file_path) if upload.file_path else ""
        name_without_ext = os.path.splitext(base_name)[0]
        svg_rel_path = f"uploads/star-pattern/{name_without_ext}.svg"
        star_pattern_url = f"{base_url}/{svg_rel_path}" if os.path.exists(svg_rel_path) else None
        
        analysis_run = db.query(AnalysisRun).filter(AnalysisRun.upload_id == upload.id).order_by(AnalysisRun.id.desc()).first()
        
        image_url = None
        if upload.file_path:
            clean_path = upload.file_path.lstrip("/")
            image_url = f"{base_url}/{clean_path}"
            
        response.append({
            "id": match.id,
            "upload_id": match.upload_id,
            "analysis_id": analysis_run.id if analysis_run else None,
            "rank": match.rank,
            "ra": match.ra,
            "dec": match.dec,
            "roll": match.roll,
            "scale": match.scale,
            "parity": match.parity,
            "n_matched": match.n_matched,
            "log_odds": match.log_odds,
            "confidence_pct": match.confidence_pct,
            "star_ids": match.star_ids,
            "constellation": match.constellation,
            "asterism_name": match.asterism_name,
            "asterism_meaning": match.asterism_meaning,
            "story": match.story,
            "star_pattern_url": star_pattern_url,
            "image_url": image_url,
            "discovered_on": upload.created_at.strftime("%b %d, %Y") if upload.created_at else None,
            "created_at": upload.created_at.isoformat() if upload.created_at else None
        })
        
    return response

@router.get("/{id}", response_model=AnalysisResponse)
def get_analysis(
    id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis_run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not analysis_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
        
    if analysis_run.upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    base_url = str(request.base_url).rstrip("/") if request else settings.BASE_URL.rstrip("/")
    image_url = None
    if analysis_run.upload and analysis_run.upload.file_path:
        clean_path = analysis_run.upload.file_path.lstrip("/")
        image_url = f"{base_url}/{clean_path}"

    response = {
        "analysis_id": analysis_run.id,
        "upload_id": analysis_run.upload_id,
        "status": analysis_run.status,
        "image_url": image_url,
    }
    
    if analysis_run.status in ("freckles_detected", "matching_stars", "success"):
        detections = db.query(Detection).filter(Detection.upload_id == analysis_run.upload_id).all()
        point_set = db.query(PointSet).filter(PointSet.upload_id == analysis_run.upload_id).first()
        match = db.query(Match).filter(Match.upload_id == analysis_run.upload_id).first()
        
        width, height = 0, 0
        if point_set and point_set.bbox:
            parts = point_set.bbox.split(",")
            if len(parts) == 4:
                width, height = int(parts[2]), int(parts[3])
                
        response["image"] = {"width": width, "height": height}
        response["n_points"] = len(detections)
        response["points"] = [
            {
                "x": d.x,
                "y": d.y,
                "radius": d.radius,
                "score": d.score,
                "source": d.source,
            }
            for d in detections
        ]
        
        if match:
            response["match"] = {
                "ra": match.ra,
                "dec": match.dec,
                "roll": match.roll,
                "scale": match.scale,
                "n_matched": match.n_matched,
                "confidence_pct": match.confidence_pct,
                "constellation": match.constellation,
                "asterism_name": match.asterism_name
            }
        
    return response

@router.patch("/{id}/points", response_model=PointsPatchResponse)
def update_analysis_points(
    id: int,
    patch: PointsPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis_run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not analysis_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
        
    if analysis_run.upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    upload_id = analysis_run.upload_id
    
    # Delete existing detections
    db.query(Detection).filter(Detection.upload_id == upload_id).delete()
    
    # Insert new detections
    new_detections = []
    for p in patch.points:
        new_detections.append(Detection(
            upload_id=upload_id,
            x=p.x,
            y=p.y,
            radius=p.radius,
            score=p.score,
            source=p.source
        ))
        
    db.add_all(new_detections)
    
    # Update point set count
    point_set = db.query(PointSet).filter(PointSet.upload_id == upload_id).first()
    if point_set:
        point_set.n_points = len(new_detections)
        
    # Mark analysis as matching
    analysis_run.status = "matching_stars"
    
    db.commit()
    
    # Enqueue new matching job
    process_matching_job.delay(analysis_run.id)
    
    return {"message": "Points updated, matching re-triggered", "status": "matching_stars"}
