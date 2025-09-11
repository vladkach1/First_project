import fitz  # PyMuPDF

def crop_pdf_to_table(input_path, output_path, crop_coords):
    """
    Обрезает каждую страницу PDF до указанной области и сохраняет результат.
    
    :param input_path: Путь к исходному PDF-файлу
    :param output_path: Путь для сохранения обрезанного PDF
    :param crop_coords: Кортеж (x0, y0, x1, y1) с координатами области для обрезки
    """
    doc = fitz.open(input_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page.set_cropbox(fitz.Rect(crop_coords))
    
    doc.save(output_path)
    doc.close()



# Пример использования
if __name__ == "__main__":
    input_pdf = "3.pdf"
    output_pdf = "output_cropped.pdf"
    
    # Координаты для обрезки (x0, y0, x1, y1) в пунктах
    # Подобраны специально для вашего PDF с таблицей оборудования
    crop_coords = (935, 105, 990, 670)
    
    # Анализируем координаты (раскомментируйте при необходимости)
    # analyze_pdf_coordinates(input_pdf)
    
    # Обрезаем PDF
    crop_pdf_to_table(input_pdf, output_pdf, crop_coords)
    print(f"PDF успешно обрезана и сохранена как {output_pdf}")