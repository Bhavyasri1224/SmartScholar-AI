"""Deterministic application analysis for officer-assisted review.

This module is an explainable rules engine, not a trained fraud or language
model. It compares persisted application/profile values with extracted fields
and reuses Phase 2 eligibility validation.
"""

import json
import re
from collections import defaultdict
from typing import Any, Iterable

from app.models import Application, Document, ExtractedField, StudentProfile
from app.services.validation_service import (
    validate_application_completeness,
    validate_eligibility,
)

ANALYSIS_FINDING_TYPES = {
    "MISMATCH",
    "MISSING_INFORMATION",
    "ELIGIBILITY",
    "DOCUMENT_ISSUE",
    "RISK",
    "CONSISTENCY",
    "MISSING_DOCUMENT",
    "LOW_CONFIDENCE",
    "INVALID_DOCUMENT",
}
SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _numeric(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _field_map(fields: Iterable[ExtractedField]) -> dict[int, dict[str, ExtractedField]]:
    mapped: dict[int, dict[str, ExtractedField]] = defaultdict(dict)
    for field in fields:
        mapped[field.document_id][field.field_name.casefold()] = field
    return mapped


def _finding(
    finding_type: str,
    severity: str,
    title: str,
    description: str,
    expected: Any = None,
    observed: Any = None,
    document: Document | None = None,
    field: ExtractedField | None = None,
) -> dict:
    return {
        "finding_type": finding_type,
        "severity": severity,
        "title": title,
        "description": description,
        "expected_value": None if expected is None else str(expected),
        "observed_value": None if observed is None else str(observed),
        "source_document_id": document.id if document else None,
        "source_page": field.page_number if field else None,
        "confidence": field.confidence if field else None,
        "status": "OPEN",
    }


def _document_field(
    documents: list[Document],
    fields_by_document: dict[int, dict[str, ExtractedField]],
    document_type: str,
    field_names: tuple[str, ...],
) -> tuple[Document, ExtractedField] | None:
    for document in documents:
        if document.document_type != document_type:
            continue
        for field_name in field_names:
            field = fields_by_document.get(document.id, {}).get(field_name)
            if field and field.field_value:
                return document, field
    return None


def _compare_text(
    findings: list[dict],
    title: str,
    application_value: Any,
    document_type: str,
    field_names: tuple[str, ...],
    documents: list[Document],
    fields_by_document: dict[int, dict[str, ExtractedField]],
) -> None:
    if application_value is None or not str(application_value).strip():
        return
    match = _document_field(documents, fields_by_document, document_type, field_names)
    if not match:
        return
    document, field = match
    if _normalize_text(application_value) == _normalize_text(field.field_value):
        return
    findings.append(_finding(
        "MISMATCH",
        "HIGH" if field_names == ("student_name",) else "MEDIUM",
        title,
        f"Application value '{application_value}' does not match the value extracted from the {document_type.lower()}.",
        application_value,
        field.field_value,
        document,
        field,
    ))


def _compare_number(
    findings: list[dict],
    title: str,
    application_value: Any,
    document_type: str,
    field_names: tuple[str, ...],
    documents: list[Document],
    fields_by_document: dict[int, dict[str, ExtractedField]],
) -> None:
    application_number = _numeric(application_value)
    if application_number is None:
        return
    match = _document_field(documents, fields_by_document, document_type, field_names)
    if not match:
        return
    document, field = match
    observed_number = _numeric(field.field_value)
    if observed_number is None or abs(application_number - observed_number) < 0.01:
        return
    findings.append(_finding(
        "MISMATCH",
        "HIGH",
        title,
        f"Application value '{application_value}' does not match the value extracted from the {document_type.lower()}.",
        application_value,
        field.field_value,
        document,
        field,
    ))


def _risk_level(findings: list[dict]) -> str:
    if any(item["severity"] == "CRITICAL" for item in findings):
        return "CRITICAL"
    high_count = sum(item["severity"] == "HIGH" for item in findings)
    if high_count >= 2:
        return "HIGH"
    if high_count == 1:
        return "HIGH"
    if any(item["severity"] == "MEDIUM" for item in findings):
        return "MEDIUM"
    return "LOW"


def _recommendation(result: str, risk_level: str) -> str:
    if result == "INELIGIBLE":
        return "Eligibility review required"
    if risk_level in {"HIGH", "CRITICAL"} or result == "REVIEW_REQUIRED":
        return "Officer review required"
    return "No additional review indicated by automated checks"


def analyze_application(
    application: Application,
    profile: StudentProfile | None,
    documents: list[Document],
    extracted_fields: list[ExtractedField],
    scheme: Any = None,
) -> dict:
    fields_by_document = _field_map(extracted_fields)
    findings: list[dict] = []

    completeness = validate_application_completeness(application, documents)
    eligibility = validate_eligibility(application, scheme)
    for issue in eligibility["issues"]:
        findings.append(_finding("ELIGIBILITY", "HIGH", "Eligibility rule failed", issue))
    for missing_document in completeness["missing_documents"]:
        findings.append(_finding(
            "MISSING_DOCUMENT", "HIGH", "Required document missing",
            f"Required document {missing_document} was not found.",
            missing_document,
        ))

    for document in documents:
        document_fields = fields_by_document.get(document.id, {})
        if document.ocr_status != "COMPLETED":
            findings.append(_finding(
                "DOCUMENT_ISSUE", "HIGH", "Document OCR incomplete",
                f"Document {document.id} was not processed successfully.",
                "COMPLETED", document.ocr_status, document,
            ))
        elif not document_fields:
            findings.append(_finding(
                "MISSING_INFORMATION", "MEDIUM", "No fields extracted",
                f"No supported fields were extracted from document {document.id}.",
                document.document_type, None, document,
            ))

    student_name = profile.full_name if profile else None
    for document_type, label in (
        ("MARKSHEET", "Student name mismatch in marksheet"),
        ("INCOME_CERTIFICATE", "Student name mismatch in income certificate"),
        ("CASTE_CERTIFICATE", "Student name mismatch in caste certificate"),
    ):
        _compare_text(
            findings, label, student_name, document_type, ("student_name",),
            documents, fields_by_document,
        )

    _compare_number(
        findings, "Percentage mismatch", application.marks_percentage,
        "MARKSHEET", ("percentage",), documents, fields_by_document,
    )
    _compare_text(
        findings, "Board mismatch", application.board,
        "MARKSHEET", ("board",), documents, fields_by_document,
    )
    _compare_text(
        findings, "Passing year mismatch", application.class_12_year,
        "MARKSHEET", ("year", "passing_year"), documents, fields_by_document,
    )
    _compare_number(
        findings, "Family income mismatch", application.annual_family_income,
        "INCOME_CERTIFICATE", ("annual_income",), documents, fields_by_document,
    )
    if profile and profile.category:
        _compare_text(
            findings, "Category mismatch", profile.category,
            "CASTE_CERTIFICATE", ("category", "caste"), documents, fields_by_document,
        )

    risk_level = _risk_level(findings)
    if not eligibility["eligible"]:
        eligibility_result = "INELIGIBLE"
    elif findings:
        eligibility_result = "REVIEW_REQUIRED"
    else:
        eligibility_result = "ELIGIBLE"

    key_issues = [item["title"] for item in findings]
    if not findings:
        summary_text = (
            "Application is eligible based on the provided application information. "
            "Processed documents are consistent with the available application data."
        )
    else:
        summary_text = "Application requires officer review. " + " ".join(
            item["description"] for item in findings[:5]
        )
    evidence_summary = (
        f"Reviewed {len(documents)} document(s) and {len(extracted_fields)} extracted field(s)."
    )
    return {
        "eligibility_result": eligibility_result,
        "risk_level": risk_level,
        "findings": findings,
        "summary_text": summary_text,
        "key_issues": key_issues,
        "evidence_summary": evidence_summary,
        "recommendation": _recommendation(eligibility_result, risk_level),
        "eligibility": eligibility,
        "completeness": completeness,
    }


def serialize_finding(finding: Any) -> dict:
    return {
        "id": finding.id,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "title": finding.title,
        "description": finding.description,
        "expected_value": finding.expected_value,
        "observed_value": finding.observed_value,
        "source_document_id": finding.source_document_id,
        "source_page": finding.source_page,
        "confidence": finding.confidence,
        "status": finding.status,
    }


def serialize_summary(summary: Any) -> dict:
    return {
        "id": summary.id,
        "summary_text": summary.summary_text,
        "eligibility_result": summary.eligibility_result,
        "risk_level": summary.risk_level,
        "key_issues": json.loads(summary.key_issues) if summary.key_issues else [],
        "evidence_summary": summary.evidence_summary,
    }
