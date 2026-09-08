from pydantic import BaseModel, ConfigDict, Field


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    full_name: str
    date_of_birth: str | None = None
    phone: str | None = None
    gender: str | None = None
    category: str | None = None
    state: str | None = None


class StudentProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    date_of_birth: str | None = None
    phone: str | None = None
    gender: str | None = None
    category: str | None = None
    state: str | None = None
