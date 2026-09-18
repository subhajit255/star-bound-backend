from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from skimage.feature import blob_dog


@dataclass(frozen=True)
class DetectedPoint:
    x: float
    y: float
    radius: float
    score: float
    source: str = "auto"


@dataclass(frozen=True)
class DetectionResult:
    width: int
    height: int
    points: list[DetectedPoint]
    stages: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "points": [asdict(point) for point in self.points],
            "stages": self.stages,
        }


def _read_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image")
    return image


def sanitize_image_bytes(content: bytes) -> tuple[bytes, str]:
    """Decode and re-encode an upload, stripping EXIF/GPS metadata."""
    encoded = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image")
    ok, output = cv2.imencode(
        ".jpg",
        image,
        [cv2.IMWRITE_JPEG_QUALITY, 95],
    )
    if not ok:
        raise ValueError("The image could not be processed")
    return output.tobytes(), "image/jpeg"


def _skin_mask(image: np.ndarray) -> np.ndarray:
    """Conservative YCrCb mask; false negatives are safer than background FPs."""
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0, 120, 60], dtype=np.uint8)
    upper = np.array([255, 190, 145], dtype=np.uint8)
    mask = cv2.inRange(ycrcb, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _remove_hair(image: np.ndarray) -> np.ndarray:
    """DullRazor implementation to remove hair."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (17, 17))
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    diff = cv2.absdiff(gray, closed)
    _, hair_mask = cv2.threshold(diff, 10, 255, cv2.THRESH_BINARY)
    return cv2.inpaint(image, hair_mask, inpaintRadius=2, flags=cv2.INPAINT_TELEA)


def _correct_illumination(channel: np.ndarray) -> np.ndarray:
    """Morphological black-hat to extract dark spots on bright skin."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
    return cv2.morphologyEx(channel, cv2.MORPH_BLACKHAT, kernel)


def detect_image(path: str | Path, *, max_points: int = 150, skip_nn: bool = False) -> DetectionResult:
    """Detect dark, compact candidate points from one image."""
    image = _read_image(path)
    height, width = image.shape[:2]
    
    # 1. Hair removal (DullRazor)
    image_no_hair = _remove_hair(image)
    
    # 2. Skin mask
    mask = _skin_mask(image_no_hair)

    # 3. Colour space (LAB L* and b*)
    lab = cv2.cvtColor(image_no_hair, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]
    
    # 4. Illumination correction (Morphological Black-Hat)
    # Extracts dark spots (freckles) from bright background (skin)
    signal = _correct_illumination(l_channel)
    signal[mask == 0] = 0

    # 5. Blob detection
    blobs = blob_dog(
        signal.astype(np.float32) / 255.0,
        min_sigma=2,
        max_sigma=min(24, max(4, min(width, height) / 16)),
        sigma_ratio=1.6,
        threshold=0.01, # Lowered from 0.02 to be more sensitive to lower-contrast freckles
        overlap=0.1,
    )

    # 6. Filtering
    points: list[DetectedPoint] = []
    for y, x, sigma in blobs:
        radius = float(sigma * np.sqrt(2))
        if radius < 2 or radius > min(width, height) * 0.04:
            continue
            
        xi, yi = int(round(x)), int(round(y))
        edge_margin = int(min(width, height) * 0.08)
        if not (edge_margin <= xi < width - edge_margin and edge_margin <= yi < height - edge_margin) or mask[yi, xi] == 0:
            continue
            
        # Extract local patch for filtering (clipping to image bounds)
        patch_size = int(radius * 2 + 2)
        r = patch_size // 2
        
        y1, y2 = max(0, yi - r), min(height, yi + r)
        x1, x2 = max(0, xi - r), min(width, xi + r)
        
        if y2 - y1 < 3 or x2 - x1 < 3: # Too small to analyze
            continue
            
        # Hue gate (Relaxed to allow reddish-brown freckles)
        # patch_hsv = cv2.cvtColor(image_no_hair[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        # mean_hue = np.median(patch_hsv[:,:,0])
        # if mean_hue < 5 or mean_hue > 170:
        #     continue
            
        # Shape metrics (Circularity and Convexity)
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
        
        # Reject non-circular or non-convex spots (like scars)
        if circularity < 0.2 or convexity < 0.5:
            continue
            
        local = signal[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3]
        score = float(np.clip(local.mean() / 255.0, 0.0, 1.0))
        
        # Only keep clearly visible, high-contrast spots
        if score >= 0.02: # Lowered from 0.05 to allow softer freckles
            points.append(DetectedPoint(float(x), float(y), radius, score))

    # Distance-based NMS to merge close double detections
    points.sort(key=lambda point: point.score, reverse=True)
    filtered_points = []
    for p in points:
        keep = True
        for fp in filtered_points:
            dist = np.sqrt((p.x - fp.x)**2 + (p.y - fp.y)**2)
            if dist < max(p.radius, fp.radius) * 1.5:
                keep = False
                break
        if keep:
            filtered_points.append(p)

    # 7. Learned rejection (CNN)
    final_points = []
    try:
        model_path = Path(__file__).parent.parent / "models" / "freckle_classifier.onnx"
        if not skip_nn and model_path.exists() and filtered_points:
            session = ort.InferenceSession(str(model_path))
            
            batch_crops = []
            
            for p in filtered_points:
                xi, yi = int(round(p.x)), int(round(p.y))
                r = 24 # 48x48 crop
                y1, y2 = max(0, yi - r), min(height, yi + r)
                x1, x2 = max(0, xi - r), min(width, xi + r)
                
                crop = image_no_hair[y1:y2, x1:x2]
                
                # Pad if near edge to ensure 48x48
                if crop.shape[0] < 48 or crop.shape[1] < 48:
                    pad_y = 48 - crop.shape[0]
                    pad_x = 48 - crop.shape[1]
                    crop = cv2.copyMakeBorder(crop, 0, pad_y, 0, pad_x, cv2.BORDER_CONSTANT, value=[0,0,0])
                    
                # Preprocess for MobileNetV3
                crop_float = crop.astype(np.float32) / 255.0
                crop_float = (crop_float - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
                crop_float = crop_float.astype(np.float32)
                crop_tensor = np.transpose(crop_float, (2, 0, 1)) # HWC to CHW
                
                batch_crops.append(crop_tensor)
                
            batch_tensor = np.stack(batch_crops)
            inputs = {session.get_inputs()[0].name: batch_tensor}
            outputs = session.run(None, inputs)[0]
            
            for i, out in enumerate(outputs):
                exp_out = np.exp(out - np.max(out))
                probs = exp_out / exp_out.sum()
                freckle_prob = float(probs[1])
                
                if freckle_prob > 0.2: # 20% confidence threshold (lowered from 40% to keep more valid freckles)
                    # You could also update the score here if desired
                    final_points.append(filtered_points[i])
        else:
            final_points = filtered_points
    except ImportError:
        # Fallback to classical pipeline if onnxruntime is not installed
        final_points = filtered_points

    return DetectionResult(width, height, final_points[:max_points], {"detector": 0.0})