import re


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison.

    Example:
    'Nithilaa S' -> 'NITHILAA S'
    """

    if not name:
        return ""

    name = name.upper()

    # Keep only letters and spaces
    name = re.sub(r"[^A-Z ]", " ", name)

    # Remove extra spaces
    name = re.sub(r"\s+", " ", name).strip()

    return name


def compare_application_with_document(
    application,
    extracted_data: dict
) -> dict:
    """
    Compare application information with
    information extracted from uploaded documents.
    """

    findings = []

    # ==================================================
    # 1. STUDENT NAME
    # ==================================================

    document_name = extracted_data.get("student_name")

    if document_name:

        findings.append({
            "field": "student_name",
            "status": "EXTRACTED",
            "document_value": document_name
        })

    # ==================================================
    # 2. EXTRACTED MARKS
    # ==================================================

    extracted_marks = extracted_data.get("marks", {})

    subject_marks = []

    for subject, marks in extracted_marks.items():

        if isinstance(marks, (int, float)):

            if 0 <= marks <= 100:
                subject_marks.append(marks)

    # ==================================================
    # 3. CALCULATE PERCENTAGE
    # ==================================================

    calculated_percentage = None

    if subject_marks:

        calculated_percentage = round(
            sum(subject_marks) / len(subject_marks),
            2
        )

    # ==================================================
    # 4. GET APPLICATION PERCENTAGE
    # ==================================================

    application_percentage = None

    if application.marks_percentage is not None:

        try:

            application_percentage = float(
                application.marks_percentage
            )

        except (ValueError, TypeError):

            application_percentage = None

    # ==================================================
    # 5. COMPARE PERCENTAGE
    # ==================================================

    if (
        application_percentage is not None
        and calculated_percentage is not None
    ):

        difference = round(
            abs(
                application_percentage
                - calculated_percentage
            ),
            2
        )

        # Allow small rounding difference
        if difference <= 1:

            status = "MATCH"

        else:

            status = "MISMATCH"

        findings.append({
            "field": "marks_percentage",
            "status": status,
            "application_value": application_percentage,
            "document_calculated_value": calculated_percentage,
            "difference": difference
        })

    # ==================================================
    # 6. FINAL VERIFICATION STATUS
    # ==================================================

    mismatch_found = any(
        finding.get("status") == "MISMATCH"
        for finding in findings
    )

    if mismatch_found:

        verification_status = "MISMATCH_FOUND"

    else:

        verification_status = "MATCHED"

    # ==================================================
    # 7. RETURN RESULT
    # ==================================================

    return {
        "verification_status": verification_status,
        "findings": findings
    }