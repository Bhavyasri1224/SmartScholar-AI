"""Deterministic validation for scholarship applications.

The repository does not define a machine-readable PM-USP rule set. The
service therefore uses documented, configurable MVP defaults and accepts
scheme-specific JSON rules when a Scheme provides them. Update the defaults
or the environment variables when the governing scheme rules are confirmed.
"""

import json
import os
from numbers import Number
from typing import Any, Iterable

from app.models import Application, Document, Scheme
from app.schemas.validation import (
    EligibilityResult,
    EligibilityRuleResult,
    ValidationErrorItem,
    ValidationResult,
)


REQUIRED_DOCUMENT_TYPES = ("MARKSHEET", "INCOME_CERTIFICATE")
BOOLEAN_FIELDS = (
    "other_scholarship",
    "regular_course",
    "is_diploma",
    "drop_after_class_12",
)
REQUIRED_APPLICATION_FIELDS = (
    "scheme_name",
    "college_name",
    "board",
    "class_12_year",
    "stream",
    "marks_percentage",
    "course_name",
    "course_type",
    "admission_year",
    "annual_family_income",
    *BOOLEAN_FIELDS,
)

# These are MVP assumptions because no definitive rule configuration exists
# in the repository. They can be overridden without changing the schema.
DEFAULT_MAX_FAMILY_INCOME = 450000.0
MAX_FAMILY_INCOME = float(
    os.getenv("PM_USP_MAX_FAMILY_INCOME", DEFAULT_MAX_FAMILY_INCOME)
)


def _error(field: str, code: str, message: str) -> ValidationErrorItem:
    return ValidationErrorItem(field=field, code=code, message=message)


def _value(application: Any, field: str) -> Any:
    if isinstance(application, dict):
        return application.get(field)
    return getattr(application, field, None)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, Number) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def validate_application_fields(application: Application | dict[str, Any]) -> dict:
    errors: list[ValidationErrorItem] = []
    warnings: list[str] = []

    for field in REQUIRED_APPLICATION_FIELDS:
        if _is_missing(_value(application, field)):
            errors.append(_error(field, "REQUIRED", f"{field} is required."))

    for field in ("class_12_year", "admission_year"):
        value = _value(application, field)
        if _is_missing(value):
            continue
        year = _integer(value)
        if year is None or not 1900 <= year <= 2200:
            errors.append(_error(field, "INVALID_YEAR", f"{field} must be a valid year."))

    marks = _value(application, "marks_percentage")
    if not _is_missing(marks):
        marks_value = _number(marks)
        if marks_value is None:
            errors.append(_error("marks_percentage", "INVALID_NUMBER", "Marks percentage must be numeric."))
        elif not 0 <= marks_value <= 100:
            errors.append(_error("marks_percentage", "OUT_OF_RANGE", "Marks percentage must be between 0 and 100."))

    income = _value(application, "annual_family_income")
    if not _is_missing(income):
        income_value = _number(income)
        if income_value is None:
            errors.append(_error("annual_family_income", "INVALID_NUMBER", "Annual family income must be numeric."))
        elif income_value < 0:
            errors.append(_error("annual_family_income", "NEGATIVE_VALUE", "Annual family income cannot be negative."))

    for field in BOOLEAN_FIELDS:
        value = _value(application, field)
        if not _is_missing(value) and _boolean(value) is None:
            errors.append(_error(field, "INVALID_BOOLEAN", f"{field} must be true or false."))

    class_year = _integer(_value(application, "class_12_year"))
    admission_year = _integer(_value(application, "admission_year"))
    if class_year is not None and admission_year is not None and admission_year < class_year:
        errors.append(_error("admission_year", "INVALID_SEQUENCE", "Admission year cannot be before class 12 year."))

    return {
        "valid": not errors,
        "errors": [item.model_dump() for item in errors],
        "warnings": warnings,
    }


def _document_types(documents: Iterable[Document | str]) -> list[str]:
    values = []
    for document in documents:
        value = document if isinstance(document, str) else getattr(document, "document_type", None)
        if value:
            values.append(str(value).strip().upper())
    return sorted(set(values))


def validate_required_documents(documents: Iterable[Document | str]) -> dict:
    uploaded_documents = _document_types(documents)
    missing_documents = [
        document_type
        for document_type in REQUIRED_DOCUMENT_TYPES
        if document_type not in uploaded_documents
    ]
    errors = [
        _error(
            "documents",
            "MISSING_DOCUMENT",
            f"Required document is missing: {document_type}.",
        )
        for document_type in missing_documents
    ]
    return {
        "valid": not errors,
        "errors": [item.model_dump() for item in errors],
        "warnings": [],
        "missing_documents": missing_documents,
        "uploaded_documents": uploaded_documents,
    }


