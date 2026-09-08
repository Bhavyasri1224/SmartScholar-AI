from sqlalchemy.orm import Session

from app.models import Notification


def create_notification(db: Session, user_id: int, notification_type: str,
                         title: str, message: str, application_id: int | None = None):
    notification = Notification(
        user_id=user_id,
        application_id=application_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read="false",
    )
    db.add(notification)
    return notification
