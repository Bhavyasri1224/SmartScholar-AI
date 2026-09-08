from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.auth import StudentRegisterRequest, StudentLoginRequest
from app.database import get_db
from app.models import User, StudentProfile
from app.core.security import password_hash, create_access_token


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/register")
def register_student(
    data: StudentRegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user:
        return {
            "message": "Email already registered"
        }

    hashed_password = password_hash.hash(data.password)

    new_user = User(
        email=data.email,
        password_hash=hashed_password,
        role="STUDENT"
    )

    db.add(new_user)
    db.flush()

    new_student = StudentProfile(
        user_id=new_user.id,
        full_name=data.full_name,
        phone=data.phone
    )

    db.add(new_student)
    db.commit()

    db.refresh(new_user)
    db.refresh(new_student)

    return {
        "message": "Student registered successfully",
        "user_id": new_user.id,
        "student_profile_id": new_student.id,
        "email": new_user.email
    }

@router.post("/login")
def login_student(
    data: StudentLoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not password_hash.verify(data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token({
        "user_id": user.id,
        "role": user.role
    })

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": user.role
    }