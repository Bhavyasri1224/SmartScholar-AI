from app.core.security import create_access_token, password_hash
from app.models import (
    AIFinding,
    AISummary,
    Application,
    Document,
    ExtractedField,
    OfficerProfile,
    StudentProfile,
    User,
)
from app.services.analysis_service import analyze_application


VALID_APPLICATION = {
    "scheme_name": "PM-USP",
    "college_name": "Government College",
    "board": "CBSE",
    "class_12_year": 2024,
    "stream": "Science",
    "marks_percentage": "85",
    "course_name": "BSc Computer Science",
    "course_type": "UG",
    "admission_year": 2024,
    "annual_family_income": "180000",
    "other_scholarship": "false",
    "regular_course": "true",
    "is_diploma": "false",
    "drop_after_class_12": "false",
}


def create_case(db_session, email="analysis@example.com", application_number="APP-ANALYSIS"):
    user = User(
        email=email,
        password_hash=password_hash.hash("StrongPassword123!"),
        role="STUDENT",
    )
    db_session.add(user)
    db_session.flush()
    profile = StudentProfile(
        user_id=user.id,
        full_name="Asha Kumar",
        category="OBC",
    )
    db_session.add(profile)
    db_session.flush()
    application = Application(
        student_profile_id=profile.id,
        application_number=application_number,
        status="DRAFT",
        **VALID_APPLICATION,
    )
    db_session.add(application)
    db_session.flush()
    return user, profile, application


def add_document(db_session, application, document_type, fields, ocr_status="COMPLETED"):
    document = Document(
        application_id=application.id,
        document_type=document_type,
        file_name=f"{document_type.lower()}.pdf",
        file_path=f"uploads/{document_type.lower()}.pdf",
        mime_type="application/pdf",
        ocr_status=ocr_status,
        classification_status="COMPLETED",
        page_count=2,
    )
    db_session.add(document)
    db_session.flush()
    for field_name, field_value, page_number in fields:
        db_session.add(ExtractedField(
            document_id=document.id,
            field_name=field_name,
            field_value=str(field_value),
            confidence="0.85",
            page_number=page_number,
        ))
    db_session.flush()
    return document


def add_consistent_documents(db_session, application):
    add_document(db_session, application, "MARKSHEET", [
        ("student_name", "Asha Kumar", 1),
        ("percentage", "85", 2),
        ("board", "CBSE", 2),
        ("year", "2024", 2),
    ])
    add_document(db_session, application, "INCOME_CERTIFICATE", [
        ("student_name", "Asha Kumar", 1),
        ("annual_income", "180000", 2),
    ])
    add_document(db_session, application, "CASTE_CERTIFICATE", [
        ("student_name", "Asha Kumar", 1),
        ("category", "OBC", 2),
    ])


def header(user_id, role="STUDENT"):
    return {"Authorization": f"Bearer {create_access_token({'user_id': user_id, 'role': role})}"}


def test_valid_application_analysis(db_session):
    _, profile, application = create_case(db_session)
    add_consistent_documents(db_session, application)

    result = analyze_application(
        application,
        profile,
        db_session.query(Document).filter(Document.application_id == application.id).all(),
        db_session.query(ExtractedField).join(Document).filter(Document.application_id == application.id).all(),
    )

    assert result["eligibility_result"] == "ELIGIBLE"
    assert result["risk_level"] == "LOW"
    assert result["findings"] == []


def test_no_mismatch_when_values_agree(db_session):
    _, profile, application = create_case(db_session)
    add_consistent_documents(db_session, application)

    result = analyze_application(application, profile,
        db_session.query(Document).filter(Document.application_id == application.id).all(),
        db_session.query(ExtractedField).join(Document).filter(Document.application_id == application.id).all())

    assert not [finding for finding in result["findings"] if finding["finding_type"] == "MISMATCH"]


def test_student_name_mismatch(db_session):
    _, profile, application = create_case(db_session)
    add_document(db_session, application, "MARKSHEET", [("student_name", "Different Student", 2)])

    result = analyze_application(application, profile,
        db_session.query(Document).filter(Document.application_id == application.id).all(),
        db_session.query(ExtractedField).join(Document).filter(Document.application_id == application.id).all())

    finding = next(item for item in result["findings"] if "name mismatch" in item["title"].lower())
    assert finding["severity"] == "HIGH"
    assert finding["source_page"] == 2


def test_percentage_mismatch(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "MARKSHEET", [("percentage", "72", 1)])

    result = analyze_application(application, profile, [document],
        db_session.query(ExtractedField).filter(ExtractedField.document_id == document.id).all())

    finding = next(item for item in result["findings"] if item["title"] == "Percentage mismatch")
    assert finding["expected_value"] == "85"
    assert finding["observed_value"] == "72"
    assert finding["source_document_id"] == document.id


def test_income_mismatch(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "INCOME_CERTIFICATE", [("annual_income", "450000", 2)])

    result = analyze_application(application, profile, [document],
        db_session.query(ExtractedField).filter(ExtractedField.document_id == document.id).all())

    assert any(item["title"] == "Family income mismatch" for item in result["findings"])


def test_category_mismatch(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "CASTE_CERTIFICATE", [("category", "SC", 2)])

    result = analyze_application(application, profile, [document],
        db_session.query(ExtractedField).filter(ExtractedField.document_id == document.id).all())

    assert any(item["title"] == "Category mismatch" for item in result["findings"])


