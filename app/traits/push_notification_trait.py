import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from firebase_admin import messaging
from app.services.firebase import initFirebase
from app.models.user import User
from app.models.notification import Notification

logger = logging.getLogger(__name__)


class PushNotificationTrait:
    """
    Push Notification Trait/Mixin providing Firebase Cloud Messaging (FCM)
    and unified database in-app notification dispatch.
    
    Can be used as a mixin for services or called statically.
    """

    @classmethod
    def send_push_notification(
        cls,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Sends an FCM push notification directly to a device token.
        Initializes Firebase automatically if not already initialized.
        """
        if not fcm_token or not str(fcm_token).strip():
            logger.info("[PushNotificationTrait] No FCM token provided; skipping push notification.")
            return None

        # Ensure Firebase Admin SDK is initialized
        initFirebase()

        try:
            # FCM requires all custom data key-value pairs to be strings
            serialized_data = {str(k): str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=serialized_data,
                token=str(fcm_token).strip()
            )
            response = messaging.send(message)
            logger.info(f"[PushNotificationTrait] Push notification sent successfully. Message ID: {response}")
            return response
        except Exception as e:
            logger.error(f"[PushNotificationTrait] Failed to send push notification to {fcm_token[:15]}...: {e}")
            return None

    @classmethod
    def notify_user(
        cls,
        db: Session,
        user_id: int,
        title: str,
        body: str,
        notification_type: str = "general",
        data: Optional[Dict[str, Any]] = None,
        redirection_id: Optional[int] = None,
        redirection_table: Optional[str] = None
    ) -> Optional[Notification]:
        """
        1. Persists an in-app notification in the MySQL `notifications` table.
        2. Dispatches an FCM push notification if the user has an `fcm_token`.
        """
        try:
            # 1. Create in-app notification record
            notif = Notification(
                user_id=user_id,
                title=title,
                description=body,
                type=notification_type,
                is_read=0,
                redirection_foreign_id=redirection_id,
                redirection_foreign_table=redirection_table
            )
            db.add(notif)
            db.commit()
            db.refresh(notif)

            # 2. Fetch user to retrieve fcm_token
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.fcm_token:
                push_data = dict(data or {})
                push_data.setdefault("notification_id", str(notif.id))
                push_data.setdefault("type", notification_type)
                if redirection_id is not None:
                    push_data.setdefault("redirection_id", str(redirection_id))
                if redirection_table is not None:
                    push_data.setdefault("redirection_table", str(redirection_table))

                cls.send_push_notification(
                    fcm_token=user.fcm_token,
                    title=title,
                    body=body,
                    data=push_data
                )
            else:
                logger.info(f"[PushNotificationTrait] User {user_id} has no registered fcm_token; in-app notification created only.")

            return notif
        except Exception as e:
            db.rollback()
            logger.error(f"[PushNotificationTrait] Failed to notify user {user_id}: {e}")
            return None

    # Aliases for camelCase convenience (matching project trait conventions)
    sendPushNotification = send_push_notification
    notifyUser = notify_user
