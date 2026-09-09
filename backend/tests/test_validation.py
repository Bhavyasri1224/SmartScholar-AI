from app.core.security import create_access_token, password_hash
from app.models import Application, Document, StudentProfile, User
from app.services.validation_service import (
    validate_application_completeness,
    validate_application_fields,
    validate_application_for_submission,
    validate_eligibility,
)


VALID_VALUES = {
    "scheme_name": "PM-USP",
    "college_name": "Government College",
    "board": "CBSE",
    "class_12_year": 2024,
    "stream": "Science",
    "marks_percentage": "82.5",
    "course_name": "BSc Computer Science",
    "course_type": "UG",
    "admission_year": 2024,
    "annual_family_income": "180000",
    "other_scholarship": "false",
    "regular_course": "true",
    "is_diploma": "false",
    "drop_after_class_12": "false",
}


def valid_application():
    return Application(
        student_profile_id=1,
        application_number="APP-VALIDATION",
        status="DRAFT",
        **VALID_VALUES,
    )


def required_documents():
    return [
        Document(
            application_id=1,
            document_type="MARKSHEET",
            file_name="marksheet.pdf",
            file_path="uploads/marksheet.pdf",
        ),
        Document(
            application_id=1,
            document_type="INCOME_CERTIFICATE",
            file_name="income.pdf",
            file_path="uploads/income.pdf",
        ),
    ]


def create_student_application(db_session, complete_documents=False):
    user = User(
        email="submit@example.com",
        password_hash=password_hash.hash("StrongPassword123!"),
        role="STUDENT",
    )
    db_session.add(user)
    db_session.flush()
    profile = StudentProfile(user_id=user.id, full_name="Submit Student")
    db_session.add(profile)
    db_session.flush()
    application = valid_application()
    application.student_profile_id = profile.id
    application.application_number = "APP-SUBMIT"
    db_session.add(application)
    db_session.flush()
    if complete_documents:
        for document in required_documents():
            document.application_id = application.id
            db_session.add(document)
    db_session.commit()
    return application


def test_valid_application():
    result = validate_application_fields(valid_application())

    assert result["valid"] is True
    assert result["errors"] == []


def test_missing_required_field():
    application = valid_application()
    application.course_name = None

    result = validate_application_fields(application)

    assert result["valid"] is False
    assert {error["code"] for error in result["errors"]} == {"REQUIRED"}
    assert result["errors"][0]["field"] == "course_name"


def test_invalid_marks_percentage():
    application = valid_application()
    application.marks_percentage = "101"

    result = validate_application_fields(application)

    assert result["valid"] is False
    assert any(error["field"] == "marks_percentage" for error in result["errors"])


def test_invalid_family_income():
    application = valid_application()
    application.annual_family_income = "-1"

    result = validate_application_fields(application)

    assert result["valid"] is False
    assert any(error["code"] == "NEGATIVE_VALUE" for error in result["errors"])


def test_missing_required_document():
    result = validate_application_completeness(valid_application(), [required_documents()[0]])

    assert result["complete"] is False
    assert result["missing_documents"] == ["INCOME_CERTIFICATE"]


def test_incomplete_application():
    application = valid_application()
    application.annual_family_income = None

    result = validate_application_completeness(application, [])

    assert result["complete"] is False
    assert "annual_family_income" in result["missing_fields"]
    assert set(result["missing_documents"]) == {"MARKSHEET", "INCOME_CERTIFICATE"}


def test_eligible_application():
    result = validate_eligibility(valid_application())

    assert result["eligible"] is True
    assert all(check["passed"] for check in result["checks"])


def test_ineligible_application():
    application = valid_application()
    application.annual_family_income = "500000"

    result = validate_eligibility(application)

    assert result["eligible"] is False
    assert any(check["rule"] == "FAMILY_INCOME" and not check["passed"] for check in result["checks"])


def test_submission_blocked_when_validation_fails(client, db_session):
    application = create_student_application(db_session)
    user_id = db_session.query(StudentProfile).filter(
        StudentProfile.id == application.student_profile_id
    ).one().user_id
    token = create_access_token(
        {"user_id": user_id, "role": "STUDENT"}
    )

    response = client.post(
        f"/api/applications/{application.id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["valid"] is False
    assert db_session.get(Application, application.id).status == "DRAFT"


def test_submission_succeeds_when_validation_passes(client, db_session):
    application = create_student_application(db_session, complete_documents=True)
    user_id = db_session.query(StudentProfile).filter(
        StudentProfile.id == application.student_profile_id
    ).one().user_id
    token = create_access_token(
        {"user_id": user_id, "role": "STUDENT"}
    )

    response = client.post(
        f"/api/applications/{application.id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"
    assert db_session.get(Application, application.id).status == "SUBMITTED"


def test_submission_validation_result_is_structured():
    result = validate_application_for_submission(valid_application(), required_documents())

    assert result["valid"] is True
    assert result["complete"] is True
    assert result["eligibility"]["eligible"] is True
