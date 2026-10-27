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
            
        run.status = "detecting_freckles"
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
            if detections:
                db.add_all(detections)
            
            db.add(
                PointSet(
                    upload_id=upload.id,
                    n_points=len(detections),
                    bbox=f"0,0,{result.width},{result.height}",
                )
            )
            
            from app.traits.push_notification_trait import PushNotificationTrait
            from workers.tasks.run_matching import process_matching_job

            if len(result.points) > 0:
                run.status = "freckles_detected"
                db.commit()

                # Notify user that freckles were detected with coordinates
                PushNotificationTrait.notify_user(
                    db=db,
                    user_id=upload.user_id,
                    title="Freckles Detected!",
                    body="Your freckles have been detected. You can now proceed to generate your constellation.",
                    notification_type="freckle_detection_success",
                    data={
                        "analysis_id": str(analysis_id),
                        "upload_id": str(upload.id),
                        "status": "freckles_detected",
                        "freckle_count": str(len(result.points)),
                    },
                    redirection_id=analysis_id,
                    redirection_table="analysis_runs",
                )

                # Trigger Constellation Matcher in background
                process_matching_job.delay(analysis_id)
                
                return {
                    "points_detected": len(result.points)
                }
            else:
                run.status = "no_freckles_detected"
                db.commit()

                # Notify user that no freckles were detected
                PushNotificationTrait.notify_user(
                    db=db,
                    user_id=upload.user_id,
                    title="No Freckles Detected",
                    body="No freckles were identified in your uploaded photo. Please try uploading a clearer, well-lit image.",
                    notification_type="no_freckles_detected",
                    data={
                        "analysis_id": str(analysis_id),
                        "upload_id": str(upload.id),
                        "status": "no_freckles_detected",
                        "freckle_count": "0",
                    },
                    redirection_id=analysis_id,
                    redirection_table="analysis_runs",
                )

                return {
                    "points_detected": 0
                }
            
        except Exception as e:
            db.rollback()
            run.status = "failed"
            db.commit()
            print(f"Error in detection pipeline for analysis {analysis_id}: {e}")
            traceback.print_exc()

            try:
                from app.traits.push_notification_trait import PushNotificationTrait
                PushNotificationTrait.notify_user(
                    db=db,
                    user_id=upload.user_id,
                    title="Freckle Analysis Failed",
                    body="An error occurred while analyzing freckles. Please try uploading your image again.",
                    notification_type="freckle_detection_failed",
                    data={
                        "analysis_id": str(analysis_id),
                        "upload_id": str(upload.id),
                        "status": "failed",
                    },
                    redirection_id=analysis_id,
                    redirection_table="analysis_runs",
                )
            except Exception as notify_err:
                print(f"Failed to send failure notification: {notify_err}")

            return {"error": str(e)}
            
    finally:
        db.close()
