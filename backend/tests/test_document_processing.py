from pathlib import Path

import pymupdf
from PIL import Image

from app.core.security import create_access_token, password_hash
from app.models import Application, Document, ExtractedField, StudentProfile, User
from app.services import ocr_service
from app.services.classification_service import classify_document, classify_document_result
from app.services.extraction_service import extract_document_fields
from app.services.ocr_service import extract_document_text


def create_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def create_image(path: Path) -> None:
    image = Image.new("RGB", (300, 100), "white")
    image.save(path, format="PNG")


def create_student_application(db_session, email: str, application_number: str):
    user = User(
        email=email,
        password_hash=password_hash.hash("StrongPassword123!"),
        role="STUDENT",
    )
    db_session.add(user)
    db_session.flush()
    profile = StudentProfile(user_id=user.id, full_name="Document Student")
    db_session.add(profile)
    db_session.flush()
    application = Application(
        student_profile_id=profile.id,
        application_number=application_number,
        status="DRAFT",
        scheme_name="PM-USP",
    )
    db_session.add(application)
    db_session.commit()
    return user, application


def auth_header(user_id: int) -> dict[str, str]:
    token = create_access_token({"user_id": user_id, "role": "STUDENT"})
    return {"Authorization": f"Bearer {token}"}


def test_pdf_page_count(tmp_path):
    path = tmp_path / "two-pages.pdf"
    create_pdf(path, ["This is page one with useful text.", "This is page two with useful text."])

    result = extract_document_text(str(path), "application/pdf")

    assert result["page_count"] == 2
    assert len(result["pages"]) == 2


def test_image_page_count(tmp_path, monkeypatch):
    path = tmp_path / "image.png"
    create_image(path)
    monkeypatch.setattr(ocr_service, "_check_tesseract", lambda: None)
    monkeypatch.setattr(ocr_service, "_ocr_image", lambda image: "Income certificate")

    result = extract_document_text(str(path), "image/png")

    assert result["page_count"] == 1
    assert result["pages"][0]["page_number"] == 1


def test_embedded_pdf_text_does_not_require_ocr(tmp_path, monkeypatch):
    path = tmp_path / "embedded.pdf"
    create_pdf(path, ["Income Certificate\nAnnual income: 180000"])
    monkeypatch.setattr(
        ocr_service,
        "_check_tesseract",
        lambda: (_ for _ in ()).throw(RuntimeError("OCR unavailable")),
    )

    result = extract_document_text(str(path), "application/pdf")

    assert "Income Certificate" in result["text"]
    assert result["status"] == "COMPLETED"


def test_ocr_fallback_behavior(tmp_path, monkeypatch):
    path = tmp_path / "scanned.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()
    monkeypatch.setattr(ocr_service, "_check_tesseract", lambda: None)
    monkeypatch.setattr(ocr_service, "_ocr_image", lambda image: "Marks Certificate")

    result = extract_document_text(str(path), "application/pdf")

    assert result["pages"][0]["text"] == "Marks Certificate"


def test_ocr_unavailable_behavior(tmp_path, monkeypatch):
    path = tmp_path / "image.png"
    create_image(path)
    monkeypatch.setattr(
        ocr_service,
        "_check_tesseract",
        lambda: (_ for _ in ()).throw(RuntimeError("OCR unavailable")),
    )

    try:
        extract_document_text(str(path), "image/png")
    except RuntimeError as exc:
        assert "OCR unavailable" in str(exc)
    else:
        raise AssertionError("OCR failure should be reported")


def test_document_classification_types():
    assert classify_document("Income Certificate annual income") == "INCOME_CERTIFICATE"
    assert classify_document("Caste Certificate scheduled caste") == "CASTE_CERTIFICATE"
    assert classify_document("Board marksheet percentage subject") == "MARKSHEET"


def test_unknown_document_classification():
    result = classify_document_result("A document without a recognized category")

    assert result["document_type"] == "OTHER"
    assert result["confidence"] is None


def test_field_extraction_uses_document_type_and_page_number():
    pages = [
        {"page_number": 1, "text": "Income Certificate"},
        {
            "page_number": 2,
            "text": "Student Name: Asha Kumar\nAnnual Income: Rs. 250000\nCertificate Number: INC/42\nIssue Date: 01/04/2025",
        },
    ]

    fields = extract_document_fields("", "INCOME_CERTIFICATE", pages)
    values = {field["field_name"]: field for field in fields}

    assert values["student_name"]["field_value"] == "Asha Kumar"
    assert values["annual_income"]["field_value"] == "250000"
    assert values["annual_income"]["page_number"] == 2
    assert values["certificate_number"]["page_number"] == 2


def test_marksheet_field_extraction():
    fields = extract_document_fields(
        "Student Name: Asha Kumar\nRoll No: 17\nBoard: CBSE\nPercentage: 82.5\nPassing Year: 2024",
        "MARKSHEET",
    )
    values = {field["field_name"]: field["field_value"] for field in fields}

    assert values["student_name"] == "Asha Kumar"
    assert values["roll_number"] == "17"
    assert values["percentage"] == "82.5"
    assert values["year"] == "2024"


def test_reprocessing_replaces_extracted_fields(client, db_session, tmp_path, monkeypatch):
    user, application = create_student_application(
        db_session, "reprocess@example.com", "APP-REPROCESS"
    )
    path = tmp_path / "income.pdf"
    create_pdf(path, ["Income Certificate\nAnnual Income: 180000"])
    document = Document(
        application_id=application.id,
        document_type="OTHER",
        file_name=path.name,
        file_path=str(path),
        mime_type="application/pdf",
        ocr_status="PENDING",
        classification_status="PENDING",
    )
    db_session.add(document)
    db_session.commit()
    headers = auth_header(user.id)

    first = client.post(f"/api/documents/{document.id}/process", headers=headers)
    second = client.post(f"/api/documents/{document.id}/process", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(ExtractedField).filter(
        ExtractedField.document_id == document.id
    ).count() == 1


def test_document_ownership_protection(client, db_session, tmp_path):
    owner, application = create_student_application(
        db_session, "owner@example.com", "APP-OWNER"
    )
    other_user, _ = create_student_application(
        db_session, "other@example.com", "APP-OTHER"
    )
    path = tmp_path / "document.pdf"
    create_pdf(path, ["Income Certificate"])
    document = Document(
        application_id=application.id,
        document_type="INCOME_CERTIFICATE",
        file_name=path.name,
        file_path=str(path),
        mime_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()

    response = client.post(
        f"/api/documents/{document.id}/process",
        headers=auth_header(other_user.id),
    )

    assert response.status_code == 404


def test_invalid_upload_rejected(client, db_session):
    user, application = create_student_application(
        db_session, "upload@example.com", "APP-UPLOAD"
    )

    response = client.post(
        f"/api/applications/{application.id}/documents",
        params={"document_type": "MARKSHEET"},
        headers=auth_header(user.id),
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]
