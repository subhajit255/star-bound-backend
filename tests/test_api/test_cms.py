import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.models.cms import Cms
from app.schemas.cms import CmsCreate, CmsUpdate
from app.services.cms_service import CmsService
from app.main import app
from app.api.deps import get_db, get_current_user


class TestCmsServiceAndRoutes(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine, tables=[Role.__table__, User.__table__, Cms.__table__])
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed roles
        self.admin_role = Role(id=1, name='Super Admin', slug='super-admin')
        self.user_role = Role(id=3, name='User', slug='user')
        self.db.add_all([self.admin_role, self.user_role])
        self.db.commit()

        # Seed admin and regular users
        self.admin_user = User(id=1, name='Admin', email='admin@example.com', role_id=1)
        self.regular_user = User(id=2, name='Regular', email='regular@example.com', role_id=3)
        self.db.add_all([self.admin_user, self.regular_user])
        self.db.commit()

        self.service = CmsService(db=self.db)

        # Setup TestClient with dependency overrides
        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return self.admin_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_create_cms_auto_slug(self):
        cms = self.service.create_cms(
            payload=CmsCreate(
                title="Terms & Conditions",
                description="<p>Our terms of service.</p>",
                meta_title="Terms of Service",
                meta_keywords="terms, legal"
            ),
            current_user=self.admin_user
        )
        self.assertIsNotNone(cms.id)
        self.assertEqual(cms.slug, "terms-conditions")
        self.assertEqual(cms.title, "Terms & Conditions")
        self.assertTrue(cms.status)

    def test_create_cms_explicit_slug(self):
        cms = self.service.create_cms(
            payload=CmsCreate(
                title="Privacy Policy",
                slug="privacy-policy-2026",
                description="Privacy details."
            ),
            current_user=self.admin_user
        )
        self.assertEqual(cms.slug, "privacy-policy-2026")

    def test_create_cms_duplicate_slug_raises_error(self):
        self.service.create_cms(
            payload=CmsCreate(title="About Us", slug="about-us"),
            current_user=self.admin_user
        )
        with self.assertRaises(HTTPException) as ctx:
            self.service.create_cms(
                payload=CmsCreate(title="Another About Us", slug="about-us"),
                current_user=self.admin_user
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_cms(self):
        cms = self.service.create_cms(
            payload=CmsCreate(title="Refund Policy", description="Initial refund info"),
            current_user=self.admin_user
        )
        updated = self.service.update_cms(
            cms_id=cms.id,
            payload=CmsUpdate(description="Updated refund info", meta_description="Refund page"),
            current_user=self.admin_user
        )
        self.assertEqual(updated.description, "Updated refund info")
        self.assertEqual(updated.meta_description, "Refund page")
        self.assertEqual(updated.title, "Refund Policy")  # unchanged

    def test_update_cms_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_cms(
                cms_id=999,
                payload=CmsUpdate(title="Non-existent"),
                current_user=self.admin_user
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_cms_list(self):
        self.service.create_cms(CmsCreate(title="Page 1", status=True), current_user=self.admin_user)
        self.service.create_cms(CmsCreate(title="Page 2", status=False), current_user=self.admin_user)

        all_pages = self.service.get_cms_list()
        self.assertEqual(len(all_pages), 2)

        active_pages = self.service.get_cms_list(status=True)
        self.assertEqual(len(active_pages), 1)
        self.assertEqual(active_pages[0].title, "Page 1")

    def test_get_cms_by_identifier(self):
        cms = self.service.create_cms(
            CmsCreate(title="Contact Us", slug="contact-us"),
            current_user=self.admin_user
        )
        by_slug = self.service.get_cms_by_identifier("contact-us")
        self.assertEqual(by_slug.id, cms.id)

        by_id = self.service.get_cms_by_identifier(str(cms.id))
        self.assertEqual(by_id.slug, "contact-us")

    def test_delete_cms(self):
        cms = self.service.create_cms(
            CmsCreate(title="Temporary Page", slug="temp-page"),
            current_user=self.admin_user
        )
        res = self.service.delete_cms(cms_id=cms.id, current_user=self.admin_user)
        self.assertEqual(res["id"], cms.id)
        self.assertIsNone(self.db.query(Cms).filter(Cms.id == cms.id).first())

    # --- API Route HTTP Tests ---
    def test_route_create_cms(self):
        res = self.client.post(
            "/api/v1/cms/",
            json={"title": "Community Guidelines", "description": "Be respectful."}
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["slug"], "community-guidelines")
        self.assertEqual(data["title"], "Community Guidelines")

    def test_route_list_cms(self):
        self.client.post("/api/v1/cms/", json={"title": "Page A"})
        self.client.post("/api/v1/cms/", json={"title": "Page B"})

        res = self.client.get("/api/v1/cms/")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 2)

    def test_route_get_cms(self):
        create_res = self.client.post("/api/v1/cms/", json={"title": "FAQ Page", "slug": "faq"})
        self.assertEqual(create_res.status_code, 201)

        # Get by slug
        res = self.client.get("/api/v1/cms/faq")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["title"], "FAQ Page")

    def test_route_update_cms(self):
        create_res = self.client.post("/api/v1/cms/", json={"title": "Changelog", "slug": "changelog"})
        cms_id = create_res.json()["id"]

        update_res = self.client.put(
            f"/api/v1/cms/{cms_id}",
            json={"metaDescription": "Latest product releases."}
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["metaDescription"], "Latest product releases.")

    def test_route_delete_cms(self):
        create_res = self.client.post("/api/v1/cms/", json={"title": "Old Page", "slug": "old-page"})
        cms_id = create_res.json()["id"]

        del_res = self.client.delete(f"/api/v1/cms/{cms_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["id"], cms_id)

        # Verify 404 after delete
        get_res = self.client.get(f"/api/v1/cms/{cms_id}")
        self.assertEqual(get_res.status_code, 404)

