from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreateRequest(BaseModel):
    scheme_name: str = Field(min_length=1)
    college_name: str = Field(min_length=1)
    board: str = Field(min_length=1)
    class_12_year: int = Field(ge=1900, le=2200)
    stream: str = Field(min_length=1)
    marks_percentage: float = Field(ge=0, le=100)
    course_name: str = Field(min_length=1)
    course_type: str = Field(min_length=1)
    admission_year: int = Field(ge=1900, le=2200)
    annual_family_income: float = Field(ge=0)
    other_scholarship: bool
    regular_course: bool
    is_diploma: bool
    drop_after_class_12: bool


class ApplicationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_name: str | None = Field(default=None, min_length=1)
    college_name: str | None = Field(default=None, min_length=1)
    board: str | None = Field(default=None, min_length=1)
    class_12_year: int | None = Field(default=None, ge=1900, le=2200)
    stream: str | None = Field(default=None, min_length=1)
    marks_percentage: float | None = Field(default=None, ge=0, le=100)
    course_name: str | None = Field(default=None, min_length=1)
    course_type: str | None = Field(default=None, min_length=1)
    admission_year: int | None = Field(default=None, ge=1900, le=2200)
    annual_family_income: float | None = Field(default=None, ge=0)
    other_scholarship: bool | None = None
    regular_course: bool | None = None
    is_diploma: bool | None = None
    drop_after_class_12: bool | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_number: str
    scheme_name: str | None
    college_name: str | None
    board: str | None
    class_12_year: int | None
    stream: str | None
    marks_percentage: str | None
    course_name: str | None
    course_type: str | None
    admission_year: int | None
    annual_family_income: str | None
    other_scholarship: str | None
    regular_course: str | None
    is_diploma: str | None
    drop_after_class_12: str | None
    status: str