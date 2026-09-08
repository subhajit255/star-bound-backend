import cv2
import numpy as np
from pathlib import Path

def generate_test_images(output_dir: str):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Base image dimensions
    width, height = 400, 400
    
    # Create base skin-colored image (BGR for OpenCV)
    # Skin color roughly YCrCb: Y~150, Cr~140, Cb~110 -> BGR ~ (150, 180, 210)
    # Let's just use a light peachy color in BGR: (150, 180, 220)
    base_img = np.full((height, width, 3), (150, 180, 220), dtype=np.uint8)
    
    # Add some dark spots (freckles)
    spots = [
        (100, 100, 5),
        (150, 200, 4),
        (250, 150, 6),
        (300, 300, 3),
        (180, 80, 5),
    ]
    
    for (x, y, r) in spots:
        # Dark brown color in BGR: (40, 60, 90)
        cv2.circle(base_img, (x, y), r, (40, 60, 90), -1)
        # Add some blur to make it less sharp (like a real freckle)
        
    base_img = cv2.GaussianBlur(base_img, (5, 5), 0)
    
    # Image 1: just the base image
    cv2.imwrite(str(output_path / "photo1.jpg"), base_img)
    
    # Image 2: translated slightly to simulate a reshoot
    # Translation matrix: shift right by 20 pixels, down by 15 pixels
    M = np.float32([[1, 0, 20], [0, 1, 15]])
    img2 = cv2.warpAffine(base_img, M, (width, height), borderValue=(150, 180, 220))
    cv2.imwrite(str(output_path / "photo2.jpg"), img2)
    
    print(f"Generated 2 test images in {output_dir}")

if __name__ == "__main__":
    generate_test_images("test_images")
