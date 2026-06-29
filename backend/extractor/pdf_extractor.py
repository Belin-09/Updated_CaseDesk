import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import os

from dotenv import load_dotenv
load_dotenv()

pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")

POPPLER_PATH = os.getenv("POPPLER_PATH")

def extract_from_digital_pdf(file_path: str) -> tuple[str, None]:
    """Extract text from a digital (selectable text) PDF using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise RuntimeError(f"pdfplumber failed: {str(e)}")
    return text.strip(), None


from extractor.image_extractor import preprocess_image, reconstruct_text

def extract_from_scanned_pdf(file_path: str) -> tuple[str, float]:
    """Extract text from a scanned PDF using pdf2image + tesseract with layout preservation and preprocessing."""
    text = ""
    confidences = []

    try:
        images = convert_from_path(file_path, dpi=300, poppler_path=POPPLER_PATH)
    except Exception as e:
        raise RuntimeError(f"pdf2image failed: {str(e)}")

    for image in images:
        try:
            # Preprocess page image prior to running Tesseract to optimize OCR accuracy
            processed_image = preprocess_image(image)

            data = pytesseract.image_to_data(
                processed_image,
                output_type=pytesseract.Output.DICT
            )

            # Reconstruct page text preserving line formatting and structure
            page_text = reconstruct_text(data)
            text += page_text + "\n"

            page_confidences = [
                int(c) for c in data["conf"] if str(c) != "-1"
            ]
            confidences.extend(page_confidences)

        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {str(e)}")

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text.strip(), round(avg_confidence, 2)


def is_digital_pdf(file_path: str) -> bool:
    """Check if PDF has selectable text (digital) or is scanned."""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    return True
    except:
        pass
    return False


def extract_from_pdf(file_path: str) -> tuple[str, float | None]:
    """
    Main PDF extraction function.
    Auto-detects digital vs scanned and uses the right method.
    Returns (text, ocr_confidence or None)
    """
    if is_digital_pdf(file_path):
        text, confidence = extract_from_digital_pdf(file_path)
        return text, confidence
    else:
        text, confidence = extract_from_scanned_pdf(file_path)
        return text, confidence