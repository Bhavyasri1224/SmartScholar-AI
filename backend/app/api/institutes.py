from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Institute

router = APIRouter(prefix="/api/institutes", tags=["Institutes"])

@router.get("")
def list_institutes(state: str | None = None, district: str | None = None, search: str | None = Query(None), db: Session = Depends(get_db)):
    query = db.query(Institute)
    if state:
        query = query.filter(Institute.state == state)
    if district:
        query = query.filter(Institute.district == district)
    if search:
        query = query.filter(Institute.institute_name.ilike(f"%{search}%"))
    return query.all()

@router.get("/{institute_id}")
def get_institute(institute_id: int, db: Session = Depends(get_db)):
    item = db.query(Institute).filter(Institute.id == institute_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Institute not found")
    return item
