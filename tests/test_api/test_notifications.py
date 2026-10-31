import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.models.notification import Notification
from app.models.analysis_run import AnalysisRun
from app.models.upload import Upload
from app.models.match import Match
from app.services.notification_service import NotificationService
from app.main import app
from app.api.deps import get_db, get_current_user


class TestNotificationService(unittest.TestCase):
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
            Match.__table__,
            Notification.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=tables)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed roles
        role = Role(id=3, name='User', slug='user')
        self.db.add(role)
        self.db.commit()

        # Seed users
        self.user1 = User(id=1, name='User One', email='user1@example.com', role_id=3)
        self.user2 = User(id=2, name='User Two', email='user2@example.com', role_id=3)
        self.db.add_all([self.user1, self.user2])
        self.db.commit()

        # Seed uploads and analysis runs
        self.upload1 = Upload(
            id=10,
            user_id=1,
            file_name="freckle_10.jpg",
            file_path="uploads/analysis/user1/freckle_10.jpg"
        )
        self.upload2 = Upload(
            id=20,
            user_id=2,
            file_name="freckle_20.jpg",
            file_path="uploads/analysis/user2/freckle_20.jpg"
        )
        self.db.add_all([self.upload1, self.upload2])
        self.db.commit()

        self.analysis_run1 = AnalysisRun(
            id=100,
            upload_id=10,
            status="freckles_detected"
        )
        self.db.add(self.analysis_run1)
        self.db.commit()

        self.service = NotificationService(db=self.db)
        self.base_url = "http://testserver"

    def tearDown(self):
        self.db.close()

    def test_get_user_notifications_empty(self):
        res = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(res.total, 0)
        self.assertEqual(res.unread_count, 0)
        self.assertEqual(len(res.items), 0)

    def test_get_user_notifications_with_analysis_image(self):
        notif = Notification(
            id=1,
            user_id=1,
            title="Freckles Detected!",
            description="Your freckles have been identified.",
            type="freckle_detection_success",
            is_read=0,
            redirection_foreign_id=100,
            redirection_foreign_table="analysis_runs",
            created_at=datetime.now()
        )
        self.db.add(notif)
        self.db.commit()

        res = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(res.total, 1)
        self.assertEqual(res.unread_count, 1)
        self.assertEqual(len(res.items), 1)

        item = res.items[0]
        self.assertEqual(item.id, 1)
        self.assertEqual(item.is_read, 0)
        self.assertEqual(item.title, "Freckles Detected!")
        self.assertEqual(item.redirection_foreign_id, 100)
        self.assertEqual(item.redirection_foreign_table, "analysis_runs")
        # Verify image URL is correctly resolved from AnalysisRun -> Upload -> file_path
        expected_url = f"{self.base_url}/uploads/analysis/user1/freckle_10.jpg"
        self.assertEqual(item.image, expected_url)
        self.assertEqual(item.image_url, expected_url)

    def test_get_user_notifications_with_upload_image(self):
        notif = Notification(
            id=2,
            user_id=1,
            title="Upload Completed",
            description="Image uploaded.",
            type="upload_success",
            is_read=0,
            redirection_foreign_id=10,
            redirection_foreign_table="uploads",
            created_at=datetime.now()
        )
        self.db.add(notif)
        self.db.commit()

        res = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(res.total, 1)
        item = res.items[0]
        expected_url = f"{self.base_url}/uploads/analysis/user1/freckle_10.jpg"
        self.assertEqual(item.image, expected_url)

    def test_user_isolation(self):
        # User 1 notification
        n1 = Notification(id=1, user_id=1, title="User 1 Alert", is_read=0, created_at=datetime.now())
        # User 2 notification
        n2 = Notification(id=2, user_id=2, title="User 2 Alert", is_read=0, created_at=datetime.now())
        self.db.add_all([n1, n2])
        self.db.commit()

        # User 1 should only see their own notification
        res1 = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(res1.total, 1)
        self.assertEqual(res1.items[0].id, 1)

        # User 2 should only see their own notification
        res2 = self.service.getUserNotifications(currentUser=self.user2, base_url=self.base_url)
        self.assertEqual(res2.total, 1)
        self.assertEqual(res2.items[0].id, 2)

    def test_mark_as_read_success(self):
        notif = Notification(
            id=5,
            user_id=1,
            title="Unread Notice",
            description="Notice text",
            type="alert",
            is_read=0,
            redirection_foreign_id=100,
            redirection_foreign_table="analysis_runs",
            created_at=datetime.now()
        )
        self.db.add(notif)
        self.db.commit()

        # Verify unread before
        before = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(before.unread_count, 1)
        self.assertEqual(before.items[0].is_read, 0)

        # Mark as read
        updated = self.service.markAsRead(currentUser=self.user1, notification_id=5, base_url=self.base_url)
        self.assertEqual(updated.id, 5)
        self.assertEqual(updated.is_read, 1)
        self.assertIsNotNone(updated.image)

        # Verify unread after
        after = self.service.getUserNotifications(currentUser=self.user1, base_url=self.base_url)
        self.assertEqual(after.unread_count, 0)
        self.assertEqual(after.items[0].is_read, 1)

    def test_mark_as_read_forbidden_for_other_user(self):
        notif = Notification(
            id=6,
            user_id=2,
            title="User 2 Notification",
            is_read=0,
            created_at=datetime.now()
        )
        self.db.add(notif)
        self.db.commit()

        # User 1 attempts to mark User 2's notification as read
        with self.assertRaises(HTTPException) as ctx:
            self.service.markAsRead(currentUser=self.user1, notification_id=6)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_mark_as_read_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.markAsRead(currentUser=self.user1, notification_id=9999)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_mark_all_as_read(self):
        n1 = Notification(id=1, user_id=1, title="N1", is_read=0, created_at=datetime.now())
        n2 = Notification(id=2, user_id=1, title="N2", is_read=0, created_at=datetime.now())
        n3 = Notification(id=3, user_id=1, title="N3", is_read=1, created_at=datetime.now())
        self.db.add_all([n1, n2, n3])
        self.db.commit()

        res = self.service.markAllAsRead(currentUser=self.user1)
        self.assertEqual(res.marked_count, 2)

        after = self.service.getUserNotifications(currentUser=self.user1)
        self.assertEqual(after.unread_count, 0)
        for item in after.items:
            self.assertEqual(item.is_read, 1)


