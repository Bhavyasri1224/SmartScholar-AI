from fastapi import FastAPI
from app.api.auth import router as auth_router
from fastapi import Depends
from app.core.security import get_current_user
from app.api.applications import router as applications_router
from app.api.documents import router as documents_router

app = FastAPI(
    title="PM-USP Scholarship Processing System",
    version="1.0.0"
)


app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(documents_router)


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
