
KEYWORDS = {
    "AADHAAR": ("aadhaar", "unique identification", "government of india"),
    "INCOME_CERTIFICATE": ("income certificate", "annual income", "yearly income"),
    "MARKSHEET": ("marksheet", "mark sheet", "percentage", "board", "subject"),
    "CASTE_CERTIFICATE": ("caste certificate", "scheduled caste", "backward class"),
    "BONAFIDE_CERTIFICATE": ("bonafide", "bonafide certificate"),
    "BANK_DOCUMENT": ("bank account", "ifsc", "passbook"),
    "ADMISSION_PROOF": ("admission", "enrollment", "college"),
}


def classify_document_result(text: str) -> dict:
    normalized = (text or "").lower()
    scores = {
        document_type: sum(keyword in normalized for keyword in keywords)
        for document_type, keywords in KEYWORDS.items()
    }
    document_type, score = max(scores.items(), key=lambda item: item[1])
    if score == 0:
        return {"document_type": "OTHER", "confidence": None}
    total_keywords = len(KEYWORDS[document_type])
    return {
        "document_type": document_type,
        "confidence": round(score / total_keywords, 2),
    }


def classify_document(text: str) -> str:
    return classify_document_result(text)["document_type"]
