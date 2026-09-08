import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models.user import User
from app.models.upload import Upload
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from app.models.role import Role
from workers.tasks.analysis_tasks import process_detection_job
import datetime

def run_test():
    db = SessionLocal()
    print("Setting up test data...")
    
    role = db.query(Role).first()
    if not role:
        role = Role(name="User", slug="user")
        db.add(role)
        db.commit()
        db.refresh(role)
        
    user = db.query(User).first()
    if not user:
        user = User(
            name="Test User", 
            email="test@example.com", 
            user_name="testuser",
            password="fake",
            role_id=role.id,
            verified_at=datetime.datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    upload = Upload(
        user_id=user.id,
        file_name="mole.jpg",
        file_path="test_images/mole.jpg",
        file_type="image/jpeg"
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    
    run = AnalysisRun(
        upload_id=upload.id,
        status="queued"
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    
    print(f"Created Upload ID {upload.id} and AnalysisRun ID {run.id}")
    db.close() # Close session so process_detection_job gets a fresh read if it's sqlite
    
    print("Running process_detection_job...")
    # Celery tasks need to be called with .apply() to run locally synchronously, or we can just call it if it's directly callable.
    try:
        # In newer Celery, you can call it directly, or .apply() if needed
        # We will try .apply()
        result = process_detection_job.apply(args=[run.id])
        print(f"Task result: {result.status}, {result.result}")
    except Exception as e:
        print("Failed with apply, trying direct call:", e)
        process_detection_job(run.id)
    
    print("Job finished.")
    
    db = SessionLocal()
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run.id).first()
    print(f"Final run status: {run.status}")
    
    point_set = db.query(PointSet).filter(PointSet.upload_id == upload.id).first()
    if point_set:
        print(f"Generated PointSet: {point_set.n_points} points, bbox: {point_set.bbox}")
    else:
        print("No PointSet generated.")
        
    detections = db.query(Detection).filter(Detection.upload_id == upload.id).all()
    print(f"Generated {len(detections)} Detections.")
    
    matches = db.query(Match).filter(Match.upload_id == upload.id).all()
    if matches:
        for m in matches:
            print(f"Match found: {m.asterism_name} (n_matched={m.n_matched}, confidence={m.confidence_pct}%)")
    else:
        print("No Matches found.")
        
    db.close()

if __name__ == "__main__":
    run_test()
