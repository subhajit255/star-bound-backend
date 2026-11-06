from __future__ import annotations
import cv2
import numpy as np


def get_skin_mask(image: np.ndarray) -> np.ndarray:
    """
    Computes a robust human skin mask using consensus across RGB, HSV, and YCrCb color spaces.
    Accommodates all Fitzpatrick skin phototypes (I to VI) under diverse indoor/outdoor lighting.
    """
    # 1. Normalized RGB Rule
    B = image[:, :, 0].astype(int)
    G = image[:, :, 1].astype(int)
    R = image[:, :, 2].astype(int)
    # Human skin: Red component dominates, with distinct red-green chrominance gap
    rgb_skin = (R > G) & (G > B) & ((R - G) > 10) & (R > 50) & (B < 175)

    # 2. HSV Rule
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    # Hue: [0, 25] and [170, 180] covers human skin undertones (pinkish to deep brown)
    hsv_skin = ((H <= 25) | (H >= 170)) & (S >= 20) & (S <= 210) & (V >= 40)

    # 3. YCrCb Rule
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = ycrcb[:, :, 0], ycrcb[:, :, 1], ycrcb[:, :, 2]
    ycrcb_skin = (Y >= 40) & (Cr >= 133) & (Cr <= 180) & (Cb >= 80) & (Cb <= 135)

    # Multi-space consensus: pixel must satisfy at least 2 of the 3 color models
    skin_consensus = (rgb_skin.astype(int) + hsv_skin.astype(int) + ycrcb_skin.astype(int)) >= 2
    skin_mask_u8 = (skin_consensus * 255).astype(np.uint8)

    # Morphological opening and closing to eliminate noise and seal contiguous body patches
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    opened = cv2.morphologyEx(skin_mask_u8, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    # Fill internal holes so dark moles and prominent freckles inside skin are preserved in mask
    contours, _ = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(closed)
    for i in range(len(contours)):
        cv2.drawContours(filled, contours, i, 255, -1)
    return filled


def validate_body_image(image: np.ndarray) -> tuple[bool, str, dict]:
    """
    Validates whether an uploaded image contains a human body / skin region suitable for freckle analysis.

    Rejects:
    - Animals (yak, cattle, cats, dogs, wildlife, birds)
    - Landscapes, nature, scenery, foliage, stones, water
    - Non-body objects, vehicles, food, documents
    - High-frequency fur or clutter textures

    Returns:
        (is_valid: bool, error_message: str, metrics: dict)
    """
    if image is None or image.size == 0:
        return False, "The uploaded image is empty or could not be decoded.", {}

    height, width = image.shape[:2]
    total_pixels = height * width

    # Check minimum resolution
    if width < 150 or height < 150:
        return False, "Image resolution is too low. Please upload a clear photo of your skin.", {}

    # 1. Skin coverage calculation
    skin_mask = get_skin_mask(image)
    skin_pixel_count = int(np.count_nonzero(skin_mask))
    skin_ratio = float(skin_pixel_count) / float(total_pixels)

    # Rule 1: Minimum total skin coverage
    # Real body/skin uploads in Star Bound typically have 80-100% skin.
    # We require at least 25% to allow for partial clothing / background.
    if skin_ratio < 0.25:
        return (
            False,
            f"No human skin or body region detected (detected skin coverage was {skin_ratio * 100:.1f}%). "
            "Please upload a clear photo of your skin or body.",
            {"skin_ratio": round(skin_ratio, 4)}
        )

    # Rule 2: Contiguous skin patch check (Connected Components)
    # Natural body photos have large contiguous skin areas (arms, back, face).
    # Scattered background false positives (soil, leaves) only form small fragmented clusters.
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(skin_mask)
    largest_patch_ratio = 0.0
    if num_labels > 1:
        largest_patch_area = int(np.max(stats[1:, cv2.CC_STAT_AREA]))
        largest_patch_ratio = float(largest_patch_area) / float(total_pixels)

    if largest_patch_ratio < 0.15:
        return (
            False,
            f"Detected skin area is too fragmented or far away (largest patch was {largest_patch_ratio * 100:.1f}%). "
            "Please take a closer photo focusing on your skin.",
            {"skin_ratio": round(skin_ratio, 4), "largest_patch_ratio": round(largest_patch_ratio, 4)}
        )

    # Rule 3: Texture and edge density check (Animal fur, foliage, stones, fabric)
    # Human skin is smooth tissue with isolated freckles.
    # Animal fur (like a yak or dog) and outdoor scenery have high-frequency edge transitions everywhere.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / float(total_pixels)

    if edge_density > 0.20:
        return (
            False,
            "The image contains excessive high-frequency texture or clutter (such as animal fur, foliage, or stones). "
            "Please upload a clear photo of your skin.",
            {"skin_ratio": round(skin_ratio, 4), "edge_density": round(edge_density, 4)}
        )

    metrics = {
        "skin_ratio": round(skin_ratio, 4),
        "largest_patch_ratio": round(largest_patch_ratio, 4),
        "edge_density": round(edge_density, 4)
    }
    return True, "Valid human skin/body image", metrics

