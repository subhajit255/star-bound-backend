from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.subscription import SubscriptionCreate
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.post("/", status_code=status.HTTP_200_OK, summary="Create or Update subscription plan (Admin only)")
def create_or_update_subscription(
    subscription_in: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends()
):
    """
    Create or update a subscription plan:
    - If `id` is provided in the request body: searches for that ID and updates the subscription & Stripe details.
    - If `id` is NOT provided: creates a new Product & Price in Stripe and saves a new subscription plan in DB.
    - Requires Admin or Super-Admin privileges.
    """
    return subscription_service.createSubscription(
        currentUser=current_user,
        payload=subscription_in.model_dump(exclude_unset=True)
    )


@router.put("/{subscription_id}", status_code=status.HTTP_200_OK, summary="Update an existing subscription plan by ID (Admin only)")
def update_subscription(
    subscription_id: int,
    subscription_in: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends()
):
    """
    Update an existing subscription plan by path parameter ID.
    - Updates Product details (name, description, metadata) in Stripe
    - If price, currency, or interval changes, generates a new Stripe Price and archives the old one
    - Updates local database record
    - Requires Admin or Super-Admin privileges.
    """
    payload = subscription_in.model_dump(exclude_unset=True)
    payload["id"] = subscription_id
    return subscription_service.createSubscription(
        currentUser=current_user,
        payload=payload
    )


@router.get("/", status_code=status.HTTP_200_OK, summary="List all active subscription plans")
def get_subscriptions(
    subscription_service: SubscriptionService = Depends()
):
    """
    Get all active subscription plans for users to subscribe to.
    """
    return subscription_service.getSubscriptions()


@router.delete("/{subscription_id}", status_code=status.HTTP_200_OK, summary="Delete an existing subscription plan by ID (Admin only)")
def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends()
):
    """
    Delete a subscription plan by ID (Admin only).
    """
    return subscription_service.deleteSubscription(
        currentUser=current_user,
        subscription_id=subscription_id
    )
