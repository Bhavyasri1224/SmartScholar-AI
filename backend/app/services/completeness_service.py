def check_document_completeness(document_types: list[str]) -> dict:
    """
    Check whether the required PM-USP documents are available.
    """

    required_documents = [
        "MARKSHEET",
        "INCOME_CERTIFICATE"
    ]

    conditional_documents = [
        "CASTE_CERTIFICATE",
        "DISABILITY_CERTIFICATE"
    ]

    normalized_types = {
        str(document_type).strip().upper()
        for document_type in document_types
    }

    missing_documents = []

    # Check required documents
    for document in required_documents:
        if document not in normalized_types:
            missing_documents.append(document)

    return {
        "is_complete": len(missing_documents) == 0,
        "missing_documents": missing_documents,
        "uploaded_documents": sorted(normalized_types),
        "conditional_documents": conditional_documents
    }