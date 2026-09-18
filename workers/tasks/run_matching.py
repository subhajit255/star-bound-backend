from workers.celery_app import celery_app
from app.db import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from catalogue.matcher import match
from workers.tasks.matcher_state import get_matcher_state
import numpy as np
import traceback
import os

@celery_app.task(name="workers.tasks.run_matching.process_matching_job")
def process_matching_job(analysis_id: int):
    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
        if not run:
            return
            
        run.status = "processing"
        db.commit()
        
        try:
            detections = db.query(Detection).filter(Detection.upload_id == run.upload_id).all()
            point_set = db.query(PointSet).filter(PointSet.upload_id == run.upload_id).first()
            
            width, height = 0, 0
            if point_set and point_set.bbox:
                parts = point_set.bbox.split(",")
                if len(parts) == 4:
                    width, height = int(parts[2]), int(parts[3])
                    
            # Delete previous match if it exists
            db.query(Match).filter(Match.upload_id == run.upload_id).delete()
            db.commit()
            
            # Run Constellation Matcher
            if len(detections) >= 4 and width > 0 and height > 0:
                quad_index, catalogue_lookup = get_matcher_state()
                
                # Center and scale points to roughly a 20 degree Field of View
                max_dim = max(width, height)
                scale_factor = 20.0 / max_dim
                cx, cy = width / 2.0, height / 2.0
                
                scaled_points_xy = np.array([
                    [(d.x - cx) * scale_factor, (d.y - cy) * scale_factor]
                    for d in detections
                ])
                
                matches = match(scaled_points_xy, quad_index, catalogue_lookup)
                
                if matches:
                    best_match = matches[0]
                    db.add(
                        Match(
                            upload_id=run.upload_id,
                            rank=1,
                            ra=float(best_match.transform.translation[0]),
                            dec=float(best_match.transform.translation[1]),
                            roll=float(best_match.transform.rotation),
                            scale=float(best_match.transform.scale),
                            parity=int(best_match.parity),
                            n_matched=int(best_match.n_matched),
                            log_odds=float(best_match.log_odds),
                            confidence_pct=95.0, # Placeholder pending calibration
                            star_ids=[int(sid) for sid in best_match.star_ids_matched],
                            constellation="Unknown",
                            asterism_name="Your Stellaris"
                        )
                    )
                    
                    # Generate SVG skymap
                    star_coords = [catalogue_lookup[sid] for sid in best_match.star_ids_matched if sid in catalogue_lookup]
                    if star_coords:
                        coords = np.array(star_coords)
                        min_x, max_x = np.min(coords[:, 0]), np.max(coords[:, 0])
                        min_y, max_y = np.min(coords[:, 1]), np.max(coords[:, 1])
                        pad = max(max_x - min_x, max_y - min_y) * 0.15
                        if pad == 0:
                            pad = 1.0
                        min_x -= pad; max_x += pad
                        min_y -= pad; max_y += pad
                        
                        width_svg, height_svg = 800, 800
                        svg = [f'<svg width="{width_svg}" height="{height_svg}" xmlns="http://www.w3.org/2000/svg" style="background-color: #050510;">']
                        
                        # Draw constellation lines (simple spanning by x)
                        if len(coords) > 1:
                            svg.append('<polyline points="')
                            sorted_coords = coords[np.argsort(coords[:, 0])]
                            points_str = []
                            for x, y in sorted_coords:
                                cx = (x - min_x) / (max_x - min_x) * width_svg
                                cy = height_svg - (y - min_y) / (max_y - min_y) * height_svg
                                points_str.append(f"{cx},{cy}")
                            svg.append(" ".join(points_str))
                            svg.append('" fill="none" stroke="#4a90e2" stroke-width="2" stroke-dasharray="4,4" opacity="0.6"/>')
                        
                        # Draw stars
                        for x, y in coords:
                            cx = (x - min_x) / (max_x - min_x) * width_svg
                            cy = height_svg - (y - min_y) / (max_y - min_y) * height_svg
                            svg.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#ffffff" />')
                            svg.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="#ffffff" opacity="0.2" />')
                        
                        svg.append('</svg>')
                        
                        # Ensure directory exists
                        os.makedirs("uploads/star-pattern", exist_ok=True)
                        
                        # Use same base name as the upload file but with .svg
                        base_name = os.path.basename(run.upload.file_path)
                        name_without_ext = os.path.splitext(base_name)[0]
                        svg_path = os.path.join("uploads/star-pattern", f"{name_without_ext}.svg")
                        
                        with open(svg_path, "w") as f:
                            f.write("\n".join(svg))
            
            run.status = "success"
            db.commit()
            
            return {
                "matched": bool(matches),
                "n_matched_stars": best_match.n_matched if matches else 0
            }
            
        except Exception as e:
            db.rollback()
            run.status = "failed"
            db.commit()
            print(f"Error in matching pipeline for analysis {analysis_id}: {e}")
            traceback.print_exc()
            return {"error": str(e)}
            
    finally:
        db.close()
