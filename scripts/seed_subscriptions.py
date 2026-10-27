from app.db import SessionLocal
from app.models.subscription import Subscription
from app.schemas.subscription import slugify

SUBSCRIPTIONS = [
    {
        "name": "Free",
        "price": 0.00,
        "currency": "usd",
        "interval": "month",
        "interval_count": 1,
        "description": "Discover your personal constellation through your freckle patterns with basic scanning and constellation viewing.",
        "features": "Limited constellation scans,View generated constellations,Basic constellation details",
        "status": 1,
        "is_default": True,
    }
]

def seed_subscriptions():
    db = SessionLocal()
    try:
        for plan_data in SUBSCRIPTIONS:
            name = plan_data["name"]
            # Auto-generate slug from name if not provided
            slug = plan_data.get("slug") or slugify(name)

            existing = db.query(Subscription).filter(Subscription.slug == slug).first()
            if not existing:
                sub = Subscription(
                    name=name,
                    slug=slug,
                    price=plan_data.get("price", 0.00),
                    currency=plan_data.get("currency", "usd"),
                    interval=plan_data.get("interval", "month"),
                    interval_count=plan_data.get("interval_count", 1),
                    description=plan_data.get("description"),
                    features=plan_data.get("features"),
                    status=plan_data.get("status", 1),
                    is_default=plan_data.get("is_default", False),
                )
                db.add(sub)
                print(f"Added subscription plan: {name} (slug: {slug})")
            else:
                existing.name = name
                existing.price = plan_data.get("price", 0.00)
                existing.currency = plan_data.get("currency", "usd")
                existing.interval = plan_data.get("interval", "month")
                existing.interval_count = plan_data.get("interval_count", 1)
                existing.description = plan_data.get("description")
                existing.features = plan_data.get("features")
                existing.status = plan_data.get("status", 1)
                existing.is_default = plan_data.get("is_default", False)
                print(f"Subscription plan already exists. Updated: {name} (slug: {slug})")

        db.commit()
        print("Subscriptions seeded successfully.")
    except Exception as e:
        print(f"Error seeding subscriptions: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting subscription seeder...")
    seed_subscriptions()
