import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import cv2
import numpy as np
from skimage.feature import blob_dog
from detection.pipeline import _skin_mask, _remove_hair, _correct_illumination

def debug_detect(path: str):
    print(f"Debugging {path}")
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        print("Failed to read image")
        return
        
    height, width = image.shape[:2]
    print(f"Image size: {width}x{height}")
    
    image_no_hair = _remove_hair(image)
    mask = _skin_mask(image_no_hair)
    mask_ratio = np.count_nonzero(mask) / (width * height)
    print(f"Skin mask coverage: {mask_ratio:.2%}")
    
    lab = cv2.cvtColor(image_no_hair, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]
    signal = _correct_illumination(l_channel)
    signal[mask == 0] = 0
    
    blobs = blob_dog(
        signal.astype(np.float32) / 255.0,
        min_sigma=2,
        max_sigma=min(24, max(4, min(width, height) / 16)),
        sigma_ratio=1.6,
        threshold=0.02, # Lowered from 0.06
        overlap=0.1,
    )
    print(f"Initial blob_dog count (thresh=0.02): {len(blobs)}")
    
    filtered_count = 0
    for y, x, sigma in blobs:
        radius = float(sigma * np.sqrt(2))
        if radius < 2 or radius > min(width, height) * 0.04:
            continue
            
        xi, yi = int(round(x)), int(round(y))
        edge_margin = int(min(width, height) * 0.08)
        if not (edge_margin <= xi < width - edge_margin and edge_margin <= yi < height - edge_margin) or mask[yi, xi] == 0:
            continue
            
        patch_size = int(radius * 2 + 2)
        r = patch_size // 2
        y1, y2 = max(0, yi - r), min(height, yi + r)
        x1, x2 = max(0, xi - r), min(width, xi + r)
        if y2 - y1 < 3 or x2 - x1 < 3:
            continue
            
        patch_hsv = cv2.cvtColor(image_no_hair[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        mean_hue = np.median(patch_hsv[:,:,0])
        if mean_hue < 5 or mean_hue > 170:
            continue
            
        local_signal = signal[y1:y2, x1:x2]
        _, local_thresh = cv2.threshold(local_signal, 10, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(local_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
            
        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area == 0:
            continue
            
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
            
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
            
        convexity = area / hull_area
        if circularity < 0.4 or convexity < 0.7:
            continue
            
        local = signal[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3]
        score = float(np.clip(local.mean() / 255.0, 0.0, 1.0))
        
        # Lower score threshold for this image (max was 57/255 = 0.22)
        if score >= 0.05:
            filtered_count += 1
            
    print(f"Points after filtering: {filtered_count}")

if __name__ == "__main__":
    debug_detect("/Users/subhajitsaha/.gemini/antigravity-ide/brain/734ca4d8-7568-4b31-8ec2-02e2a60d23e2/.user_uploaded/media_1788378000691.jpg")
