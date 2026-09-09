import os

import pymupdf
import pytesseract
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageOps


load_dotenv()
if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]


def _check_tesseract() -> None:
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise RuntimeError("OCR is unavailable: configure TESSERACT_CMD or install Tesseract") from exc


def _ocr_image(image: Image.Image) -> str:
    return pytesseract.image_to_string(
        preprocess_image(image),
        config="--oem 3 --psm 6",
    ).strip()


def extract_document_text(file_path: str, mime_type: str | None) -> dict:
    if mime_type == "application/pdf":
        try:
            document = pymupdf.open(file_path)
        except Exception as exc:
            raise ValueError("The uploaded PDF is invalid or corrupted") from exc

        if len(document) == 0:
            document.close()
            raise ValueError("The uploaded PDF contains no pages")

        pages: list[dict] = []
        needs_ocr = False
        for index, page in enumerate(document):
            text = page.get_text().strip()
            page_result = {"page_number": index + 1, "text": text}
            pages.append(page_result)
            if len(text) < 20:
                needs_ocr = True

        if needs_ocr:
            _check_tesseract()
            for index, page in enumerate(document):
                if len(pages[index]["text"]) >= 20:
                    continue
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                pages[index]["text"] = _ocr_image(image)
        document.close()
    elif mime_type in {"image/jpeg", "image/png"}:
        try:
            with Image.open(file_path) as image:
                image.verify()
            _check_tesseract()
            with Image.open(file_path) as image:
                pages = [{"page_number": 1, "text": _ocr_image(image)}]
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise ValueError("The uploaded image is invalid or corrupted") from exc
    else:
        raise ValueError("Unsupported document type")

    text = "\n\n".join(
        f"--- Page {page['page_number']} ---\n{page['text']}"
        for page in pages
    )
    if not text.strip() or not any(page["text"].strip() for page in pages):
        raise ValueError("No readable text was found in the document")
    return {
        "text": text,
        "pages": pages,
        "page_count": len(pages),
        "status": "COMPLETED",
    }


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess the page image before OCR.

    Steps:
    1. Convert to grayscale
    2. Improve contrast
    3. Convert to black and white
    """

    # Convert image to grayscale
    image = ImageOps.grayscale(image)

    # Improve contrast
    image = ImageEnhance.Contrast(image).enhance(2.0)

    # Convert to black and white
    image = image.point(
        lambda pixel: 255 if pixel > 180 else 0
    )

    return image


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF using
    image preprocessing + Tesseract OCR.
    """

    document = pymupdf.open(file_path)

    extracted_text = []

    for page_number in range(len(document)):

        page = document[page_number]

        # Render PDF page at higher resolution
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(3, 3)
        )

        image = Image.frombytes(
            "RGB",
            [pixmap.width, pixmap.height],
            pixmap.samples
        )

        # Preprocess image
        processed_image = preprocess_image(image)

        # Run Tesseract OCR
        text = pytesseract.image_to_string(
            processed_image,
            config="--oem 3 --psm 6"
        )

        extracted_text.append(
            f"--- Page {page_number + 1} ---\n{text}"
        )

    document.close()

    return "\n\n".join(extracted_text)