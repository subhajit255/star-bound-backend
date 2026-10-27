import os
import firebase_admin
from firebase_admin import credentials
from app.config import settings

_firebase_app = None

def initFirebase():
    """Call this once at app startup or before using Firebase services."""
    global _firebase_app
    if not firebase_admin._apps:
        try:
            cert_path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
            if not os.path.isabs(cert_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidate = os.path.join(base_dir, cert_path)
                if os.path.exists(candidate):
                    cert_path = candidate

            if os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                _firebase_app = firebase_admin.initialize_app(cred)
                print("Firebase initialized successfully")
            else:
                print(f"Firebase service account file not found at: {cert_path}")
        except Exception as e:
            print("Failed to initialize Firebase: ", e)
    else:
        _firebase_app = firebase_admin.get_app()

    return _firebase_app