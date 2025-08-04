import os
import logging
import pytesseract
from pdf2image import convert_from_path
from config import OCR_ENABLED, OCR_LANGUAGES, logger
from pathlib import Path

def extract_text_with_ocr(pdf_path: Path) -> str:
    """Извлечение текста из PDF с помощью OCR"""
    if not OCR_ENABLED:
        logger.warning("OCR запрошен, но отключен в конфигурации")
        return ""
    
    try:
        logger.info(f"Начато распознавание текста для {pdf_path}")
        
        # Конвертация PDF в изображения
        images = convert_from_path(
            pdf_path=pdf_path,
            dpi=300,
            thread_count=4,
            fmt='jpeg',
            poppler_path=os.getenv('POPPLER_PATH')
        )
        
        # Распознавание текста
        full_text = ""
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(
                image, 
                lang=OCR_LANGUAGES,
                config='--psm 6 --oem 3'  # Предполагаем единый блок текста
            )
            full_text += f"\n\n--- Страница {i+1} ---\n\n{text}"
            logger.debug(f"Страница {i+1} распознана")
        
        logger.info(f"Распознано {len(images)} страниц, {len(full_text)} символов")
        return full_text
    
    except Exception as e:
        logger.error(f"Ошибка OCR: {e}")
        return ""