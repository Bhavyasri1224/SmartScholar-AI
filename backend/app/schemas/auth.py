from pydantic import BaseModel, EmailStr


class StudentRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str


class StudentLoginRequest(BaseModel):
    email: EmailStr
    password: str
