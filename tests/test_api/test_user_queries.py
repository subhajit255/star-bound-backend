import io
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.models.notification import Notification
from app.models.user_query import UserQuery
from app.services.user_query_service import UserQueryService
from app.main import app
from app.api.deps import get_db, get_current_user


class TestUserQueryServiceAndRoutes(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(
            self.engine,
            tables=[Role.__table__, User.__table__, Notification.__table__, UserQuery.__table__]
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed roles
        self.admin_role = Role(id=1, name='Super Admin', slug='super-admin')
        self.user_role = Role(id=3, name='User', slug='user')
        self.db.add_all([self.admin_role, self.user_role])
        self.db.commit()

        # Seed users
        self.admin_user = User(id=1, name='Admin', email='admin@example.com', role_id=1)
        self.user1 = User(id=10, name='Alice', email='alice@example.com', role_id=3)
        self.user2 = User(id=20, name='Bob', email='bob@example.com', role_id=3)
        self.db.add_all([self.admin_user, self.user1, self.user2])
        self.db.commit()

        self.service = UserQueryService(db=self.db)
        self.current_mock_user = self.user1

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return self.current_mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_create_query_without_attachment(self):
        query = self.service.create_query(
            current_user=self.user1,
            subject="Cannot generate skymap",
            message="I uploaded my freckle photo but processing failed with an error."
        )
        self.assertIsNotNone(query.id)
        self.assertEqual(query.user_id, 10)
        self.assertEqual(query.subject, "Cannot generate skymap")
        self.assertEqual(query.status, 0)
        self.assertIsNone(query.file)

    def test_create_query_empty_subject_raises_error(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.create_query(
                current_user=self.user1,
                subject="",
                message="Sample message"
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_my_queries(self):
        self.service.create_query(self.user1, "Query 1", "Msg 1")
        self.service.create_query(self.user1, "Query 2", "Msg 2")
        self.service.create_query(self.user2, "Bob Query", "Bob Msg")

        alice_queries = self.service.get_my_queries(self.user1)
        self.assertEqual(len(alice_queries), 2)
        self.assertTrue(all(q.user_id == 10 for q in alice_queries))

    def test_get_query_by_id_authorization(self):
        q = self.service.create_query(self.user1, "Secret Query", "Confidential issue")

        # Author can view
        found = self.service.get_query_by_id(q.id, self.user1)
        self.assertEqual(found.id, q.id)

        # Admin can view
        admin_found = self.service.get_query_by_id(q.id, self.admin_user)
        self.assertEqual(admin_found.id, q.id)

        # Other regular user cannot view (403)
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_query_by_id(q.id, self.user2)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_reply_to_query_and_notification(self):
        q = self.service.create_query(self.user1, "Login Problem", "Cannot reset password")

        # Regular user cannot reply (403)
        with self.assertRaises(HTTPException) as ctx:
            self.service.reply_to_query(q.id, "Attempted reply", self.user2)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Admin replies
        replied_q = self.service.reply_to_query(
            query_id=q.id,
            reply_text="We have refreshed your password link. Please try again.",
            current_user=self.admin_user,
            new_status=1
        )
        self.assertEqual(replied_q.status, 1)
        self.assertEqual(replied_q.replied_by, 1)
        self.assertEqual(replied_q.reply, "We have refreshed your password link. Please try again.")

        # Verify an in-app notification was created for Alice (user_id=10)
        notif = self.db.query(Notification).filter(Notification.user_id == 10).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.redirection_foreign_id, q.id)
        self.assertEqual(notif.redirection_foreign_table, "user_queries")

    # --- HTTP API Route Tests ---
    def test_route_add_query_with_attachment(self):
        file_content = b"fake image content"
        res = self.client.post(
            "/api/v1/user-queries/",
            data={
                "subject": "App crash on startup",
                "message": "When opening camera view, the app immediately closes."
            },
            files={
                "attachment": ("error_log.png", io.BytesIO(file_content), "image/png")
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["subject"], "App crash on startup")
        self.assertEqual(data["status"], 0)
        self.assertEqual(data["statusText"], "Pending")
        self.assertIsNotNone(data["file"])
        self.assertTrue(data["file"].startswith("uploads/queries/"))
        self.assertTrue(data["fileUrl"].endswith(".png"))

        # Clean up created file
        created_file = Path(data["file"])
        if created_file.exists():
            created_file.unlink()

    def test_route_get_my_queries(self):
        self.client.post(
            "/api/v1/user-queries/",
            data={"subject": "Subscription charge issue", "message": "Charged twice."}
        )
        res = self.client.get("/api/v1/user-queries/me")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["subject"], "Subscription charge issue")

    def test_route_admin_reply_and_delete(self):
        # 1. User submits query
        add_res = self.client.post(
            "/api/v1/user-queries/",
            data={"subject": "How to export results?", "message": "Where is the PDF export button?"}
        )
        query_id = add_res.json()["id"]

        # 2. Admin replies
        self.current_mock_user = self.admin_user
        reply_res = self.client.post(
            f"/api/v1/user-queries/{query_id}/reply",
            json={"reply": "Go to Results > Share > Export PDF."}
        )
        self.assertEqual(reply_res.status_code, 200)
        self.assertEqual(reply_res.json()["status"], 1)
        self.assertEqual(reply_res.json()["statusText"], "Replied")
        self.assertEqual(reply_res.json()["reply"], "Go to Results > Share > Export PDF.")

        # 3. User deletes query
        self.current_mock_user = self.user1
        del_res = self.client.delete(f"/api/v1/user-queries/{query_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["id"], query_id)

