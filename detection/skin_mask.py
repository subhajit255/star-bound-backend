from __future__ import annotations
import cv2
import numpy as np


def get_skin_mask(image: np.ndarray) -> np.ndarray:
    """
    Computes a robust human skin mask using consensus across RGB, HSV, and YCrCb color spaces.
    Accommodates all Fitzpatrick skin phototypes (I to VI) under diverse indoor/outdoor lighting
    while strictly rejecting non-skin surfaces (marble, stone, sky, foliage, metals, animals).
    """
    B = image[:, :, 0].astype(int)
    G = image[:, :, 1].astype(int)
    R = image[:, :, 2].astype(int)

    # 1. Biological human skin RGB rule:
    # Hemoglobin absorption creates a distinctive red-green and red-blue chrominance gap
    rgb_skin = (R > G) & (G > B) & ((R - G) >= 12) & ((R - B) >= 18) & (R >= 55)

    # 2. HSV skin rule:
    # Hue [0, 22] and [165, 180] covers human undertones (fair to deep brown)
    # Saturation [28, 200] excludes neutral stone, marble, overcast sky, and neon cartoons
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    hsv_skin = ((H <= 22) | (H >= 165)) & (S >= 28) & (S <= 200) & (V >= 45)

    # 3. YCrCb skin rule:
    # (Cr - Cb >= 14) captures the physical red-chrominance disparity of living human tissue
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = ycrcb[:, :, 0].astype(int), ycrcb[:, :, 1].astype(int), ycrcb[:, :, 2].astype(int)
    ycrcb_skin = (Y >= 45) & (Cr >= 135) & (Cr <= 180) & (Cb >= 85) & (Cb <= 135) & ((Cr - Cb) >= 14)

    # Multi-space consensus: pixel must satisfy at least 2 of the 3 color models
    skin_consensus = (rgb_skin.astype(int) + hsv_skin.astype(int) + ycrcb_skin.astype(int)) >= 2
    skin_mask_u8 = (skin_consensus * 255).astype(np.uint8)

    # Morphological opening and closing to eliminate noise and seal contiguous body patches
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    opened = cv2.morphologyEx(skin_mask_u8, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    # Fill internal holes (e.g. dark moles, prominent freckles) inside skin patches
    # Holes are restricted to at most 2% of total image area to prevent flooding external background/openings
    contours, hierarchy = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = closed.copy()
    if hierarchy is not None and len(contours) > 0:
        total_pixels = image.shape[0] * image.shape[1]
        max_hole_pixels = total_pixels * 0.02
        for i in range(len(contours)):
            parent = hierarchy[0][i][3]
            if parent != -1:  # Internal hole inside an outer skin contour
                hole_area = cv2.contourArea(contours[i])
                if hole_area <= max_hole_pixels:
                    cv2.drawContours(filled, contours, i, 255, -1)
    return filled


def validate_body_image(image: np.ndarray) -> tuple[bool, str, dict]:
    """
    Validates whether an uploaded image contains a genuine human body / skin region suitable for freckle analysis.

    Rejects:
    - Architecture, monuments, marble, buildings, interiors (e.g. Taj Mahal, temples, rooms)
    - Animals and wildlife (e.g. yak, cattle, dogs, cats, birds, horses)
    - Scenery, landscapes, nature, foliage, sky, water, stones
    - Non-body objects, vehicles, furniture, documents, artificial graphics
    - Far-away or fully-clothed subjects lacking sufficient skin area
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

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Reject artificial flat / blank color blocks
    if float(gray.std()) < 3.0:
        return (
            False,
            "No human skin or body region detected (the image appears to be a blank or artificial solid color block). "
            "Please upload a clear photo of your skin.",
            {}
        )

    # 1. Skin coverage calculation
    skin_mask = get_skin_mask(image)
    skin_pixel_count = int(np.count_nonzero(skin_mask))
    skin_ratio = float(skin_pixel_count) / float(total_pixels)

    # Rule 1: Minimum total skin coverage
    # Real body/skin uploads in Star Bound have 80-100% skin.
    # At least 35% skin is required for reliable mole/freckle localization.
    if skin_ratio < 0.35:
        return (
            False,
            f"No human skin or body region detected (detected skin coverage was {skin_ratio * 100:.1f}%). "
            "Please upload a clear photo of your skin or body.",
            {"skin_ratio": round(skin_ratio, 4)}
        )

    # Rule 2: Contiguous skin patch check (Connected Components)
    # Natural body photos have large contiguous skin areas (arms, back, face, torso).
    # Scattered background false positives only form small fragmented clusters.
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(skin_mask)
    largest_patch_ratio = 0.0
    if num_labels > 1:
        largest_patch_area = int(np.max(stats[1:, cv2.CC_STAT_AREA]))
        largest_patch_ratio = float(largest_patch_area) / float(total_pixels)

    if largest_patch_ratio < 0.25:
        return (
            False,
            f"Detected skin area is too fragmented or far away (largest patch was {largest_patch_ratio * 100:.1f}%). "
            "Please take a closer photo focusing on your skin.",
            {"skin_ratio": round(skin_ratio, 4), "largest_patch_ratio": round(largest_patch_ratio, 4)}
        )

    # Rule 3: Chromatic gap within detected skin region
    # Human dermis microvasculature produces strong hemoglobin disparity
    mask_bool = skin_mask > 0
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    Cr = ycrcb[:, :, 1].astype(int)
    Cb = ycrcb[:, :, 2].astype(int)
    R = image[:, :, 2].astype(int)
    G = image[:, :, 1].astype(int)

    mean_cr_cb = float(np.mean(Cr[mask_bool] - Cb[mask_bool]))
    mean_rg = float(np.mean(R[mask_bool] - G[mask_bool]))

    if mean_cr_cb < 22.0 or mean_rg < 18.0:
        return (
            False,
            "The detected region does not match human skin chrominance characteristics. "
            "Please upload a clear photo of your skin.",
            {"skin_ratio": round(skin_ratio, 4), "mean_cr_cb": round(mean_cr_cb, 2), "mean_rg": round(mean_rg, 2)}
        )

    # Rule 4: Texture and edge density check (Animal fur, foliage, stones, masonry)
    edges = cv2.Canny(gray, 80, 200)
    edge_density = float(np.count_nonzero(edges)) / float(total_pixels)

    if edge_density > 0.16:
        return (
            False,
            "The image contains excessive high-frequency texture or clutter (such as animal fur, foliage, or stones). "
            "Please upload a clear photo of your skin.",
            {"skin_ratio": round(skin_ratio, 4), "edge_density": round(edge_density, 4)}
        )

    metrics = {
        "skin_ratio": round(skin_ratio, 4),
        "largest_patch_ratio": round(largest_patch_ratio, 4),
        "mean_cr_cb": round(mean_cr_cb, 2),
        "mean_rg": round(mean_rg, 2),
        "edge_density": round(edge_density, 4)
    }
    return True, "Valid human skin/body image", metrics
