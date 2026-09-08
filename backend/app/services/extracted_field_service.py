from sqlalchemy.orm import Session

from app.models import ExtractedField


def save_extracted_information(
    db: Session,
    document_id: int,
    extracted_data: dict
):
    """
    Save extracted document information into PostgreSQL.
    """

    saved_fields = []

    # Save simple fields
    simple_fields = [
        "student_name",
        "roll_number",
        "school"
    ]

    for field_name in simple_fields:

        value = extracted_data.get(field_name)

        if value is not None:
            field = ExtractedField(
                document_id=document_id,
                field_name=field_name,
                field_value=str(value),
                confidence=None,
                page_number=1
            )

            db.add(field)
            saved_fields.append(field_name)

    # Save subject marks
    marks = extracted_data.get("marks", {})

    for subject, mark in marks.items():

        field = ExtractedField(
            document_id=document_id,
            field_name=subject,
            field_value=str(mark),
            confidence=None,
            page_number=1
        )

        db.add(field)
        saved_fields.append(subject)

    db.commit()

    return saved_fields