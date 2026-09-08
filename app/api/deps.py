from typing import Generator
from sqlalchemy.orm import Session, joinedload
from app.db import SessionLocal
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.config import settings
from app.models.user import User

def get_db() -> Generator:
    """
    FastAPI dependency that yields a database session 
    and ensures it is closed after the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# This tells FastAPI to use standard Bearer token auth in Swagger UI
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    # Fetch the user from the DB, eagerly loading the role
    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
        
    return user
