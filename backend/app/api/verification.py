from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import require_officer
from app.database import get_db
from app.models import Application, VerificationAction, StudentProfile
from app.services.audit_service import log_action
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/applications", tags=["Verification"])
class VerificationRequest(BaseModel):
    level: str = "APPLICATION"
    action: str
    remarks: str | None = None

@router.post("/{application_id}/verification")
def verify(application_id: int, data: VerificationRequest, current_user=Depends(require_officer), db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    statuses = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_CORRECTION": "NEEDS_CORRECTION", "VERIFY": "UNDER_REVIEW"}
    if data.action not in statuses:
        raise HTTPException(status_code=400, detail="Unsupported verification action")
    action = VerificationAction(application_id=application.id, officer_id=current_user["user_id"], level=data.level, action=data.action, remarks=data.remarks)
    application.status = statuses[data.action]
    student = db.query(StudentProfile).filter(StudentProfile.id == application.student_profile_id).first()
    db.add(action)
    if student:
        create_notification(db, student.user_id, data.action, "Application status updated", f"Your application is {application.status.lower()}.", application.id)
    log_action(db, current_user["user_id"], "verification", "Application", application.id, {"action": data.action})
    db.commit()
    return {"application_id": application.id, "status": application.status, "action": data.action}

@router.get("/{application_id}/verification")
def verification_history(application_id: int, current_user=Depends(require_officer), db: Session = Depends(get_db)):
    return db.query(VerificationAction).filter(VerificationAction.application_id == application_id).order_by(VerificationAction.created_at.desc()).all()
