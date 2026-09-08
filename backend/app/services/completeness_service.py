def check_document_completeness(document_types: list[str]) -> dict:
    """
    Check whether the required PM-USP documents are available.
    """

    required_documents = [
        "XII_MARKSHEET",
        "INCOME_CERTIFICATE"
    ]

    conditional_documents = [
        "CATEGORY_CERTIFICATE",
        "DISABILITY_CERTIFICATE"
    ]

    missing_documents = []

    # Check required documents
    for document in required_documents:
        if document not in document_types:
            missing_documents.append(document)

    return {
        "is_complete": len(missing_documents) == 0,
        "missing_documents": missing_documents,
        "uploaded_documents": document_types,
        "conditional_documents": conditional_documents
    }