class TestNotificationApiRoutes(unittest.TestCase):
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
            Match.__table__,
            Notification.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=tables)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        role = Role(id=3, name='User', slug='user')
        self.db.add(role)
        self.db.commit()

        self.user = User(id=1, name='Alice', email='alice@test.com', role_id=3)
        self.user.role = role
        self.upload = Upload(id=1, user_id=1, file_name='img.jpg', file_path='uploads/analysis/alice/img.jpg')
        self.analysis_run = AnalysisRun(id=10, upload_id=1, status='freckles_detected')
        self.notification = Notification(
            id=1,
            user_id=1,
            title='Freckles Found!',
            description='Your freckles are mapped.',
            type='freckle_detection_success',
            is_read=0,
            redirection_foreign_id=10,
            redirection_foreign_table='analysis_runs',
            created_at=datetime.now()
        )
        self.db.add_all([self.user, self.upload, self.analysis_run, self.notification])
        self.db.commit()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_http_get_notifications(self):
        res = self.client.get('/api/v1/notifications/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['unreadCount'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertTrue(data['items'][0]['image'].endswith('uploads/analysis/alice/img.jpg'))

    def test_http_get_my_notifications_alias(self):
        res = self.client.get('/api/v1/notifications/me')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['total'], 1)

    def test_http_put_notification_read(self):
        res = self.client.put('/api/v1/notifications/1/read')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['isRead'], 1)
        self.assertTrue(data['image'].endswith('uploads/analysis/alice/img.jpg'))

        # Check list again, unread count should be 0
        list_res = self.client.get('/api/v1/notifications/')
        self.assertEqual(list_res.json()['unreadCount'], 0)
        self.assertEqual(list_res.json()['items'][0]['isRead'], 1)

    def test_http_put_read_all(self):
        res = self.client.put('/api/v1/notifications/read-all')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['markedCount'], 1)


if __name__ == '__main__':
    unittest.main()
