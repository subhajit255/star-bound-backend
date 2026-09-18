import firebase_admin
from firebase_admin import credentials
from app.config import settings

_firebase_app = None

def initFirebase():
    """Call this once at app startup (from main.py's startup/lifespan event)."""
    global _firebase_app
    if _firebase_app is None:
        try:
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
            _firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully")
        except Exception as e:
            print("Failed to initialize Firebase: ", e)