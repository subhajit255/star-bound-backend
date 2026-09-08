import sys
import os
sys.path.append("/Users/subhajitsaha/Downloads/stellaris-backend")
from dotenv import load_dotenv
load_dotenv()

import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from skimage.transform import SimilarityTransform
from catalogue.download import load_filtered_catalogue
from scipy.spatial.distance import cdist

def generate_overlay(analysis_id, out_path):
    db = SessionLocal()
    run = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
    if not run:
        print("Run not found")
        return
        
    detections = db.query(Detection).filter(Detection.upload_id == run.upload_id).all()
    point_set = db.query(PointSet).filter(PointSet.upload_id == run.upload_id).first()
    match = db.query(Match).filter(Match.upload_id == run.upload_id).first()
    
    if not match or not point_set:
        print("Match or point set not found")
        return
        
    parts = point_set.bbox.split(",")
    width, height = int(parts[2]), int(parts[3])
    
    # Reconstruct the scaled points
    max_dim = max(width, height)
    scale_factor = 20.0 / max_dim
    cx, cy = width / 2.0, height / 2.0
    
    scaled_points_xy = np.array([
        [(d.x - cx) * scale_factor, (d.y - cy) * scale_factor]
        for d in detections
    ])
    
    # Load catalogue to get coords of matched stars
    df = load_filtered_catalogue("data/hygdata_v41.csv")
    df["ra_deg"] = df["ra"] * 15.0
    catalogue_lookup = {
        row["star_idx"]: (row["ra_deg"], row["dec"]) 
        for _, row in df.iterrows()
    }
    
    # Get the coordinates of the matched stars
    matched_star_coords = np.array([catalogue_lookup[sid] for sid in match.star_ids if sid in catalogue_lookup])
    
    # Reconstruct the transform model
    model = SimilarityTransform(scale=match.scale, rotation=match.roll, translation=(match.ra, match.dec))
    
    # Project the freckles to the sky
    projected = model(scaled_points_xy)
    
    # Find which freckles map to the matched stars
    # For each matched star, find the closest projected freckle
    dists = cdist(matched_star_coords, projected)
    
    matched_freckle_indices = []
    for i in range(len(matched_star_coords)):
        # Find the freckle closest to this star
        closest_freckle_idx = np.argmin(dists[i])
        # Only accept if within a small tolerance (VERIFY_TOLERANCE was 0.2)
        if dists[i, closest_freckle_idx] < 0.2:
            matched_freckle_indices.append(closest_freckle_idx)
            
    # Load the original image
    img = cv2.imread(run.upload.file_path)
    if img is None:
        print(f"Image not found at {run.upload.file_path}")
        return
        
    # Draw all detections lightly
    for d in detections:
        cv2.circle(img, (int(d.x), int(d.y)), int(max(2, d.radius)), (0, 100, 0), 1)
        
    # Draw matched freckles prominently and connect them
    matched_freckles = [detections[idx] for idx in matched_freckle_indices]
    
    # Sort them left to right to connect them just like the SVG
    matched_freckles.sort(key=lambda d: d.x)
    
    for i in range(len(matched_freckles)):
        d = matched_freckles[i]
        # Draw glowing circle
        cv2.circle(img, (int(d.x), int(d.y)), 6, (255, 255, 255), 2)
        cv2.circle(img, (int(d.x), int(d.y)), 12, (255, 200, 100), 2)
        
        # Connect to next
        if i < len(matched_freckles) - 1:
            next_d = matched_freckles[i+1]
            cv2.line(img, (int(d.x), int(d.y)), (int(next_d.x), int(next_d.y)), (255, 200, 100), 2)
            
    # Add text
    cv2.putText(img, f"Constellation: {match.asterism_name}", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(img, f"Stars matched: {match.n_matched}", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    
    cv2.imwrite(out_path, img)
    print(f"Saved overlay to {out_path}")

if __name__ == "__main__":
    generate_overlay(14, "/Users/subhajitsaha/.gemini/antigravity-ide/brain/99fa532b-802d-4799-a8f7-5ccdb31e4490/scratch/overlay.jpg")
