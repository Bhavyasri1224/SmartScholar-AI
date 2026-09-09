import re
from collections.abc import Iterable


# This is a transparent heuristic based on labelled OCR text, not a model
# confidence score. It preserves the existing confidence representation.
HEURISTIC_CONFIDENCE = "0.85"


def _field(field_name: str, value: str, page_number: int) -> dict:
    return {
        "field_name": field_name,
        "field_value": re.sub(r"\s+", " ", value).strip(),
        "confidence": HEURISTIC_CONFIDENCE,
        "page_number": page_number,
    }


def _first_match(text: str, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _extract_page_fields(text: str, document_type: str, page_number: int) -> list[dict]:
    fields: list[dict] = []
    if document_type == "MARKSHEET":
        name = _first_match(text, (
            r"(?:student\s+name|name|applicant|student)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,})",
            r"This is to certify that\s+(.+?)(?=\s+Roll\s*No|\n|$)",
        ))
        roll_number = _first_match(text, (r"roll\s*(?:no|number)\.?\s*[:\-]?\s*([A-Za-z0-9/-]+)",))
        board = _first_match(text, (r"board\s*[:\-]\s*([A-Za-z0-9 .&-]+)",))
        marks = _first_match(text, (r"(?:total\s+)?marks\s*[:\-]\s*([0-9]+(?:\.[0-9]+)?)",))
        percentage = _first_match(text, (r"(?:percentage|percent|%)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)",))
        passing_year = _first_match(text, (r"(?:passing\s+year|pass\s+year|year)\s*[:\-]?\s*(20[0-9]{2})",))
        values = (
            ("student_name", name),
            ("roll_number", roll_number),
            ("board", board),
            ("marks", marks),
            ("percentage", percentage),
            ("year", passing_year),
        )
        fields.extend(_field(name, value, page_number) for name, value in values if value)
    elif document_type == "INCOME_CERTIFICATE":
        values = (
            ("student_name", _first_match(text, (r"(?:student\s+name|name|applicant)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,})",))),
            ("annual_income", _first_match(text, (r"(?:annual income|yearly income|income)\s*[:\-]?\s*(?:rs\.?\s*)?([0-9,]+)",))),
            ("certificate_number", _first_match(text, (r"(?:certificate\s*(?:no|number))\s*[:\-]?\s*([A-Za-z0-9/-]+)",))),
            ("issue_date", _first_match(text, (r"(?:issue date|issued on|date of issue)\s*[:\-]?\s*([0-9/.-]+)",))),
        )
        fields.extend(_field(name, value, page_number) for name, value in values if value)
    elif document_type == "CASTE_CERTIFICATE":
        values = (
            ("student_name", _first_match(text, (r"(?:student\s+name|name|applicant)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,})",))),
            ("category", _first_match(text, (r"(?:caste|category)\s*[:\-]\s*([A-Za-z][A-Za-z .-]+)",))),
            ("certificate_number", _first_match(text, (r"(?:certificate\s*(?:no|number))\s*[:\-]?\s*([A-Za-z0-9/-]+)",))),
            ("issue_date", _first_match(text, (r"(?:issue date|issued on|date of issue)\s*[:\-]?\s*([0-9/.-]+)",))),
        )
        fields.extend(_field(name, value, page_number) for name, value in values if value)
    return fields


def extract_document_fields(
    text: str,
    document_type: str,
    pages: list[dict] | None = None,
) -> list[dict]:
    """Extract only fields supported by the classified document type."""
    if pages is None:
        pages = [{"page_number": 1, "text": text or ""}]
    fields: list[dict] = []
    for page in pages:
        fields.extend(_extract_page_fields(
            page.get("text", ""),
            document_type,
            int(page.get("page_number", 1)),
        ))
    return fields


def words_to_number(text: str):
    """
    Convert number words into numeric values.

    Examples:
    SIXTY -> 60
    SIXTY FIVE -> 65
    SEVENTY ONE -> 71
    SEVENTYONE -> 71
    EIGHTY SEVEN -> 87
    EIGHTYSEVEN -> 87
    """

    number_words = {
        "ZERO": 0,
        "ONE": 1,
        "TWO": 2,
        "THREE": 3,
        "FOUR": 4,
        "FIVE": 5,
        "SIX": 6,
        "SEVEN": 7,
        "EIGHT": 8,
        "NINE": 9,
        "TEN": 10,
        "ELEVEN": 11,
        "TWELVE": 12,
        "THIRTEEN": 13,
        "FOURTEEN": 14,
        "FIFTEEN": 15,
        "SIXTEEN": 16,
        "SEVENTEEN": 17,
        "EIGHTEEN": 18,
        "NINETEEN": 19,
        "TWENTY": 20,
        "THIRTY": 30,
        "FORTY": 40,
        "FIFTY": 50,
        "SIXTY": 60,
        "SEVENTY": 70,
        "EIGHTY": 80,
        "NINETY": 90,
    }

    text = text.upper().strip()
    words = text.split()

    # ------------------------------------------
    # Single word
    # ------------------------------------------

    if len(words) == 1:

        word = words[0]

        if word in number_words:
            return number_words[word]

        # Handle OCR joined words
        # SEVENTYONE -> 71
        # SEVENTYTWO -> 72
        # EIGHTYSEVEN -> 87

        tens_words = [
            ("TWENTY", 20),
            ("THIRTY", 30),
            ("FORTY", 40),
            ("FIFTY", 50),
            ("SIXTY", 60),
            ("SEVENTY", 70),
            ("EIGHTY", 80),
            ("NINETY", 90),
        ]

        for tens_word, tens_value in tens_words:

            if word.startswith(tens_word):

                remaining = word[len(tens_word):]

                if remaining in number_words:
                    return tens_value + number_words[remaining]

        return None

    # ------------------------------------------
    # Two-word number
    # ------------------------------------------

    if len(words) == 2:

        first = number_words.get(words[0])
        second = number_words.get(words[1])

        if first is not None and second is not None:
            return first + second

    return None


def extract_information(ocr_text: str) -> dict:
    """
    Extract structured information from OCR text.

    Extracts:
    - Student name
    - Roll number
    - School
    - Subject marks
    """

    result = {
        "student_name": None,
        "roll_number": None,
        "school": None,
        "marks": {}
    }

    # ==================================================
    # 1. STUDENT NAME
    # ==================================================

    name_match = re.search(
        r"This is to certify that\s+(.+?)(?=\s+Roll\s*No|\n)",
        ocr_text,
        re.IGNORECASE
    )

    if name_match:

        name = name_match.group(1).strip()

        # Keep only alphabetic characters and spaces
        name = re.sub(r"[^A-Za-z ]", " ", name)

        # Remove extra spaces
        name = re.sub(r"\s+", " ", name).strip()

        result["student_name"] = name.upper()

    # ==================================================
    # 2. ROLL NUMBER
    # ==================================================

    roll_match = re.search(
        r"Roll\s*No\.?\s*([0-9]+)",
        ocr_text,
        re.IGNORECASE
    )

    if roll_match:

        result["roll_number"] = roll_match.group(1)

    # ==================================================
    # 3. SCHOOL
    # ==================================================

    school_match = re.search(
        r"School\s+\d+\s+(.+)",
        ocr_text,
        re.IGNORECASE
    )

    if school_match:

        school = school_match.group(1).strip()

        # Stop if OCR accidentally includes next section
        school = school.split("\n")[0].strip()

        result["school"] = school

    # ==================================================
    # 4. SUBJECT MARKS
    # ==================================================

    subjects = {
        "english": "ENGLISH CORE",
        "mathematics": "MATHEMATICS",
        "physics": "PHYSICS",
        "chemistry": "CHEMISTRY",
        "computer_science": "COMPUTER SCIENCE"
    }

    lines = ocr_text.splitlines()

    for subject, subject_name in subjects.items():

        for line in lines:

            if subject_name.lower() not in line.lower():
                continue

            # ------------------------------------------
            # Extract alphabetic words from OCR line
            # ------------------------------------------

            words = re.findall(
                r"[A-Z]+",
                line.upper()
            )

            # ------------------------------------------
            # First check two-word numbers
            # Example:
            # SIXTY FIVE
            # EIGHTY SEVEN
            # ------------------------------------------

            found = False

            for i in range(len(words) - 1):

                phrase = words[i] + " " + words[i + 1]

                value = words_to_number(phrase)

                if value is not None and 30 <= value <= 100:

                    result["marks"][subject] = value
                    found = True
                    break

            if found:
                break

            # ------------------------------------------
            # Then check single / joined numbers
            # Example:
            # NINETY
            # SEVENTYONE
            # EIGHTYSEVEN
            # ------------------------------------------

            for word in words:

                value = words_to_number(word)

                if value is not None and 30 <= value <= 100:

                    result["marks"][subject] = value
                    found = True
                    break

            if found:
                break

    return result