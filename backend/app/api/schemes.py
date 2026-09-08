from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Scheme

router = APIRouter(prefix="/api/schemes", tags=["Schemes"])

@router.get("")
def list_schemes(db: Session = Depends(get_db)):
    return db.query(Scheme).filter(Scheme.is_active == "true").all()

@router.get("/{scheme_id}")
def get_scheme(scheme_id: int, db: Session = Depends(get_db)):
    item = db.query(Scheme).filter(Scheme.id == scheme_id, Scheme.is_active == "true").first()
    if not item:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return item
