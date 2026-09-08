from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import require_officer
from app.database import get_db
from app.models import Application, OfficerProfile, StudentProfile, Document, ExtractedField, AIFinding, AISummary

router = APIRouter(prefix="/api/officers", tags=["Officers"])

@router.get("/me")
def officer_me(current_user=Depends(require_officer), db: Session = Depends(get_db)):
    item = db.query(OfficerProfile).filter(OfficerProfile.user_id == current_user["user_id"]).first()
    if not item:
        raise HTTPException(status_code=404, detail="Officer profile not found")
    return item

@router.get("/applications")
def officer_applications(current_user=Depends(require_officer), db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.created_at.desc()).all()

@router.get("/applications/{application_id}")
def officer_application(application_id: int, current_user=Depends(require_officer), db: Session = Depends(get_db)):
    item = db.query(Application).filter(Application.id == application_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Application not found")
    profile = db.query(StudentProfile).filter(StudentProfile.id == item.student_profile_id).first()
    documents = db.query(Document).filter(Document.application_id == item.id).all()
    document_ids = [document.id for document in documents]
    fields = db.query(ExtractedField).filter(ExtractedField.document_id.in_(document_ids)).all() if document_ids else []
    return {"application": item, "student": profile, "documents": documents, "extracted_fields": fields,
            "findings": db.query(AIFinding).filter(AIFinding.application_id == item.id).all(),
            "summaries": db.query(AISummary).filter(AISummary.application_id == item.id).all()}
