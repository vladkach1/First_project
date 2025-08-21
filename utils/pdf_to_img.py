import os
import logging
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
from tqdm import tqdm

# Настройка логирования
logger = logging.getLogger("PDFtoImage")

def convert_pdf_to_images(pdf_path, output_dir):
    """
    Конвертирует PDF в серию изображений JPEG
    
    :param pdf_path: Путь к PDF файлу
    :param output_dir: Директория для сохранения изображений
    :return: Список путей к созданным изображениям
    """
    try:
        logger.info(f"Начало конвертации PDF: {pdf_path}")
        
        # Конвертируем PDF в изображения
        images = convert_from_path(pdf_path)
        
        img_paths = []
        for i, image in enumerate(tqdm(images, desc="Конвертация страниц")):
            img_path = os.path.join(output_dir, f'page_{i+1}.jpg')
            image.save(img_path, 'JPEG')
            img_paths.append(img_path)
            logger.debug(f"Сохранено изображение: {img_path}")
        
        logger.info(f"Успешно конвертировано {len(img_paths)} страниц")
        return img_paths
    
    except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as e:
        logger.error(f"Ошибка конвертации PDF: {e}")
        raise ValueError("Невозможно обработать PDF файл. Убедитесь, что файл не поврежден и имеет правильный формат.")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при конвертации PDF: {e}")
        raise RuntimeError("Произошла непредвиденная ошибка при обработке PDF файла.")