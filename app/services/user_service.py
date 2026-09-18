from app.schemas.user import UserResponse
from app.schemas.user import RoleResponse
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import now
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status, Depends, UploadFile
import os
import shutil
import time
import random
import httpx
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.api.deps import get_db
from app.models.user import User
from app.models.role import Role
from app.services.security import get_password_hash, create_access_token, verify_password
from app.config import settings

class UserService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def register(self, payload: dict) -> dict:
        email = payload.get("email")
        password = payload.get("password")
        name = payload.get("name")
        # phone = payload.get("phone")
        # phone_code = payload.get("phoneCode")

        if not email or not password or not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="missing required fields."
            )

        # 1. Check for duplicate email
        userByEmail = self.db.query(User).filter(User.email == email).first()
        if userByEmail:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists."
            )
            
        # 2. Extract base username from email
        baseUsername = email.split("@")[0]
        
        # 3. Hash the password before saving!
        hashedPassword = get_password_hash(password)
        # find user role from roles table
        role = self.db.query(Role).filter(Role.slug == "user").first()
        if(not role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User role not found."
            )
        roleId = role.id    
        # 4. Build the User SQLAlchemy model and insert into DB
        newUser = User(
            role_id = roleId,
            name=name,
            email=email,
            user_name=baseUsername,
            password=hashedPassword,  # Store the HASH, never the plaintext password
            verified_at = now()
        )
        
        self.db.add(newUser)
        self.db.commit()
        self.db.refresh(newUser)
        newUser.role = role
        # Generate JWT token with all required user data
        tokenData = {
            "id": newUser.id,
            "name": newUser.name,
            "email": newUser.email,
            "phone": newUser.phone,
            "phone_code": newUser.phone_code,
            "role": newUser.role.slug,
        }
        accessToken = create_access_token(data=tokenData)

        return {
            "user": newUser,
            "access_token": accessToken,
            "token_type": "bearer"
        }

    def login(self, payload: dict) -> dict:
        email = payload.get("email")
        password = payload.get("password")

        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required for login."
            )

        # 1. Fetch user by email
        user = self.db.query(User).filter(User.email == email).options(joinedload(User.role)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        # 2. Verify password
        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        # 3. Generate JWT token
        tokenData = {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
        accessToken = create_access_token(data=tokenData)

        return {
            "user": user,
            "access_token": accessToken,
            "token_type": "bearer"
        }

    def updateProfile(self, currentUser: User, payload: dict, profile_image: UploadFile | None = None) -> User:
        name = payload.get("name")
        phone = payload.get("phone")
        phoneCode = payload.get("phone_code")

        if name:
            currentUser.name = name
        if phone:
            currentUser.phone = phone
        if phoneCode:
            currentUser.phone_code = phoneCode
            
        if profile_image:
            # Create uploads directory if it doesn't exist
            upload_dir = settings.PROFILE_IMAGE_DIR
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate a unique file name to avoid collisions
            file_extension = profile_image.filename.split(".")[-1]
            file_name = f"user_{currentUser.id}_{int(time.time())}.{file_extension}"
            file_path = os.path.join(upload_dir, file_name)
            
            # Save the uploaded file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(profile_image.file, buffer)
                
            # Update the user record with the new path
            currentUser.profile_image = file_name
            
        self.db.commit()
        self.db.refresh(currentUser)
        return currentUser

    def forgetPasswordOtp(self, payload: dict) -> dict:
        email = payload.get("email")
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email Id"
            )

        # generate OTP
        otp = random.randint(100000, 999999)
        
        # update OTP into user table
        user.verification_code = otp
        self.db.commit()
        self.db.refresh(user)

        return {
            "message": "OTP sent successfully",
            "otp": otp
        }  

    def resetPassword(self, payload: dict) -> dict:
        email = payload.get("email")
        otp = payload.get("otp")
        password = payload.get("password")

        # check user exists
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email Id"
            )

        # check if OTP is correct
        if user.verification_code != otp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP"
            )

        # reset password
        user.password = get_password_hash(password)
        self.db.commit()
        self.db.refresh(user)

        return {
            "message": "Password reset successfully"
        }

    def socialLogin(self, payload: dict) -> dict:
        # Note: 'token' should now be the Firebase ID Token from the client
        token = payload.get("token")
        
        email = None
        name = None
        provider_id = None
        provider = None
        
        try:
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(token)
            
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            provider_id = decoded_token.get("uid")
            
            # Identify which provider the user used to sign into Firebase
            firebase_info = decoded_token.get("firebase", {})
            sign_in_provider = firebase_info.get("sign_in_provider")
            
            if sign_in_provider == "google.com":
                provider = "google"
            elif sign_in_provider == "apple.com":
                provider = "apple"
            elif sign_in_provider == "facebook.com":
                provider = "facebook"
            else:
                provider = payload.get("provider", "firebase")
                
            if not email:
                raise ValueError("Could not extract email from Firebase token")
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Firebase token: {str(e)}"
            )

        user = self.db.query(User).filter(User.email == email).first()
        
        if not user:
            base_username = email.split("@")[0]
            
            user = User(
                role_id=3,
                name=name,
                email=email,
                user_name=base_username,
                password=None,
                auth_provider=provider,
                provider_id=provider_id,
                is_verified=True,
                verified_at=now()
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        else:
            if user.auth_provider == "email":
                user.auth_provider = provider
                user.provider_id = provider_id
                user.is_verified = True
                if not user.verified_at:
                    user.verified_at = now()
                self.db.commit()
                self.db.refresh(user)

        token_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
        access_token = create_access_token(data=token_data)

        return {
            "user": user,
            "access_token": access_token,
            "token_type": "bearer"
        }

    def getRole(self) -> list[RoleResponse]:
        roles = self.db.query(Role).all()
        roleResponse = []
        for role in roles:
            roleResponse.append(RoleResponse.model_validate(role, from_attributes=True))
        return roleResponse

    def getUsers(self, currentUser: User, page: int = 1, size: int = 10) -> dict:
        # check the token for admin user 
        adminRoles = self.db.query(Role).filter(or_(Role.slug == "super-admin", Role.slug == "admin")).all()
        if currentUser.role_id not in [r.id for r in adminRoles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        # find all users except the admin users 
        query = self.db.query(User).filter(User.role_id.notin_([r.id for r in adminRoles]))
        
        total = query.count()
        users = query.offset((page - 1) * size).limit(size).all()
        
        userResponse = []
        for user in users:
            userResponse.append(UserResponse.model_validate(user, from_attributes=True))
            
        total_pages = (total + size - 1) // size
            
        return {
            "items": userResponse,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages
        }
        