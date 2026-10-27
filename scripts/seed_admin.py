from datetime import datetime, timezone
from app.db import SessionLocal
from app.models.user import User
from app.models.role import Role
from app.services.security import get_password_hash

def seed_admin():
    db = SessionLocal()
    try:
        # Fetch super-admin role
        super_admin_role = db.query(Role).filter(Role.slug == "super-admin").first()
        if not super_admin_role:
            print("Super Admin role not found. Please run seed_roles.py first.")
            return

        email = "super.admin@starbound.com"
        existing = db.query(User).filter(User.email == email).first()

        hashed_password = get_password_hash("secret")

        if not existing:
            admin_user = User(
                role_id=super_admin_role.id,
                name="Super Admin",
                user_name="superadmin",
                email=email,
                password=hashed_password,
                auth_provider="email",
                is_active=True,
                is_verified=True,
                verified_at=datetime.now(timezone.utc),
            )
            db.add(admin_user)
            db.commit()
            print(f"Super admin user created successfully: {email}")
        else:
            existing.role_id = super_admin_role.id
            existing.password = hashed_password
            existing.is_active = True
            existing.is_verified = True
            db.commit()
            print(f"Super admin user already exists. Updated role & password for: {email}")

    except Exception as e:
        print(f"Error seeding admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting admin seeder...")
    seed_admin()