def validate_application_completeness(
    application: Application | dict[str, Any],
    documents: Iterable[Document | str],
) -> dict:
    field_result = validate_application_fields(application)
    document_result = validate_required_documents(documents)
    missing_fields = [
        item["field"]
        for item in field_result["errors"]
        if item["code"] == "REQUIRED"
    ]
    errors = field_result["errors"] + document_result["errors"]
    return {
        "complete": not errors,
        "valid": not errors,
        "errors": errors,
        "warnings": field_result["warnings"] + document_result["warnings"],
        "missing_fields": missing_fields,
        "missing_documents": document_result["missing_documents"],
    }


def _configured_rules(scheme: Scheme | dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    rules: dict[str, Any] = {
        "max_family_income": MAX_FAMILY_INCOME,
        "requires_regular_course": True,
        "disallow_other_scholarship": True,
        "disallow_diploma": True,
        "disallow_drop_after_class_12": True,
    }
    warnings: list[str] = []
    raw_rules = None
    if scheme is not None:
        raw_rules = scheme.get("eligibility_rules") if isinstance(scheme, dict) else scheme.eligibility_rules
    if raw_rules:
        try:
            configured = json.loads(raw_rules) if isinstance(raw_rules, str) else raw_rules
            if not isinstance(configured, dict):
                raise ValueError
            rules.update(configured)
        except (TypeError, ValueError, json.JSONDecodeError):
            warnings.append("Scheme eligibility_rules is not valid JSON; MVP defaults were used.")
    return rules, warnings


def validate_eligibility(
    application: Application | dict[str, Any],
    scheme: Scheme | dict[str, Any] | None = None,
) -> dict:
    rules, warnings = _configured_rules(scheme)
    checks: list[EligibilityRuleResult] = []
    issues: list[str] = []

    income = _number(_value(application, "annual_family_income"))
    income_limit = _number(rules.get("max_family_income"))
    income_passed = income is not None and income_limit is not None and income <= income_limit
    checks.append(EligibilityRuleResult(
        rule="FAMILY_INCOME",
        passed=income_passed,
        observed=income,
        expected=f"<= {income_limit:g}" if income_limit is not None else "configured limit",
        message="Family income satisfies the eligibility condition." if income_passed else "Family income exceeds the configured limit or is unavailable.",
    ))
    if not income_passed:
        issues.append("Family income does not satisfy the configured limit.")

    boolean_rules = (
        ("REGULAR_COURSE", "regular_course", True, "Application must be for a regular course."),
        ("OTHER_SCHOLARSHIP", "other_scholarship", False, "Applicant must not receive another scholarship."),
        ("DIPLOMA_STATUS", "is_diploma", False, "Diploma courses are not eligible under the MVP rules."),
        ("DROP_AFTER_CLASS_12", "drop_after_class_12", False, "A post-class-12 drop is not eligible under the MVP rules."),
    )
    for rule, field, expected_value, message in boolean_rules:
        enabled = {
            "regular_course": rules.get("requires_regular_course", True),
            "other_scholarship": rules.get("disallow_other_scholarship", True),
            "is_diploma": rules.get("disallow_diploma", True),
            "drop_after_class_12": rules.get("disallow_drop_after_class_12", True),
        }[field]
        if not enabled:
            continue
        observed = _boolean(_value(application, field))
        passed = observed is not None and observed is expected_value
        checks.append(EligibilityRuleResult(
            rule=rule,
            passed=passed,
            observed=observed,
            expected=str(expected_value).lower(),
            message=message if not passed else "Application satisfies the eligibility condition.",
        ))
        if not passed:
            issues.append(message)

    result = EligibilityResult(
        eligible=not issues,
        issues=issues,
        warnings=warnings,
        checks=checks,
    )
    return result.model_dump()


def validate_application_for_submission(
    application: Application | dict[str, Any],
    documents: Iterable[Document | str],
    scheme: Scheme | dict[str, Any] | None = None,
) -> dict:
    completeness = validate_application_completeness(application, documents)
    eligibility = validate_eligibility(application, scheme)
    errors = list(completeness["errors"])
    errors.extend(
        _error("eligibility", "INELIGIBLE", issue).model_dump()
        for issue in eligibility["issues"]
    )
    warnings = completeness["warnings"] + eligibility["warnings"]
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "complete": completeness["complete"],
        "missing_fields": completeness["missing_fields"],
        "missing_documents": completeness["missing_documents"],
        "eligibility": eligibility,
    }
