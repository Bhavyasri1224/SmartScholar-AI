
KEYWORDS = {
    "AADHAAR": ("aadhaar", "unique identification", "government of india"),
    "INCOME_CERTIFICATE": ("income certificate", "annual income", "yearly income"),
    "MARKSHEET": ("marksheet", "mark sheet", "percentage", "board", "subject"),
    "CASTE_CERTIFICATE": ("caste certificate", "scheduled caste", "backward class"),
    "BONAFIDE_CERTIFICATE": ("bonafide", "bonafide certificate"),
    "BANK_DOCUMENT": ("bank account", "ifsc", "passbook"),
    "ADMISSION_PROOF": ("admission", "enrollment", "college"),
}


def classify_document(text: str) -> str:
    normalized = (text or "").lower()
    for document_type, keywords in KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return document_type
    return "OTHER"
