from app.db import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.point_set import PointSet
from app.models.match import Match
from app.models.detection import Detection

db = SessionLocal()

print("--- Recent Analysis Runs ---")
runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).limit(5).all()
for run in runs:
    print(f"\nAnalysis ID: {run.id}, Upload ID: {run.upload_id}, Status: {run.status}")
    
    ps = db.query(PointSet).filter(PointSet.upload_id == run.upload_id).first()
    if ps:
        print(f"  PointSet: N_points: {ps.n_points}")
    else:
        print("  PointSet: None")
        
    m = db.query(Match).filter(Match.upload_id == run.upload_id).first()
    if m:
        print(f"  Match: ID: {m.id}, Confidence: {m.confidence_pct}")
    else:
        print("  Match: None")
