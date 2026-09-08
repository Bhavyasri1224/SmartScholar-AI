from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.database import get_db
from app.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.get("")
def list_notifications(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Notification).filter(Notification.user_id == current_user["user_id"]).order_by(Notification.created_at.desc()).all()

@router.patch("/{notification_id}/read")
def mark_read(notification_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user["user_id"]).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.is_read = "true"
    db.commit()
    db.refresh(item)
    return item
