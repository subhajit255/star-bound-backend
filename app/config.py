from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl

class Settings(BaseSettings):
    PROJECT_NAME: str = "Stellaris API"
    API_V1_STR: str = "/v1"
    
    # MySQL Database connection string MUST come from .env
    DATABASE_URL: str
    ENVIRONMENT: str = "local"
    
    @property
    def BASE_URL(self) -> str:
        return "http://127.0.0.1:8000" if self.ENVIRONMENT == "local" else "https://uat.stellaris.com"
        
    # Storage settings
    STORAGE_KEY: str | None = None
    HYG_URL: str
    PROFILE_IMAGE_DIR: str = "uploads/profile"
    
    # JWT Settings
    SECRET_KEY: str = "kjopkp-dkxznjsdiu8833uhd8h8e9j9sc-sjcis9qjo0"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # Firebase Social Auth
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "secrets/star-bound-firebase-adminsdk.json"
    
    # Social Auth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    
    # Celery Settings
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    

settings = Settings()
