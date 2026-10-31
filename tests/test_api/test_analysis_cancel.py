import unittest
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.models.upload import Upload
from app.models.analysis_run import AnalysisRun
from app.models.detection import Detection
from app.models.point_set import PointSet
from app.models.match import Match
from app.models.notification import Notification
from app.main import app
from app.api.deps import get_db, get_current_user
from workers.tasks.analysis_tasks import process_detection_job


class TestAnalysisCancel(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        tables = [
            Role.__table__,
            User.__table__,
            Upload.__table__,
            AnalysisRun.__table__,
            Detection.__table__,
            PointSet.__table__,
            Match.__table__,
            Notification.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=tables)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Seed roles
        role = Role(id=3, name='User', slug='user')
        self.db.add(role)
        self.db.commit()

        # Seed users
        self.user1 = User(id=1, name='User One', email='user1@example.com', role_id=3)
        self.user2 = User(id=2, name='User Two', email='user2@example.com', role_id=3)
        self.db.add_all([self.user1, self.user2])
        self.db.commit()

        # Create dummy file on disk for user1
        self.test_file_dir = Path("uploads/analysis/test_cancel")
        self.test_file_dir.mkdir(parents=True, exist_ok=True)
        self.test_file = self.test_file_dir / "sample_test.jpg"
        self.test_file.write_bytes(b"dummy image bytes")

        # Create dummy star pattern file
        self.test_svg_dir = Path("uploads/star-pattern")
        self.test_svg_dir.mkdir(parents=True, exist_ok=True)
        self.test_svg = self.test_svg_dir / "sample_test.svg"
        self.test_svg.write_text("<svg></svg>")

        # Seed upload
        self.upload1 = Upload(
            id=10,
            user_id=1,
            file_name="sample_test.jpg",
            file_path=str(self.test_file)
        )
        self.db.add(self.upload1)
        self.db.commit()

        # Seed analysis run
        self.analysis1 = AnalysisRun(
            id=100,
            upload_id=10,
            status="detecting_freckles"
        )
        self.db.add(self.analysis1)
        self.db.commit()

        # Seed detections & point sets & matches & notifications
        self.detection = Detection(id=1, upload_id=10, x=10.0, y=20.0, radius=2.0, score=0.9, source="auto")
        self.point_set = PointSet(id=1, upload_id=10, n_points=1, bbox="0,0,100,100")
        self.match = Match(id=1, upload_id=10, rank=1, ra=10.0, dec=20.0, roll=0.0, scale=1.0, parity=1, n_matched=1)
        self.notif = Notification(
            id=1,
            user_id=1,
            title="Freckles Detected!",
            description="Found freckles.",
            type="freckle_detection_success",
            is_read=0,
            redirection_foreign_id=100,
            redirection_foreign_table="analysis_runs",
            created_at=datetime.now()
        )
        self.db.add_all([self.detection, self.point_set, self.match, self.notif])
        self.db.commit()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user1
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        # Clean up files if still present
        if self.test_file.exists():
            self.test_file.unlink(missing_ok=True)
        if self.test_svg.exists():
            self.test_svg.unlink(missing_ok=True)

    def test_cancel_analysis_success(self):
        # User cancels their analysis
        res = self.client.post('/api/v1/analyses/100/cancel')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'cancelled')
        self.assertEqual(data['analysisId'], 100)
        self.assertEqual(data['uploadId'], 10)

        # Verify DB rows are removed
        self.assertIsNone(self.db.query(AnalysisRun).filter_by(id=100).first())
        self.assertIsNone(self.db.query(Upload).filter_by(id=10).first())
        self.assertEqual(self.db.query(Detection).filter_by(upload_id=10).count(), 0)
        self.assertEqual(self.db.query(PointSet).filter_by(upload_id=10).count(), 0)
        self.assertEqual(self.db.query(Match).filter_by(upload_id=10).count(), 0)
        self.assertEqual(self.db.query(Notification).filter_by(redirection_foreign_id=100).count(), 0)

        # Verify file is deleted from disk
        self.assertFalse(self.test_file.exists())
        self.assertFalse(self.test_svg.exists())

    def test_cancel_analysis_via_delete_method(self):
        # Re-create test file
        self.test_file.write_bytes(b"dummy image bytes")

        res = self.client.delete('/api/v1/analyses/100')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'cancelled')
        self.assertIsNone(self.db.query(AnalysisRun).filter_by(id=100).first())

    def test_cancel_analysis_forbidden_for_other_user(self):
        # Switch current user to user2
        app.dependency_overrides[get_current_user] = lambda: self.user2

        res = self.client.post('/api/v1/analyses/100/cancel')
        self.assertEqual(res.status_code, 403)
        # Ensure row was NOT deleted
        self.assertIsNotNone(self.db.query(AnalysisRun).filter_by(id=100).first())

    def test_cancel_analysis_not_found(self):
        res = self.client.post('/api/v1/analyses/99999/cancel')
        self.assertEqual(res.status_code, 404)


if __name__ == '__main__':
    unittest.main()

