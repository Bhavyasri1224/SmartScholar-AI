import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import require_student
from app.database import get_db
from app.models import Application, Document, ExtractedField, StudentProfile
from app.services.audit_service import log_action
from app.services.classification_service import classify_document
from app.services.extraction_service import extract_document_fields
from app.services.ocr_service import extract_document_text

router = APIRouter(tags=["Documents"])
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def owned_application(application_id, user_id, db):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.student_profile_id == (profile.id if profile else -1),
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def document_response(document):
    return {
        "id": document.id,
        "application_id": document.application_id,
        "document_type": document.document_type,
        "file_name": document.file_name,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "page_count": document.page_count,
        "ocr_status": document.ocr_status,
        "classification_status": document.classification_status,
        "uploaded_at": document.uploaded_at,
    }


@router.post("/api/applications/{application_id}/documents", status_code=status.HTTP_201_CREATED)
def upload_document(application_id: int, document_type: str, file: UploadFile = File(...),
                    current_user=Depends(require_student), db: Session = Depends(get_db)):
    application = owned_application(application_id, current_user["user_id"], db)
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF, JPG, JPEG and PNG files are allowed")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="File extension is not allowed")
    content = file.file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit")
    folder = UPLOAD_DIR / str(application.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{secrets.token_hex(16)}{suffix}"
    try:
        path.write_bytes(content)
        document = Document(application_id=application.id, document_type=document_type.upper(),
                            file_name=path.name, file_path=str(path), mime_type=file.content_type,
                            file_size=len(content), ocr_status="PENDING", classification_status="PENDING")
        db.add(document)
        log_action(db, current_user["user_id"], "document_uploaded", "Document", None)
        db.commit()
        db.refresh(document)
        return document_response(document)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Unable to store document")


@router.get("/api/applications/{application_id}/documents")
def list_documents(application_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    owned_application(application_id, current_user["user_id"], db)
    return [document_response(item) for item in db.query(Document).filter(Document.application_id == application_id).all()]


@router.get("/api/documents/{document_id}")
def get_document(document_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    document = db.query(Document).join(Application).join(StudentProfile).filter(
        Document.id == document_id, StudentProfile.user_id == current_user["user_id"]
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_response(document)


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    document = db.query(Document).join(Application).join(StudentProfile).filter(
        Document.id == document_id, StudentProfile.user_id == current_user["user_id"]
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    Path(document.file_path).unlink(missing_ok=True)
    log_action(db, current_user["user_id"], "document_deleted", "Document", document.id)
    db.delete(document)
    db.commit()


@router.post("/api/documents/{document_id}/process")
def process_document(document_id: int, current_user=Depends(require_student), db: Session = Depends(get_db)):
    document = db.query(Document).join(Application).join(StudentProfile).filter(
        Document.id == document_id, StudentProfile.user_id == current_user["user_id"]
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.ocr_status == "COMPLETED" and document.classification_status == "COMPLETED":
        return document_response(document)
    try:
        result = extract_document_text(document.file_path, document.mime_type)
        document.page_count = result["page_count"]
        document.ocr_status = result["status"]
        document.document_type = classify_document(result["text"])
        document.classification_status = "COMPLETED"
        for field in db.query(ExtractedField).filter(ExtractedField.document_id == document.id).all():
            db.delete(field)
        for item in extract_document_fields(result["text"], document.document_type):
            db.add(ExtractedField(document_id=document.id, field_name=item["field_name"],
                                   field_value=item["field_value"], confidence=item["confidence"],
                                   page_number=item.get("page_number", 1)))
        log_action(db, current_user["user_id"], "document_processed", "Document", document.id)
        db.commit()
        db.refresh(document)
        return {**document_response(document), "text": result["text"]}
    except Exception as exc:
        db.rollback()
        document.ocr_status = "FAILED"
        document.classification_status = "FAILED"
        db.commit()
        raise HTTPException(status_code=422, detail=f"Document processing failed: {exc}")
