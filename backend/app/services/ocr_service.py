import os
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import pymupdf


TESSERACT_PATH = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def _check_tesseract():
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise RuntimeError("Tesseract OCR is not installed or TESSERACT_CMD is invalid") from exc


def extract_document_text(file_path: str, mime_type: str | None) -> dict:
    _check_tesseract()
    if mime_type == "application/pdf":
        document = pymupdf.open(file_path)
        pages = []
        for index, page in enumerate(document):
            text = page.get_text().strip()
            if len(text) < 20:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                text = pytesseract.image_to_string(preprocess_image(image), config="--oem 3 --psm 6")
            pages.append(f"--- Page {index + 1} ---\n{text}")
        page_count = len(document)
        document.close()
    else:
        with Image.open(file_path) as image:
            pages = [pytesseract.image_to_string(preprocess_image(image), config="--oem 3 --psm 6")]
        page_count = 1
    return {"text": "\n\n".join(pages), "page_count": page_count, "status": "COMPLETED"}


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