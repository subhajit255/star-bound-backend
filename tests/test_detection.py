from pathlib import Path

import cv2
import numpy as np

from detection.pipeline import detect_image


def test_detector_returns_points_for_compact_dark_marks(tmp_path: Path):
    image = np.full((240, 320, 3), (145, 175, 205), dtype=np.uint8)
    cv2.circle(image, (100, 100), 7, (55, 75, 95), -1)
    cv2.circle(image, (220, 155), 10, (45, 65, 85), -1)
    path = tmp_path / "skin.jpg"
    assert cv2.imwrite(str(path), image)

    result = detect_image(path)

    assert result.width == 320
    assert result.height == 240
    assert result.points
    assert all(point.source == "auto" for point in result.points)
    assert all(0 <= point.score <= 1 for point in result.points)


def test_detector_rejects_unreadable_image(tmp_path: Path):
    path = tmp_path / "not-an-image.txt"
    path.write_text("not an image")

    try:
        detect_image(path)
    except ValueError as exc:
        assert "readable image" in str(exc)
    else:
        raise AssertionError("expected unreadable image to raise ValueError")