from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_officer
from app.database import get_db
from app.models import Application, Document

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/statistics")
def statistics(current_user=Depends(require_officer), db: Session = Depends(get_db)):
    statuses = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "NEEDS_CORRECTION", "APPROVED", "REJECTED"]
    result = {status.lower(): db.query(Application).filter(Application.status == status).count() for status in statuses}
    total = db.query(Application).count()
    result.update(total_applications=total,
                  average_documents_per_application=(db.query(func.count(Document.id)).scalar() / total if total else 0))
    result["ocr_success_count"] = db.query(Document).filter(Document.ocr_status == "COMPLETED").count()
    result["ocr_failure_count"] = db.query(Document).filter(Document.ocr_status == "FAILED").count()
    return result
