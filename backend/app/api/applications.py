from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.security import require_student
from app.database import get_db
from app.models import AIFinding, AISummary, Application, Document, ExtractedField, StudentProfile
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationUpdateRequest,
)
from app.services.audit_service import log_action
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/applications", tags=["Applications"])
EDITABLE_STATUSES = {"DRAFT", "NEEDS_CORRECTION"}


def student_profile(current_user, db: Session) -> StudentProfile:
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user["user_id"]
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return profile


def owned_application(application_id: int, current_user, db: Session) -> Application:
    profile = student_profile(current_user, db)
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.student_profile_id == profile.id,
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def application_number() -> str:
    return f"APP-{uuid4().hex[:12].upper()}"


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreateRequest, current_user=Depends(require_student), db: Session = Depends(get_db)):
    profile = student_profile(current_user, db)
    application = Application(
        student_profile_id=profile.id,
        application_number=application_number(),
        status="DRAFT",
        **{key: str(value) if isinstance(value, (bool, float)) else value
           for key, value in data.model_dump().items()},
    )
    db.add(application)
    log_action(db, current_user["user_id"], "application_created", "Application", None)
    db.commit()
    db.refresh(application)
    return application


@router.get("/", response_model=list[ApplicationResponse])
def list_applications(current_user=Depends(require_student), db: Session = Depends(get_db)):
    profile = student_profile(current_user, db)
    return db.query(Application).filter(
        Application.student_profile_id == profile.id
    ).order_by(Application.created_at.desc()).all()


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    return owned_application(application_id, current_user, db)


@router.put("/{application_id}", response_model=ApplicationResponse)
def update_application(application_id: int, data: ApplicationUpdateRequest,
                       current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user, db)
    if application.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Only draft or correction-requested applications can be edited")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(application, key, str(value) if isinstance(value, (bool, float)) else value)
    log_action(db, current_user["user_id"], "application_updated", "Application", application.id)
    db.commit()
    db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user, db)
    if application.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft applications can be deleted")
    db.delete(application)
    log_action(db, current_user["user_id"], "application_deleted", "Application", application.id)
    db.commit()


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
def update_application_status(application_id: int, status_value: str,
                               current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user, db)
    if status_value != "DRAFT" or application.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=403, detail="Students cannot set this application status")
    application.status = status_value
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/submit", response_model=ApplicationResponse)
def submit_application(application_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user, db)
    if application.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft applications can be submitted")
    required = [application.scheme_name, application.college_name, application.course_name]
    if any(value is None or str(value).strip() == "" for value in required):
        raise HTTPException(status_code=422, detail="Required application information is missing")
    application.status = "SUBMITTED"
    create_notification(db, current_user["user_id"], "APPLICATION_SUBMITTED", "Application submitted",
                        "Your scholarship application was submitted.", application.id)
    log_action(db, current_user["user_id"], "application_submitted", "Application", application.id)
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/analyze")
def analyze_application(application_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user, db)
    documents = db.query(Document).filter(Document.application_id == application.id).all()
    findings = []
    if not documents:
        findings.append(AIFinding(application_id=application.id, finding_type="MISSING_DOCUMENT",
                                  severity="HIGH", title="Documents missing",
                                  description="Upload the required scholarship documents.", confidence="1.0"))
    for document in documents:
        fields = db.query(ExtractedField).filter(ExtractedField.document_id == document.id).all()
        if document.ocr_status != "COMPLETED":
            findings.append(AIFinding(application_id=application.id, finding_type="LOW_CONFIDENCE",
                                      severity="MEDIUM", title="Document OCR incomplete",
                                      description=f"Document {document.id} was not processed successfully.",
                                      source_document_id=document.id, confidence="1.0"))
        if not fields:
            findings.append(AIFinding(application_id=application.id, finding_type="INVALID_DOCUMENT",
                                      severity="MEDIUM", title="No fields extracted",
                                      description=f"No structured fields were extracted from document {document.id}.",
                                      source_document_id=document.id, confidence="0.8"))
    db.query(AIFinding).filter(AIFinding.application_id == application.id).delete(synchronize_session=False)
    for finding in findings:
        db.add(finding)
    result = "NOT_ELIGIBLE" if any(item.severity == "HIGH" for item in findings) else ("REVIEW_REQUIRED" if findings else "ELIGIBLE")
    summary = AISummary(application_id=application.id,
                        summary_text="Rule-based document and application review completed.",
                        eligibility_result=result,
                        risk_level="HIGH" if result == "NOT_ELIGIBLE" else ("MEDIUM" if findings else "LOW"),
                        key_issues="; ".join(item.title for item in findings) or "No issues detected",
                        evidence_summary=f"Reviewed {len(documents)} document(s).")
    db.add(summary)
    log_action(db, current_user["user_id"], "application_analyzed", "Application", application.id)
    db.commit()
    return {"application_id": application.id, "eligibility_result": result,
            "risk_level": summary.risk_level, "findings": findings, "summary": summary}


