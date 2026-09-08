from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, StudentProfile
from app.schemas.application import ApplicationCreateRequest
from app.core.security import get_current_user


router = APIRouter(
    prefix="/api/applications",
    tags=["Applications"]
)


@router.post("/")
def create_application(
    data: ApplicationCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Make sure the logged-in user is a student
    if current_user.get("role") != "STUDENT":
        raise HTTPException(
            status_code=403,
            detail="Only students can create applications"
        )

    # Find the student's profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.get("user_id")
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found"
        )

    # Create application
    new_application = Application(
        student_profile_id=student_profile.id,
        application_number=f"APP-{student_profile.id}-{db.query(Application).count() + 1}",
        scheme_name=data.scheme_name,
        college_name=data.college_name,
        board=data.board,
        class_12_year=data.class_12_year,
        stream=data.stream,
        marks_percentage=data.marks_percentage,
        course_name=data.course_name,
        course_type=data.course_type,
        admission_year=data.admission_year,
        annual_family_income=data.annual_family_income,
        other_scholarship=data.other_scholarship,
        regular_course=data.regular_course,
        is_diploma=data.is_diploma,
        drop_after_class_12=data.drop_after_class_12,
        status="DRAFT"
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return {
        "message": "Application created successfully",
        "application_id": new_application.id,
        "application_number": new_application.application_number,
        "status": new_application.status
    }

@router.get("/{application_id}")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user["user_id"]
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found"
        )

    application = db.query(Application).filter(
        Application.id == application_id,
        Application.student_profile_id == student_profile.id
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return {
        "application_id": application.id,
        "application_number": application.application_number,
        "scheme_name": application.scheme_name,
        "college_name": application.college_name,
        "board": application.board,
        "class_12_year": application.class_12_year,
        "stream": application.stream,
        "marks_percentage": application.marks_percentage,
        "course_name": application.course_name,
        "course_type": application.course_type,
        "admission_year": application.admission_year,
        "annual_family_income": application.annual_family_income,
        "other_scholarship": application.other_scholarship,
        "regular_course": application.regular_course,
        "is_diploma": application.is_diploma,
        "drop_after_class_12": application.drop_after_class_12,
        "status": application.status
    }