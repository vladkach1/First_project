from pdf2image import convert_from_path
import fitz  # PyMuPDF
import os

def crop_pdf_to_table(input_path, output_path, crop_coords):
    """
    Обрезает каждую страницу PDF до указанной области и сохраняет результат.
    
    :param input_path: Путь к исходному PDF-файлу
    :param output_path: Путь для сохранения обрезанного PDF
    :param crop_coords: Кортеж (x0, y0, x1, y1) с координатами области для обрезки
    """
    # Открываем исходный PDF
    doc = fitz.open(input_path)
    
    # Создаем новый PDF документ для обрезанных страниц
    new_doc = fitz.open()
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Создаем новую страницу в целевом документе
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        
        # Определяем область обрезки
        crop_rect = fitz.Rect(crop_coords)
        
        # Копируем только обрезанную область со старой страницы на новую
        new_page.show_pdf_page(
            new_page.rect,
            doc,
            page_num,
            clip=crop_rect
        )
    
    # Сохраняем обрезанный PDF
    new_doc.save(output_path)
    new_doc.close()
    doc.close()

# Основной код
pdf_path = 'qwer.pdf'  # Замените на путь к вашему PDF файлу
cropped_pdf_path = 'test.pdf'  # Путь для сохранения обрезанного PDF
crop_coords_name = (113, 15, 482, 37)
#105 129
#82 106
#60 83
#37 60
#15 37
#-24 от этого конца  +23.3 от прошлого конца
#28 строк пока максимум
#.  37 конец 1 стоки
#.  

# Обрезаем PDF
crop_pdf_to_table(pdf_path, cropped_pdf_path, crop_coords_name)

# Конвертируем ОБРЕЗАННЫЙ PDF в изображения
images = convert_from_path(cropped_pdf_path)

# Сохраняем изображения
for i, image in enumerate(images):
    image.save(f'page_{i}.png', 'PNG')

print("Готово! Обрезанные изображения сохранены.")