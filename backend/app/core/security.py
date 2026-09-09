from datetime import datetime, timedelta, timezone
from jose import jwt
from pwdlib import PasswordHash
import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
load_dotenv()

# Password hashing
password_hash = PasswordHash.recommended()


# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required")


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# JWT authentication
security = HTTPBearer(auto_error=False)

VALID_ROLES = {"STUDENT", "OFFICER"}


def authentication_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise authentication_error("Authentication credentials are required")

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

    except (jwt.JWTError, TypeError, ValueError):
        raise authentication_error("Invalid or expired token")

    user_id = payload.get("user_id")
    role = payload.get("role")
    if not isinstance(user_id, int) or user_id <= 0:
        raise authentication_error("Invalid token claims")
    if not isinstance(role, str) or role not in VALID_ROLES:
        raise authentication_error("Invalid token claims")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise authentication_error("User no longer exists")
    if user.role != role:
        raise authentication_error("Invalid token claims")

    return {"user_id": user.id, "role": user.role}


def require_role(role: str):
    def dependency(current_user=Depends(get_current_user)):
        if current_user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only {role.lower()} users can access this resource"
            )
        return current_user

    return dependency


require_student = require_role("STUDENT")
require_officer = require_role("OFFICER")
