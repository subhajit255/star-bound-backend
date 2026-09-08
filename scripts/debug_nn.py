import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort
from detection.pipeline import detect_image

def debug_nn(path: str):
    print(f"Detecting points on {path}")
    result = detect_image(path, skip_nn=True)
    points = result.points
    print(f"Found {len(points)} points before NN")
    
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    from detection.pipeline import _remove_hair
    image_no_hair = _remove_hair(image)
    height, width = image.shape[:2]
    
    model_path = Path("models/freckle_classifier.onnx")
    session = ort.InferenceSession(str(model_path))
    
    batch_crops = []
    for p in points:
        xi, yi = int(round(p.x)), int(round(p.y))
        r = 24
        y1, y2 = max(0, yi - r), min(height, yi + r)
        x1, x2 = max(0, xi - r), min(width, xi + r)
        crop = image_no_hair[y1:y2, x1:x2]
        if crop.shape[0] < 48 or crop.shape[1] < 48:
            pad_y = 48 - crop.shape[0]
            pad_x = 48 - crop.shape[1]
            crop = cv2.copyMakeBorder(crop, 0, pad_y, 0, pad_x, cv2.BORDER_CONSTANT, value=[0,0,0])
        crop_float = crop.astype(np.float32) / 255.0
        crop_float = (crop_float - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        crop_float = crop_float.astype(np.float32)
        crop_tensor = np.transpose(crop_float, (2, 0, 1))
        batch_crops.append(crop_tensor)
        
    batch_tensor = np.stack(batch_crops)
    inputs = {session.get_inputs()[0].name: batch_tensor}
    outputs = session.run(None, inputs)[0]
    
    for i, out in enumerate(outputs):
        exp_out = np.exp(out - np.max(out))
        probs = exp_out / exp_out.sum()
        freckle_prob = float(probs[1])
        print(f"Point {i} at ({points[i].x:.1f}, {points[i].y:.1f}): prob = {freckle_prob:.4f}")

if __name__ == "__main__":
    debug_nn("/Users/subhajitsaha/.gemini/antigravity-ide/brain/734ca4d8-7568-4b31-8ec2-02e2a60d23e2/.user_uploaded/media_1788378000691.jpg")
