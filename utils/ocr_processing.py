import logging
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError
import numpy as np
from rapidocr_onnxruntime import RapidOCR

# Настройка логирования
logger = logging.getLogger("OCRProcessing")

# Глобальный экземпляр OCR (инициализируется один раз, переиспользуется)
_ocr_engine = RapidOCR()


def preprocess_image(image_path):
    """
    Предварительная обработка изображения для улучшения распознавания

    :param image_path: Путь к изображению или PIL Image
    :return: Обработанное изображение PIL
    """
    try:
        if isinstance(image_path, Image.Image):
            img = image_path
        else:
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

        return img
    except UnidentifiedImageError:
        logger.error(f"Невозможно идентифицировать изображение: {image_path}")
        raise ValueError("Неподдерживаемый формат изображения.")
    except Exception as e:
        logger.error(f"Ошибка предварительной обработки изображения: {e}")
        raise RuntimeError("Ошибка обработки изображения.")


def extract_text_from_image(image_input):
    """
    Извлекает текст из изображения с помощью RapidOCR.

    :param image_input: Путь к изображению (str) или PIL Image
    :return: Распознанный текст
    """
    try:
        logger.info(f"Обработка изображения через RapidOCR")

        # Предварительная обработка
        img = preprocess_image(image_input)

        # RapidOCR принимает numpy array
        img_array = np.array(img)

        result, elapse = _ocr_engine(img_array)

        if not result:
            logger.debug("RapidOCR не распознал текст")
            return ""

        # result — список [bbox, text, confidence], собираем текст
        lines = [item[1] for item in result]
        text = "\n".join(lines)

        logger.debug(f"Распознан текст длиной {len(text)} символов за {elapse}")
        return text
    except Exception as e:
        logger.error(f"Ошибка OCR: {e}")
        raise RuntimeError("Ошибка распознавания текста.")