def test_missing_extracted_field_is_not_mismatch(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "MARKSHEET", [])

    result = analyze_application(application, profile, [document], [])

    assert not any(item["finding_type"] == "MISMATCH" for item in result["findings"])
    assert any(item["finding_type"] == "MISSING_INFORMATION" for item in result["findings"])


def test_multiple_findings_and_risk(db_session):
    _, profile, application = create_case(db_session)
    marksheet = add_document(db_session, application, "MARKSHEET", [
        ("student_name", "Wrong Name", 1),
        ("percentage", "72", 2),
        ("board", "ICSE", 2),
    ])
    income = add_document(db_session, application, "INCOME_CERTIFICATE", [("annual_income", "500000", 1)])

    result = analyze_application(application, profile, [marksheet, income],
        db_session.query(ExtractedField).filter(ExtractedField.document_id.in_([marksheet.id, income.id])).all())

    assert len(result["findings"]) >= 3
    assert result["risk_level"] == "HIGH"


def test_ineligible_application(db_session):
    _, profile, application = create_case(db_session)
    application.annual_family_income = "600000"

    result = analyze_application(application, profile, [], [])

    assert result["eligibility_result"] == "INELIGIBLE"
    assert any(item["finding_type"] == "ELIGIBILITY" for item in result["findings"])


def test_review_required_application(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "MARKSHEET", [("percentage", "72", 1)])

    result = analyze_application(application, profile, [document],
        db_session.query(ExtractedField).filter(ExtractedField.document_id == document.id).all())

    assert result["eligibility_result"] == "REVIEW_REQUIRED"
    assert result["recommendation"] == "Officer review required"


def test_no_processed_documents_creates_document_findings(db_session):
    _, profile, application = create_case(db_session)
    document = add_document(db_session, application, "MARKSHEET", [], ocr_status="PENDING")

    result = analyze_application(application, profile, [document], [])

    assert any(item["finding_type"] == "DOCUMENT_ISSUE" for item in result["findings"])


def test_analysis_api_creates_summary_and_returns_structure(client, db_session):
    user, profile, application = create_case(db_session)
    add_consistent_documents(db_session, application)
    db_session.commit()

    response = client.post(
        f"/api/applications/{application.id}/analyze",
        headers=header(user.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == application.id
    assert body["eligibility_result"] == "ELIGIBLE"
    assert body["summary"]["summary_text"]
    assert body["recommendation"]
    assert db_session.query(AISummary).filter(AISummary.application_id == application.id).count() == 1


def test_analysis_api_retains_evidence_page(client, db_session):
    user, profile, application = create_case(db_session, "evidence@example.com", "APP-EVIDENCE")
    document = add_document(db_session, application, "MARKSHEET", [("percentage", "72", 2)])
    db_session.commit()

    response = client.post(
        f"/api/applications/{application.id}/analyze",
        headers=header(user.id),
    )

    finding = next(item for item in response.json()["findings"] if item["title"] == "Percentage mismatch")
    assert finding["source_document_id"] == document.id
    assert finding["source_page"] == 2
    assert profile.full_name == "Asha Kumar"


def test_analysis_replaces_findings_and_summary(client, db_session):
    user, _, application = create_case(db_session)
    add_consistent_documents(db_session, application)
    db_session.commit()
    endpoint = f"/api/applications/{application.id}/analyze"

    first = client.post(endpoint, headers=header(user.id))
    second = client.post(endpoint, headers=header(user.id))

    assert first.status_code == second.status_code == 200
    assert db_session.query(AISummary).filter(AISummary.application_id == application.id).count() == 1
    assert db_session.query(AIFinding).filter(AIFinding.application_id == application.id).count() == 0


def test_student_cannot_analyze_another_students_application(client, db_session):
    owner, _, application = create_case(db_session, "owner-analysis@example.com", "APP-OWNER-ANALYSIS")
    other, _, _ = create_case(db_session, "other-analysis@example.com", "APP-OTHER-ANALYSIS")
    db_session.commit()

    response = client.post(
        f"/api/applications/{application.id}/analyze",
        headers=header(other.id),
    )

    assert response.status_code == 404
    assert owner.id != other.id


def test_officer_can_analyze_application(client, db_session):
    _, _, application = create_case(db_session, "student-for-officer@example.com", "APP-OFFICER")
    officer = User(
        email="analysis-officer@example.com",
        password_hash=password_hash.hash("OfficerPassword123!"),
        role="OFFICER",
    )
    db_session.add(officer)
    db_session.flush()
    db_session.add(OfficerProfile(user_id=officer.id, full_name="Review Officer"))
    db_session.commit()

    response = client.post(
        f"/api/applications/{application.id}/analyze",
        headers=header(officer.id, "OFFICER"),
    )

    assert response.status_code == 200


def test_nonexistent_application(client, db_session):
    user, _, _ = create_case(db_session, "missing@example.com", "APP-MISSING")

    response = client.post(
        "/api/applications/99999/analyze",
        headers=header(user.id),
    )

    assert response.status_code == 404


def test_analysis_requires_authentication(client):
    response = client.post("/api/applications/99999/analyze")

    assert response.status_code == 401


def test_missing_required_documents_are_reported(db_session):
    _, profile, application = create_case(db_session, "missing-docs@example.com", "APP-MISSING-DOCS")
    result = analyze_application(application, profile, [], [])

    missing = [item for item in result["findings"] if item["finding_type"] == "MISSING_DOCUMENT"]
    assert {item["expected_value"] for item in missing} == {"MARKSHEET", "INCOME_CERTIFICATE"}
