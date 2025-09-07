import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os

# Установите путь к Tesseract OCR (если нужно)
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

def pdf_to_text_ocr(pdf_path):
    try:
        # Конвертируем PDF в изображения
        images = convert_from_path(pdf_path, dpi=300)
        
        text = ""
        for i, image in enumerate(images):
            # Сохраняем временное изображение
            image_path = f"temp_page_{i}.png"
            image.save(image_path, 'PNG')
            
            # OCR с русским языком
            page_text = pytesseract.image_to_string(Image.open(image_path), lang='rus+eng')
            text += f"\n=== Страница {i+1} ===\n{page_text}\n"
            
            # Удаляем временный файл
            os.remove(image_path)
        
        return text
    
    except Exception as e:
        return f"Ошибка: {str(e)}"

# Основной код
if __name__ == "__main__":
    pdf_path = '1.pdf'
    text = pdf_to_text_ocr(pdf_path)
    
    # Вывод с правильной кодировкой
    try:
        print(text.encode('utf-8', errors='ignore').decode('utf-8'))
    except:
        print(text)