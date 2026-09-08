import re


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