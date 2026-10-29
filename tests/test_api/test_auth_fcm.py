import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserLogin, SocialLoginRequest
from app.services.user_service import UserService

class TestFcmTokenAuth(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine, tables=[Role.__table__, User.__table__])
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        # Seed user role
        role = Role(id=3, name='User', slug='user')
        self.db.add(role)
        self.db.commit()

        self.service = UserService(db=self.db)
        # Mock stripe methods so test doesn't need external Stripe keys
        self.service.createCustomer = MagicMock(return_value=MagicMock(id='cus_test123'))
        self.service.getAccountId = MagicMock(return_value='acct_test123')

    def tearDown(self):
        self.db.close()

    def test_register_with_fcm_token_snake_case(self):
        req = UserCreate(name='Alice', email='alice@example.com', password='password123', fcm_token='token_snake_123')
        payload = req.model_dump(by_alias=True)
        res = self.service.register(payload)
        user = self.db.query(User).filter_by(email='alice@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.fcm_token, 'token_snake_123')
        self.assertEqual(res['user'].fcm_token, 'token_snake_123')

    def test_register_with_fcm_token_camel_case(self):
        req = UserCreate.model_validate({'name': 'Bob', 'email': 'bob@example.com', 'password': 'password123', 'fcmToken': 'token_camel_456'})
        payload = req.model_dump(by_alias=True)
        res = self.service.register(payload)
        user = self.db.query(User).filter_by(email='bob@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.fcm_token, 'token_camel_456')

    def test_register_without_fcm_token(self):
        req = UserCreate(name='Dave', email='dave@example.com', password='password123')
        payload = req.model_dump(by_alias=True)
        res = self.service.register(payload)
        user = self.db.query(User).filter_by(email='dave@example.com').first()
        self.assertIsNotNone(user)
        self.assertIsNone(user.fcm_token)

    def test_login_updates_fcm_token(self):
        # Register user first
        req = UserCreate(name='Charlie', email='charlie@example.com', password='password123', fcm_token='initial_token')
        self.service.register(req.model_dump(by_alias=True))
        
        # Login with new token
        login_req = UserLogin(email='charlie@example.com', password='password123', fcm_token='updated_login_token')
        res = self.service.login(login_req.model_dump(by_alias=True))
        
        user = self.db.query(User).filter_by(email='charlie@example.com').first()
        self.assertEqual(user.fcm_token, 'updated_login_token')
        self.assertEqual(res['user'].fcm_token, 'updated_login_token')

    @patch('firebase_admin.auth.verify_id_token')
    def test_social_login_new_user_with_fcm_token(self, mock_verify):
        mock_verify.return_value = {
            'email': 'social_new@example.com',
            'name': 'Social User',
            'uid': 'google_uid_123',
            'firebase': {'sign_in_provider': 'google.com'}
        }
        
        req = SocialLoginRequest(token='mock_fb_token', fcm_token='social_device_token_789')
        res = self.service.socialLogin(req.model_dump(by_alias=True))
        
        user = self.db.query(User).filter_by(email='social_new@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.fcm_token, 'social_device_token_789')
        self.assertEqual(res['user'].fcm_token, 'social_device_token_789')

    @patch('firebase_admin.auth.verify_id_token')
    def test_social_login_existing_user_updates_fcm_token(self, mock_verify):
        # Create user first
        req = UserCreate(name='Existing', email='existing@example.com', password='password123', fcm_token='old_token')
        self.service.register(req.model_dump(by_alias=True))
        
        mock_verify.return_value = {
            'email': 'existing@example.com',
            'name': 'Existing',
            'uid': 'google_uid_456',
            'firebase': {'sign_in_provider': 'google.com'}
        }
        
        login_req = SocialLoginRequest(token='mock_fb_token', fcm_token='new_social_device_token')
        res = self.service.socialLogin(login_req.model_dump(by_alias=True))
        
        user = self.db.query(User).filter_by(email='existing@example.com').first()
        self.assertEqual(user.fcm_token, 'new_social_device_token')
        self.assertEqual(res['user'].fcm_token, 'new_social_device_token')

    def test_update_fcm_token_method(self):
        req = UserCreate(name='Eve', email='eve@example.com', password='password123')
        self.service.register(req.model_dump(by_alias=True))
        user = self.db.query(User).filter_by(email='eve@example.com').first()
        
        updated_user = self.service.updateFcmToken(currentUser=user, fcm_token='direct_fcm_update')
        self.assertEqual(updated_user.fcm_token, 'direct_fcm_update')

if __name__ == '__main__':
    unittest.main()

