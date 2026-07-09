import pytesseract
from PIL import Image, ImageEnhance

import os
from dotenv import load_dotenv
load_dotenv()

pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")


def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess the image to enhance OCR accuracy: convert to grayscale, upscale if small, and enhance contrast/sharpness."""
    # Convert to grayscale
    image = image.convert('L')
    
    # Scale up if resolution is low (improves OCR for small text)
    w, h = image.size
    if w < 1000 and h < 1000:
        # Scale up by 2x only if the image is quite small
        image = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        
    # Enhance contrast (skip sharpening to avoid noise artifacts)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    
    return image


def reconstruct_text(data: dict) -> str:
    """Reconstruct text line-by-line using block, paragraph, and line numbers to preserve format and structure."""
    lines = []
    current_line_key = None
    current_words = []
    
    for i in range(len(data['text'])):
        word = data['text'][i]
        if data['level'][i] == 5 and word.strip():
            block = data['block_num'][i]
            par = data['par_num'][i]
            line = data['line_num'][i]
            key = (block, par, line)
            
            if key != current_line_key:
                if current_words:
                    lines.append(" ".join(current_words))
                current_words = [word]
                current_line_key = key
            else:
                current_words.append(word)
                
    if current_words:
        lines.append(" ".join(current_words))
        
    return "\n".join(lines)


def extract_from_image(file_path: str) -> tuple[str, float]:
    """Extract text from an image file using pytesseract with layout preservation and preprocessing."""
    try:
        orig_image = Image.open(file_path)
        w, h = orig_image.size
        
        # 1. Full image OCR (to process full scanned document pages)
        image_full = preprocess_image(orig_image)
        data_full = pytesseract.image_to_data(
            image_full,
            output_type=pytesseract.Output.DICT
        )
        text_full = reconstruct_text(data_full)
        conf_full = [int(c) for c in data_full["conf"] if str(c) != "-1"]
        
        # 2. Bottom strip OCR (to capture camera timestamps or edge overlays cleanly)
        bottom_box = (0, int(h * 0.78), w, h)
        image_bottom = orig_image.crop(bottom_box)
        image_bottom_processed = preprocess_image(image_bottom)
        data_bottom = pytesseract.image_to_data(
            image_bottom_processed,
            output_type=pytesseract.Output.DICT
        )
        text_bottom = reconstruct_text(data_bottom)
        conf_bottom = [int(c) for c in data_bottom["conf"] if str(c) != "-1"]
        
        # Combine texts and confidences
        all_texts = []
        if text_full.strip():
            all_texts.append(text_full.strip())
        if text_bottom.strip() and text_bottom.strip() not in text_full:
            all_texts.append(text_bottom.strip())
            
        combined_text = "\n".join(all_texts)
        all_confidences = conf_full + conf_bottom
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        return combined_text, round(avg_confidence, 2)

    except Exception as e:
        raise RuntimeError(f"Image OCR failed: {str(e)}")