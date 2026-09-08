from workers.celery_app import celery_app
from app.db import SessionLocal
from app.models.upload import Upload
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from detection.pipeline import detect_image
from catalogue.matcher import match
from workers.tasks.matcher_state import get_matcher_state
from pathlib import Path
import numpy as np
import traceback

@celery_app.task(name="workers.tasks.analysis_tasks.process_detection_job")
def process_detection_job(analysis_id: int):
    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
        if not run:
            return
            
        run.status = "processing"
        db.commit()
        
        upload = db.query(Upload).filter(Upload.id == run.upload_id).first()
        if not upload:
            run.status = "failed"
            db.commit()
            return
            
        path = Path(upload.file_path)
        if not path.exists():
            run.status = "failed"
            db.commit()
            return
            
        try:
            result = detect_image(path)
            
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
            db.add_all(detections)
            
            db.add(
                PointSet(
                    upload_id=upload.id,
                    n_points=len(detections),
                    bbox=f"0,0,{result.width},{result.height}",
                )
            )
            
            # Run Constellation Matcher
            if len(result.points) >= 4:
                quad_index, catalogue_lookup = get_matcher_state()
                
                # Center and scale points to roughly a 20 degree Field of View
                max_dim = max(result.width, result.height)
                scale_factor = 20.0 / max_dim
                cx, cy = result.width / 2.0, result.height / 2.0
                
                scaled_points_xy = np.array([
                    [(p.x - cx) * scale_factor, (p.y - cy) * scale_factor]
                    for p in result.points
                ])
                
                matches = match(scaled_points_xy, quad_index, catalogue_lookup)
                
                if matches:
                    best_match = matches[0]
                    db.add(
                        Match(
                            upload_id=upload.id,
                            rank=1,
                            ra=float(best_match.transform.translation[0]),
                            dec=float(best_match.transform.translation[1]),
                            roll=float(best_match.transform.rotation),
                            scale=float(best_match.transform.scale),
                            parity=int(best_match.parity),
                            n_matched=int(best_match.n_matched),
                            log_odds=float(best_match.log_odds),
                            confidence_pct=float((best_match.n_matched / len(result.points)) * 100.0),
                            star_ids=[int(sid) for sid in best_match.star_ids_matched],
                            constellation="Unknown",
                            asterism_name="Your Stellaris"
                        )
                    )
            
            run.status = "success"
            db.commit()
            
        except Exception as e:
            db.rollback()
            run.status = "failed"
            db.commit()
            print(f"Error in detection pipeline for analysis {analysis_id}: {e}")
            traceback.print_exc()
            
    finally:
        db.close()
