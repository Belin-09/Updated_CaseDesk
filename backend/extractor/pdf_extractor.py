import pdfplumber
import pytesseract
from pdf2image import convert_from_path, pdfinfo_from_path
import os
from concurrent.futures import ThreadPoolExecutor

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

def _process_single_page(image, page_num):
    try:
        processed_image = preprocess_image(image)
        data = pytesseract.image_to_data(
            processed_image,
            output_type=pytesseract.Output.DICT
        )
        page_text = reconstruct_text(data)
        page_confidences = [
            int(c) for c in data["conf"] if str(c) != "-1"
        ]
        return page_num, page_text, page_confidences
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed on page {page_num}: {str(e)}")

def extract_from_scanned_pdf(file_path: str) -> tuple[str, float]:
    """Extract text from a scanned PDF using pdf2image + tesseract with layout preservation and preprocessing."""
    try:
        # Batch convert all pages to images using native poppler threads
        images = convert_from_path(
            file_path,
            dpi=150,
            poppler_path=POPPLER_PATH,
            thread_count=4
        )
    except Exception as e:
        raise RuntimeError(f"convert_from_path failed: {str(e)}")

    results = [None] * len(images)
    
    # Process images concurrently using threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_process_single_page, image, idx + 1): idx 
            for idx, image in enumerate(images)
        }
        
        for future in futures:
            idx = futures[future]
            try:
                _, page_text, page_confidences = future.result()
                results[idx] = (page_text, page_confidences)
            except Exception as e:
                raise e

    text = ""
    confidences = []
    
    for res in results:
        if res:
            page_text, page_confs = res
            if page_text:
                text += page_text + "\n"
            confidences.extend(page_confs)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text.strip(), round(avg_confidence, 2)


def extract_from_pdf(file_path: str) -> tuple[str, float | None]:
    """
    Main PDF extraction function.
    Auto-detects digital vs scanned and uses the right method.
    Returns (text, ocr_confidence or None)
    """
    try:
        is_digital = False
        digital_text = ""
        
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    is_digital = True
                    
                if page_text:
                    digital_text += page_text + "\n"
                    
                # If we've checked 3 pages and found no text, assume it's scanned
                if not is_digital and i >= 2:
                    break
                    
            if is_digital:
                return digital_text.strip(), None
                
    except Exception:
        pass  # Fallback to OCR if pdfplumber fails
        
    # If no selectable text was found, or an error occurred, fall back to OCR
    return extract_from_scanned_pdf(file_path)