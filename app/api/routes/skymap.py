from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.analysis_run import AnalysisRun
from app.models.match import Match
from app.models.user import User
from app.schemas.skymap import SkymapNameUpdate, SkymapResponse, SkymapUpdateResponse, BuildIndexResponse

router = APIRouter()

@router.get("/{id}/skymap", response_model=SkymapResponse)
def get_skymap(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
        
    if run.upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    match = db.query(Match).filter(Match.upload_id == run.upload_id).first()
    if not match:
        return {"id": id, "status": run.status, "message": "No match data available yet."}
        
    import os
    star_pattern_url = None
    if match:
        base_name = os.path.basename(run.upload.file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        svg_path = os.path.join("uploads/star-pattern", f"{name_without_ext}.svg")
        if os.path.exists(svg_path):
            star_pattern_url = f"/uploads/star-pattern/{name_without_ext}.svg"
            
    return {
        "id": id,
        "status": run.status,
        "match": {
            "ra": match.ra,
            "dec": match.dec,
            "roll": match.roll,
            "scale": match.scale,
            "n_matched": match.n_matched,
            "confidence_pct": match.confidence_pct,
            "star_ids": match.star_ids,
            "constellation": match.constellation,
            "asterism_name": match.asterism_name,
            "asterism_meaning": match.asterism_meaning,
            "story": match.story,
            "discovered_on": run.upload.created_at.strftime("%b %d, %Y") if run.upload.created_at else None,
            "star_pattern_url": star_pattern_url
        }
    }

@router.get("/{id}/image", responses={200: {"content": {"image/*": {}}}})
def get_skymap_image(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
        
    if run.upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    import os
    file_path = run.upload.file_path
    
    base_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(base_name)[0]
    svg_path = os.path.join("uploads/star-pattern", f"{name_without_ext}.svg")
    
    if os.path.exists(svg_path):
        return FileResponse(path=svg_path, media_type="image/svg+xml")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found on server")
        
    return FileResponse(path=file_path, media_type=run.upload.file_type or "image/jpeg")

@router.patch("/{id}/skymap", response_model=SkymapUpdateResponse)
def update_skymap_name(
    id: int, 
    update_data: SkymapNameUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
        
    if run.upload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    match = db.query(Match).filter(Match.upload_id == run.upload_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        
    match.asterism_name = update_data.asterism_name
    match.asterism_meaning = update_data.asterism_meaning
    
    # Generate placeholder story
    match.story = (
        f"In ancient times, {update_data.asterism_name} was known as the keeper of night's gentle glow. "
        f"She guided lost travelers with her radiant light and taught the stars to shine with kindness. "
        f"Her story lives on in the heart of the cosmos, just like you."
    )
    
    db.commit()
    
    return {"message": "Constellation updated successfully", "story": match.story}

@router.post("/build-index", response_model=BuildIndexResponse)
def build_catalogue_index():
    from workers.tasks.build_index import build_catalogue_index as build_task
    task = build_task.delay()
    return {"status": "processing", "task_id": task.id, "message": "Building catalogue index in background."}

@router.get("/{id}/overlay", responses={200: {"content": {"image/jpeg": {}}}})
def get_overlay_image(id: int, db: Session = Depends(get_db)):
    # This endpoint is a convenience for debugging and visualization.
    # It draws the matched stars onto the original image.
    import cv2
    import numpy as np
    from app.models.detection import Detection
    from app.models.point_set import PointSet
    from catalogue.download import load_filtered_catalogue
    from scipy.spatial.distance import cdist
    from skimage.transform import SimilarityTransform
    
    run = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    match = db.query(Match).filter(Match.upload_id == run.upload_id).first()
    point_set = db.query(PointSet).filter(PointSet.upload_id == run.upload_id).first()
    if not match or not point_set:
        raise HTTPException(status_code=404, detail="Match not found")
        
    detections = db.query(Detection).filter(Detection.upload_id == run.upload_id).all()
    
    parts = point_set.bbox.split(",")
    width, height = int(parts[2]), int(parts[3])
    
    max_dim = max(width, height)
    scale_factor = 20.0 / max_dim
    cx, cy = width / 2.0, height / 2.0
    
    scaled_points_xy = np.array([
        [(d.x - cx) * scale_factor, (d.y - cy) * scale_factor]
        for d in detections
    ])
    
    df = load_filtered_catalogue("data/hygdata_v41.csv")
    df["ra_deg"] = df["ra"] * 15.0
    catalogue_lookup = {
        row["star_idx"]: (row["ra_deg"], row["dec"]) 
        for _, row in df.iterrows()
    }
    
    matched_star_coords = np.array([catalogue_lookup[sid] for sid in match.star_ids if sid in catalogue_lookup])
    if len(matched_star_coords) == 0:
        raise HTTPException(status_code=404, detail="No matched stars in catalogue")
        
    model = SimilarityTransform(scale=match.scale, rotation=match.roll, translation=(match.ra, match.dec))
    projected = model(scaled_points_xy)
    dists = cdist(matched_star_coords, projected)
    
    matched_freckle_indices = []
    for i in range(len(matched_star_coords)):
        closest_freckle_idx = np.argmin(dists[i])
        if dists[i, closest_freckle_idx] < 0.2:
            matched_freckle_indices.append(closest_freckle_idx)
            
    img = cv2.imread(run.upload.file_path)
    if img is None:
        raise HTTPException(status_code=404, detail="Original image missing")
        
    for d in detections:
        cv2.circle(img, (int(d.x), int(d.y)), int(max(2, d.radius)), (0, 100, 0), 1)
        
    matched_freckles = [detections[idx] for idx in matched_freckle_indices]
    matched_freckles.sort(key=lambda d: d.x)
    
    for i in range(len(matched_freckles)):
        d = matched_freckles[i]
        cv2.circle(img, (int(d.x), int(d.y)), 4, (255, 255, 255), -1)
        cv2.circle(img, (int(d.x), int(d.y)), 10, (255, 200, 100), 2)
        if i < len(matched_freckles) - 1:
            next_d = matched_freckles[i+1]
            cv2.line(img, (int(d.x), int(d.y)), (int(next_d.x), int(next_d.y)), (255, 200, 100), 2)
            
    import tempfile
    _, tmp_path = tempfile.mkstemp(suffix=".jpg")
    cv2.imwrite(tmp_path, img)
    return FileResponse(path=tmp_path, media_type="image/jpeg")

