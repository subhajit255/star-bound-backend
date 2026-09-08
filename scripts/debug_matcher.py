import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import numpy as np
from detection.pipeline import detect_image
from catalogue.matcher import match, VERIFY_TOLERANCE, _candidate_query_quads
from catalogue.quads import _quad_hash, SCALE_BANDS_DEG
from workers.tasks.matcher_state import get_matcher_state

def debug_matcher(path: str):
    print(f"Detecting points on {path}")
    result = detect_image(path) # Let's NOT skip NN
    points = result.points
    print(f"Found {len(points)} points (NN enabled)")
    
    if len(points) < 4:
        print("Not enough points to match")
        return
        
    print("Loading matcher state...")
    quad_index, catalogue_lookup = get_matcher_state()
    
    max_dim = max(result.width, result.height)
    scale_factor = 20.0 / max_dim
    cx, cy = result.width / 2.0, result.height / 2.0
    
    scaled_points_xy = np.array([
        [(p.x - cx) * scale_factor, (p.y - cy) * scale_factor]
        for p in points
    ])
    
    combos = _candidate_query_quads(scaled_points_xy)
    print(f"Found {len(combos)} candidate quads")
    candidates = []
    for combo in combos:
        pts = scaled_points_xy[list(combo)]
        hash_res = _quad_hash(pts)
        if not hash_res: continue
        code, order, parity = hash_res
        
        for band in range(len(SCALE_BANDS_DEG)):
            hits = quad_index.query(code, band=band, k=3, max_dist=0.03)
            candidates.extend(hits)
            
    print(f"Found {len(candidates)} total index hits across all quads")
    
    print(f"VERIFY_TOLERANCE is {VERIFY_TOLERANCE}")
    matches = match(scaled_points_xy, quad_index, catalogue_lookup)
    
    if matches:
        print(f"Found {len(matches)} matches!")
        for m in matches[:3]:
            print(f"Match: {m.n_matched} points, log_odds {m.log_odds}, stars: {m.star_ids_matched}")
    else:
        print("No matches found.")

if __name__ == "__main__":
    debug_matcher("/Users/subhajitsaha/.gemini/antigravity-ide/brain/734ca4d8-7568-4b31-8ec2-02e2a60d23e2/.user_uploaded/media_1788378000691.jpg")
