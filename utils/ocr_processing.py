import os
import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError
from tqdm import tqdm
from config import TESSERACT_PATH, OCR_LANGUAGE

# Настройка пути к Tesseract
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Настройка логирования
logger = logging.getLogger("OCRProcessing")

def preprocess_image(image_path):
    """
    Предварительная обработка изображения для улучшения распознавания
    
    :param image_path: Путь к изображению
    :return: Обработанное изображение PIL
    """
    try:
        # Открываем изображение
        img = Image.open(image_path)
        
        # Конвертируем в оттенки серого
        img = img.convert('L')
        
        # Увеличиваем контраст
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        # Применяем легкое размытие для уменьшения шума
        img = img.filter(ImageFilter.MedianFilter(3))
        
        # Бинаризация (пороговая обработка)
        # img = img.point(lambda x: 0 if x < 140 else 255)
        
        return img
    except UnidentifiedImageError:
        logger.error(f"Невозможно идентифицировать изображение: {image_path}")
        raise ValueError("Неподдерживаемый формат изображения.")
    except Exception as e:
        logger.error(f"Ошибка предварительной обработки изображения: {e}")
        raise RuntimeError("Ошибка обработки изображения.")

def extract_text_from_image(image_path):
    """
    Извлекает текст из изображения с помощью OCR
    
    :param image_path: Путь к изображению
    :return: Распознанный текст
    """
    try:
        logger.info(f"Обработка изображения: {image_path}")
        
        # Предварительная обработка изображения
        img = preprocess_image(image_path)
        
        # Распознавание текста
        text = pytesseract.image_to_string(
            img, 
            lang=OCR_LANGUAGE,
            config='--psm 6 -c preserve_interword_spaces=1'
        )
        
        logger.debug(f"Распознан текст длиной {len(text)} символов")
        return text
    except Exception as e:
        logger.error(f"Ошибка OCR: {e}")
        raise RuntimeError("Ошибка распознавания текста.")