from app.db import SessionLocal
from app.models.role import Role

def seed_roles():
    db = SessionLocal()
    try:
        roles = [
            Role(id=1, name="Super Admin", slug="super-admin"),
            Role(id=2, name="Admin", slug="admin"),
            Role(id=3, name="User", slug="user")
        ]
        
        for role in roles:
            existing = db.query(Role).filter(Role.id == role.id).first()
            if not existing:
                db.add(role)
                print(f"Added role: {role.name}")
            else:
                print(f"Role already exists: {role.name}")
                
        db.commit()
        print("Roles seeded successfully.")
    except Exception as e:
        print(f"Error seeding roles: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting seeder...")
    seed_roles()
