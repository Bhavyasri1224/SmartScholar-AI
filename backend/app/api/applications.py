import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.security import get_current_user, require_student
from app.database import get_db
from app.models import AIFinding, AISummary, Application, Document, ExtractedField, Scheme, StudentProfile
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationUpdateRequest,
)
from app.services.audit_service import log_action
from app.services.notification_service import create_notification
from app.services.analysis_service import (
    ANALYSIS_FINDING_TYPES,
    analyze_application as run_analysis,
    serialize_finding,
    serialize_summary,
)
from app.services.validation_service import validate_application_for_submission

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
    documents = db.query(Document).filter(
        Document.application_id == application.id
    ).all()
    scheme = None
    if application.scheme_id is not None:
        scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
    validation = validate_application_for_submission(application, documents, scheme)
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail=validation)
    application.status = "SUBMITTED"
    create_notification(db, current_user["user_id"], "APPLICATION_SUBMITTED", "Application submitted",
                        "Your scholarship application was submitted.", application.id)
    log_action(db, current_user["user_id"], "application_submitted", "Application", application.id)
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/analyze")
def analyze_application(application_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user["role"] == "STUDENT":
        application = owned_application(application_id, current_user, db)
    else:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

    documents = db.query(Document).filter(Document.application_id == application.id).all()
    document_ids = [document.id for document in documents]
    extracted_fields = []
    if document_ids:
        extracted_fields = db.query(ExtractedField).filter(
            ExtractedField.document_id.in_(document_ids)
        ).all()
    profile = db.query(StudentProfile).filter(
        StudentProfile.id == application.student_profile_id
    ).first()
    scheme = None
    if application.scheme_id is not None:
        scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
    result = run_analysis(application, profile, documents, extracted_fields, scheme)

    db.query(AIFinding).filter(
        AIFinding.application_id == application.id,
        AIFinding.finding_type.in_(ANALYSIS_FINDING_TYPES),
    ).delete(synchronize_session=False)
    for finding in result["findings"]:
        db.add(AIFinding(application_id=application.id, **finding))

    summary = db.query(AISummary).filter(
        AISummary.application_id == application.id
    ).order_by(AISummary.created_at.desc(), AISummary.id.desc()).first()
    if summary is None:
        summary = AISummary(application_id=application.id)
        db.add(summary)
    summary.summary_text = result["summary_text"]
    summary.eligibility_result = result["eligibility_result"]
    summary.risk_level = result["risk_level"]
    summary.key_issues = json.dumps(result["key_issues"])
    summary.evidence_summary = result["evidence_summary"]
    log_action(db, current_user["user_id"], "application_analyzed", "Application", application.id)
    db.commit()
    db.refresh(summary)
    saved_findings = db.query(AIFinding).filter(
        AIFinding.application_id == application.id,
        AIFinding.finding_type.in_(ANALYSIS_FINDING_TYPES),
    ).order_by(AIFinding.id.asc()).all()
    return {
        "application_id": application.id,
        "eligibility_result": result["eligibility_result"],
        "risk_level": result["risk_level"],
        "findings": [serialize_finding(finding) for finding in saved_findings],
        "summary": serialize_summary(summary),
        "recommendation": result["recommendation"],
        "eligibility": result["eligibility"],
        "completeness": result["completeness"],
    }


