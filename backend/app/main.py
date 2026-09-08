from fastapi import FastAPI
from app.api.auth import router as auth_router
from fastapi import Depends
from app.core.security import get_current_user
from app.api.applications import router as applications_router
from app.api.documents import router as documents_router
from app.api.students import router as students_router
from app.api.officers import router as officers_router
from app.api.verification import router as verification_router
from app.api.notifications import router as notifications_router
from app.api.schemes import router as schemes_router
from app.api.institutes import router as institutes_router
from app.api.dashboard import router as dashboard_router

app = FastAPI(
    title="PM-USP Scholarship Processing System",
    version="1.0.0"
)


app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(documents_router)
app.include_router(students_router)
app.include_router(officers_router)
app.include_router(verification_router)
app.include_router(notifications_router)
app.include_router(schemes_router)
app.include_router(institutes_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "message": "PM-USP Scholarship API is running"
    }

@app.get("/api/test-protected")
def test_protected(current_user=Depends(get_current_user)):
    return {
        "message": "JWT authentication successful",
        "user": current_user
    }
