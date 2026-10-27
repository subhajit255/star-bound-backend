from scripts.seed_roles import seed_roles
from scripts.seed_admin import seed_admin
from scripts.seed_subscriptions import seed_subscriptions

def seed_all():
    print("=== Running all seeders ===")
    print("\n--- 1. Seeding Roles ---")
    seed_roles()
    print("\n--- 2. Seeding Super Admin ---")
    seed_admin()
    print("\n--- 3. Seeding Subscriptions ---")
    seed_subscriptions()
    print("\n=== All seeders completed successfully ===")

if __name__ == "__main__":
    seed_all()

