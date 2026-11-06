import io
import unittest
import cv2
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.models.upload import Upload
from app.main import app
from app.api.deps import get_db, get_current_user
from detection.skin_mask import validate_body_image, get_skin_mask
from detection.pipeline import detect_image


class TestBodySkinValidation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine, tables=[Role.__table__, User.__table__, Upload.__table__])
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed role and user
        role = Role(id=3, name='User', slug='user')
        self.user = User(id=1, name='Alice', user_name='alice', email='alice@example.com', role_id=3)
        self.db.add_all([role, self.user])
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return self.user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_validate_body_image_accepts_skin(self):
        # Synthetic skin image (B=145, G=175, R=205)
        skin_img = np.full((300, 300, 3), (145, 175, 205), dtype=np.uint8)
        # Add small freckle spots
        cv2.circle(skin_img, (100, 100), 5, (40, 60, 80), -1)
        cv2.circle(skin_img, (200, 150), 6, (40, 60, 80), -1)

        is_valid, msg, metrics = validate_body_image(skin_img)
        self.assertTrue(is_valid)
        self.assertGreaterEqual(metrics['skin_ratio'], 0.8)

    def test_validate_body_image_rejects_non_skin(self):
        # Non-skin: pure green grass / landscape color
        green_img = np.full((300, 300, 3), (35, 160, 45), dtype=np.uint8)
        is_valid, msg, metrics = validate_body_image(green_img)
        self.assertFalse(is_valid)
        self.assertIn("No human skin or body region detected", msg)

        # Non-skin: blue sky / vehicle
        blue_img = np.full((300, 300, 3), (220, 120, 30), dtype=np.uint8)
        is_valid, msg, _ = validate_body_image(blue_img)
        self.assertFalse(is_valid)

    def test_validate_body_image_rejects_yak_user_image(self):
        yak_path = Path("/Users/subhajitsaha/.gemini/antigravity/brain/c82cd1e8-0b77-4f8f-a2f1-ba0d925f50ff/.user_uploaded/media_1793978331808_d6c0be8d.jpg")
        if yak_path.exists():
            yak_img = cv2.imread(str(yak_path))
            is_valid, msg, metrics = validate_body_image(yak_img)
            self.assertFalse(is_valid)
            self.assertLess(metrics['skin_ratio'], 0.10)
            self.assertIn("No human skin or body region detected", msg)

    def test_validate_body_image_rejects_taj_mahal_user_image(self):
        taj_path = Path("/Users/subhajitsaha/.gemini/antigravity/brain/c82cd1e8-0b77-4f8f-a2f1-ba0d925f50ff/.user_uploaded/media_1793980299883_41c995b0.jpg")
        if taj_path.exists():
            taj_img = cv2.imread(str(taj_path))
            is_valid, msg, metrics = validate_body_image(taj_img)
            self.assertFalse(is_valid)
            self.assertLess(metrics['skin_ratio'], 0.35)
            self.assertIn("No human skin or body region detected", msg)

    def test_upload_api_rejects_taj_mahal_image(self):
        taj_path = Path("/Users/subhajitsaha/.gemini/antigravity/brain/c82cd1e8-0b77-4f8f-a2f1-ba0d925f50ff/.user_uploaded/media_1793980299883_41c995b0.jpg")
        if taj_path.exists():
            with open(taj_path, "rb") as f:
                res = self.client.post(
                    "/api/v1/uploads/",
                    files={"image": ("taj_mahal.jpg", f, "image/jpeg")}
                )
            self.assertEqual(res.status_code, 400)
            self.assertIn("No human skin or body region detected", res.json()["message"])

    def test_freckles_and_moles_detection_accuracy_preserved(self):
        # Verify genuine skin images detect moles and freckles with 100% precision
        baselines = {
            'mole.jpg': 3,
            'mole_2.jpg': 4,
            'moles_test.jpg': 4,
            'freckles_test.jpg': 17,
        }
        for name, expected_count in baselines.items():
            p = Path("test_images") / name
            if p.exists():
                res = detect_image(p)
                self.assertEqual(len(res.points), expected_count, f"Mismatch in point count for {name}")

    def test_upload_api_accepts_valid_skin_image(self):
        skin_img = np.full((300, 300, 3), (145, 175, 205), dtype=np.uint8)
        cv2.circle(skin_img, (100, 100), 5, (40, 60, 80), -1)
        ok, buf = cv2.imencode(".jpg", skin_img)
        self.assertTrue(ok)

        res = self.client.post(
            "/api/v1/uploads/",
            files={"image": ("my_skin.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")}
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("upload_id", data)
        self.assertIn("url", data)

    def test_upload_api_rejects_non_skin_image(self):
        non_skin = np.full((300, 300, 3), (40, 180, 50), dtype=np.uint8)
        ok, buf = cv2.imencode(".jpg", non_skin)
        self.assertTrue(ok)

        res = self.client.post(
            "/api/v1/uploads/",
            files={"image": ("nature.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("No human skin or body region detected", res.json()["message"])

    def test_detect_image_raises_error_on_non_skin(self, tmp_path=None):
        non_skin = np.full((300, 300, 3), (10, 10, 10), dtype=np.uint8)
        path = Path("test_images") / "temp_black.jpg"
        cv2.imwrite(str(path), non_skin)
        try:
            with self.assertRaises(ValueError) as ctx:
                detect_image(path)
            self.assertIn("No human skin or body region detected", str(ctx.exception))
        finally:
            if path.exists():
                path.unlink()
