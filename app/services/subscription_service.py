from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends
from sqlalchemy import or_

from app.api.deps import get_db
from app.models.user import User
from app.models.role import Role
from app.models.subscription import Subscription
from app.traits.stripe_trait import StripeTrait
from app.schemas.subscription import slugify


class SubscriptionService(StripeTrait):
    def __init__(self, db: Session = Depends(get_db)):
        super().__init__()
        self.db = db

    def createSubscription(self, currentUser: User, payload: dict) -> dict:
        """
        Create or update a subscription plan.
        - If 'id' is present in payload: finds and updates the existing subscription & Stripe details.
        - If 'id' is NOT present: creates a new subscription in Stripe and stores it in the database.
        """
        # Check authorization: user must have super-admin or admin role
        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        if currentUser.role_id not in [r.id for r in admin_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage subscriptions"
            )

        sub_id = payload.get("id")
        name = payload.get("name")
        slug = payload.get("slug")
        price = payload.get("price")

        if (not slug or (isinstance(slug, str) and not slug.strip())) and name:
            slug = slugify(name)
            payload["slug"] = slug

        # ======================================================================
        # 1. UPDATE FLOW (When 'id' is passed)
        # ======================================================================
        if sub_id:
            subscription = self.db.query(Subscription).filter(Subscription.id == sub_id).first()
            if not subscription:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subscription with ID {sub_id} not found."
                )

            # Check slug uniqueness if slug is being updated
            if slug and slug != subscription.slug:
                existing_slug = self.db.query(Subscription).filter(
                    Subscription.slug == slug,
                    Subscription.id != sub_id
                ).first()
                if existing_slug:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A subscription with this slug already exists."
                    )
                subscription.slug = slug

            # Update Product details in Stripe
            if subscription.stripe_product_id:
                try:
                    metadata = {"slug": subscription.slug}
                    if payload.get("tagline"):
                        metadata["tagline"] = payload.get("tagline")

                    self.updateStripeProduct(
                        productId=subscription.stripe_product_id,
                        name=name or subscription.name,
                        description=payload.get("description", subscription.description),
                        metadata=metadata
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to update Stripe product: {str(e)}"
                    )

            # In Stripe, prices are immutable. If price or recurring interval changed, create a new price
            new_price = float(price) if price is not None else float(subscription.price or 0)
            new_currency = payload.get("currency") or subscription.currency or "usd"
            new_interval = payload.get("interval") or subscription.interval or "month"
            new_interval_count = int(payload.get("interval_count") or subscription.interval_count or 1)

            price_changed = (
                (price is not None and float(price) != float(subscription.price or 0)) or
                (payload.get("currency") and payload.get("currency") != subscription.currency) or
                (payload.get("interval") and payload.get("interval") != subscription.interval) or
                (payload.get("interval_count") and int(payload.get("interval_count")) != (subscription.interval_count or 1))
            )

            if price_changed and subscription.stripe_product_id:
                try:
                    new_stripe_price = self.createStripePrice(
                        name=name or subscription.name,
                        amount=new_price,
                        currency=new_currency,
                        interval=new_interval,
                        intervalCount=new_interval_count,
                        productId=subscription.stripe_product_id,
                        metadata={"slug": subscription.slug}
                    )
                    # Archive old price in Stripe
                    if subscription.stripe_price_id:
                        try:
                            self.archiveStripePrice(subscription.stripe_price_id)
                        except Exception:
                            pass
                    subscription.stripe_price_id = new_stripe_price.id
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to update Stripe price: {str(e)}"
                    )

            # Update database model fields
            if name is not None:
                subscription.name = name
            if payload.get("description") is not None:
                subscription.description = payload.get("description")
            if payload.get("features") is not None:
                subscription.features = payload.get("features")
            if price is not None:
                subscription.price = new_price
            if payload.get("currency") is not None:
                subscription.currency = new_currency
            if payload.get("interval") is not None:
                subscription.interval = new_interval
            if payload.get("interval_count") is not None:
                subscription.interval_count = new_interval_count
            if payload.get("status") is not None:
                subscription.status = payload.get("status")
            if payload.get("is_default") is not None:
                subscription.is_default = payload.get("is_default")

            self.db.commit()
            self.db.refresh(subscription)

            return {
                "message": "Subscription updated successfully",
                "subscription": subscription
            }

        # ======================================================================
        # 2. CREATE FLOW (When 'id' is NOT passed)
        # ======================================================================
        if not name or not slug or price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name, slug, and price are required fields to create a subscription."
            )

        existing_sub = self.db.query(Subscription).filter(Subscription.slug == slug).first()
        if existing_sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A subscription with this slug already exists."
            )

        # Create Product in Stripe
        metadata = {"slug": slug}
        if payload.get("tagline"):
            metadata["tagline"] = payload.get("tagline")

        try:
            stripe_product = self.createStripeProduct(
                name=name,
                description=payload.get("description"),
                metadata=metadata
            )
            stripe_product_id = stripe_product.id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create product in Stripe: {str(e)}"
            )

        # Create Price in Stripe
        currency = payload.get("currency", "usd")
        interval = payload.get("interval", "month")
        interval_count = int(payload.get("interval_count") or 1)

        try:
            stripe_price = self.createStripePrice(
                name=name,
                amount=float(price),
                currency=currency,
                interval=interval,
                intervalCount=interval_count,
                productId=stripe_product_id,
                metadata={"slug": slug}
            )
            stripe_price_id = stripe_price.id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create price in Stripe: {str(e)}"
            )

        new_subscription = Subscription(
            name=name,
            slug=slug,
            description=payload.get("description"),
            features=payload.get("features"),
            price=price,
            currency=currency,
            interval=interval,
            interval_count=interval_count,
            status=payload.get("status", 1),
            is_default=payload.get("is_default", False),
            stripe_product_id=stripe_product_id,
            stripe_price_id=stripe_price_id
        )

        self.db.add(new_subscription)
        self.db.commit()
        self.db.refresh(new_subscription)

        return {
            "message": "Subscription created successfully",
            "subscription": new_subscription
        }

    def getSubscriptions(self) -> dict:
        subscriptions = self.db.query(Subscription).filter(
            Subscription.status == 1,
            Subscription.deleted_at == None
        ).all()
        return {
            "subscriptions": subscriptions
        }
    def deleteSubscription(self, currentUser: User, subscription_id: int) -> dict:
        """
        Delete (soft-delete) a subscription plan (Admin only).
        """
        admin_roles = self.db.query(Role).filter(
            or_(Role.slug == "super-admin", Role.slug == "admin")
        ).all()
        if currentUser.role_id not in [r.id for r in admin_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete subscriptions"
            )

        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.deleted_at == None
        ).first()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )

        if subscription.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the default starter plan"
            )

        if subscription.stripe_product_id:
            try:
                import stripe
                stripe.Product.modify(subscription.stripe_product_id, active=False)
            except Exception as e:
                print(f"Stripe product archive warning: {e}")

        from datetime import datetime, timezone
        subscription.deleted_at = datetime.now(timezone.utc)
        subscription.status = 0
        self.db.commit()

        return {
            "message": "Subscription plan deleted successfully",
            "id": subscription_id
        }
