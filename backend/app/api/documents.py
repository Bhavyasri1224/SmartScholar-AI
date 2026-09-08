from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
import shutil

from app.database import get_db
from app.models import Application, Document, StudentProfile
from app.core.security import get_current_user


router = APIRouter(
    prefix="/api/applications",
    tags=["Documents"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/{application_id}/documents")
def upload_document(
    application_id: int,
    document_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Only students can upload documents
    if current_user.get("role") != "STUDENT":
        raise HTTPException(
            status_code=403,
            detail="Only students can upload documents"
        )

    # Find student profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.get("user_id")
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found"
        )

    # Find application belonging to this student
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.student_profile_id == student_profile.id
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    # Allowed file types
    allowed_types = [
        "application/pdf",
        "image/jpeg",
        "image/png"
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG and PNG files are allowed"
        )

    # Create application-specific folder
    application_dir = UPLOAD_DIR / str(application_id)
    application_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = application_dir / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create document record
    new_document = Document(
        application_id=application.id,
        document_type=document_type,
        file_name=file.filename,
        file_path=str(file_path),
        mime_type=file.content_type,
        file_size=file_path.stat().st_size,
        ocr_status="PENDING",
        classification_status="PENDING"
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    return {
        "message": "Document uploaded successfully",
        "document_id": new_document.id,
        "application_id": application.id,
        "document_type": new_document.document_type,
        "file_name": new_document.file_name,
        "ocr_status": new_document.ocr_status,
        "classification_status": new_document.classification_status
    }