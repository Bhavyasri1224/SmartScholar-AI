from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_student
from app.database import get_db
from app.models import StudentProfile
from app.schemas.student import StudentProfileResponse, StudentProfileUpdate

router = APIRouter(prefix="/api/students", tags=["Students"])


def get_profile(current_user, db: Session) -> StudentProfile:
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user["user_id"]
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return profile


@router.get("/me", response_model=StudentProfileResponse)
def get_student_profile(current_user=Depends(require_student), db: Session = Depends(get_db)):
    return get_profile(current_user, db)


@router.get("/me/profile", response_model=StudentProfileResponse)
def get_student_profile_alias(current_user=Depends(require_student), db: Session = Depends(get_db)):
    return get_profile(current_user, db)


@router.put("/me/profile", response_model=StudentProfileResponse)
def update_student_profile(
    data: StudentProfileUpdate,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    profile = get_profile(current_user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
