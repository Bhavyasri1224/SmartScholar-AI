from pydantic import BaseModel


class ApplicationCreateRequest(BaseModel):
    scheme_name: str
    college_name: str
    board: str
    class_12_year: int
    stream: str
    marks_percentage: float
    course_name: str
    course_type: str
    admission_year: int
    annual_family_income: float
    other_scholarship: bool
    regular_course: bool
    is_diploma: bool
    drop_after_class_12: bool