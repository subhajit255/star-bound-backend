import argparse
from pathlib import Path
import cv2
import numpy as np
from detection.pipeline import detect_image
from skimage.measure import ransac
from skimage.transform import SimilarityTransform

def compute_jaccard(points_a, points_b, threshold=5.0):
    """
    Computes the Jaccard index (Intersection over Union) of two point sets.
    points_a and points_b should be aligned into the same coordinate space first.
    Two points are considered a match if they are within `threshold` pixels.
    """
    if len(points_a) == 0 and len(points_b) == 0:
        return 1.0
    if len(points_a) == 0 or len(points_b) == 0:
        return 0.0

    # Greedy matching O(N^2)
    matched_b = set()
    intersection_count = 0
    
    for pa in points_a:
        best_dist = float('inf')
        best_idx = -1
        for i, pb in enumerate(points_b):
            if i in matched_b:
                continue
            dist = np.sqrt((pa[0] - pb[0])**2 + (pa[1] - pb[1])**2)
            if dist < threshold and dist < best_dist:
                best_dist = dist
                best_idx = i
                
        if best_idx != -1:
            intersection_count += 1
            matched_b.add(best_idx)
            
    union_count = len(points_a) + len(points_b) - intersection_count
    return intersection_count / union_count

def align_point_sets(points_src, points_dst):
    """
    Uses RANSAC to find a similarity transform (translation, rotation, scale)
    between two point sets. This is necessary because the camera might have moved
    between photos.
    Returns the aligned points_src.
    """
    if len(points_src) < 2 or len(points_dst) < 2:
        return points_src
        
    src_arr = np.array(points_src)
    dst_arr = np.array(points_dst)
    
    # In a real scenario, we'd need feature descriptors to match points before RANSAC.
    # For this simplistic harness, we assume points are roughly ordered similarly 
    # or we fall back to a naive alignment.
    # To truly do this, you might extract ORB/SIFT features at the detected points 
    # and match them, then run RANSAC on the matches.
    # For now, we will simulate the structure.
    
    try:
        # Sort points top-to-bottom, left-to-right to ensure roughly consistent ordering 
        # for this dummy alignment harness, since scores might fluctuate and change order.
        src_sorted = sorted(src_arr, key=lambda p: (p[1], p[0]))
        dst_sorted = sorted(dst_arr, key=lambda p: (p[1], p[0]))
        
        src_sorted = np.array(src_sorted)
        dst_sorted = np.array(dst_sorted)
        
        min_len = min(len(src_sorted), len(dst_sorted))
        model, inliers = ransac((src_sorted[:min_len], dst_sorted[:min_len]), SimilarityTransform, min_samples=2,
                                residual_threshold=5, max_trials=100)
        
        # Apply the transform to all source points
        aligned_src = model(src_arr)
        return aligned_src
    except Exception as e:
        print(f"Alignment failed: {e}")
        return src_arr

def evaluate_repeatability(image_paths):
    """
    Evaluates the detection pipeline on multiple images of the SAME skin patch.
    Calculates the average Jaccard index to verify repeatability.
    """
    if len(image_paths) < 2:
        print("Need at least 2 images to compare repeatability.")
        return

    point_sets = []
    print("Running detection pipeline on images...")
    for path in image_paths:
        result = detect_image(path)
        pts = [(p.x, p.y) for p in result.points]
        point_sets.append(pts)
        print(f"  {path.name}: Detected {len(pts)} points")

    print("\nCalculating Jaccard Index (Repeatability) across pairs...")
    jaccards = []
    for i in range(len(point_sets)):
        for j in range(i + 1, len(point_sets)):
            pts_a = point_sets[i]
            pts_b = point_sets[j]
            
            # 1. Align point set B to match point set A
            aligned_b = align_point_sets(pts_b, pts_a)
            
            # 2. Compute Jaccard Index
            jaccard = compute_jaccard(pts_a, aligned_b)
            jaccards.append(jaccard)
            print(f"  Pair ({i}, {j}): Jaccard = {jaccard:.2f}")
            
    avg_jaccard = sum(jaccards) / len(jaccards)
    print(f"\nAverage Repeatability (Jaccard Index): {avg_jaccard:.2f}")
    if avg_jaccard >= 0.80:
        print("✅ Milestone 1 Repeatability Target Achieved (>= 0.80)!")
    else:
        print("❌ Repeatability Target Failed (< 0.80). Requires tuning.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate detection repeatability on a set of re-shoots.")
    parser.add_argument("image_dir", type=str, help="Directory containing re-shoots of the same skin patch")
    args = parser.parse_args()
    
    image_dir = Path(args.image_dir)
    image_paths = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.jpeg")) + list(image_dir.glob("*.png"))
    
    if not image_paths:
        print(f"No images found in {image_dir}")
    else:
        evaluate_repeatability(image_paths)
