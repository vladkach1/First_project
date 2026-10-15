import pdfplumber
from PIL import Image
import re
import os
import fitz
import io
import logging
import pandas as pd
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logger = logging.getLogger("PdfToImg")

# Инициализация OpenRouter
_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
_OR_MODEL = "google/gemma-3-12b-it:free"

_OCR_PROMPT = (
    "Извлеки весь текст с изображения построчно. "
    "Сохраняй оригинальное написание: кириллицу пиши кириллицей, "
    "латиницу — латиницей (артикулы, марки, аббревиатуры). "
    "Не добавляй пояснений, только текст."
)


def crop_page_to_region(pdf_path, page_num, crop_region):
    """Обрезает страницу PDF до указанной области и возвращает изображение"""
    try:
        doc = fitz.open(pdf_path)
        if doc.is_repaired:
            logger.warning(f"PDF восстановлен из повреждённого состояния: {pdf_path}")
        page = doc[page_num]

        rect = fitz.Rect(crop_region)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)

        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))

        doc.close()
        return image

    except Exception as e:
        logger.error(f"Ошибка обрезки страницы {page_num}: {e}")
        return None


def _ocr_image(image):
    """Извлекает текст из PIL Image через OpenRouter Vision"""
    try:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = __import__("base64").b64encode(buf.getvalue()).decode()

        response = _openrouter.chat.completions.create(
            model=_OR_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка OpenRouter OCR: {e}")
        return ""


def extract_text_from_region(pdf_path, page_num, crop_region):
    """Извлекает текст из указанной области страницы"""
    results = {
        'text_lines': [],
        'tables': [],
        'used_ocr': False
    }

    # Сначала пробуем извлечь через pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num < len(pdf.pages):
                page = pdf.pages[page_num]

                # Обрезаем страницу до нужной области
                cropped_page = page.within_bbox(crop_region)

                # Пробуем извлечь таблицы
                tables = cropped_page.extract_tables()
                if tables and any(any(cell for cell in row if cell) for table in tables for row in table):
                    for table in tables:
                        cleaned_table = []
                        for row in table:
                            cleaned_row = [re.sub(r'\s+', ' ', str(cell).replace('\n', ' ')).strip() if cell else "" for cell in row]
                            cleaned_table.append(cleaned_row)
                        results['tables'].extend(cleaned_table)

                # Извлекаем обычный текст
                text = cropped_page.extract_text()
                if text:
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    results['text_lines'].extend(lines)

                # Проверяем наличие (cid:) символов
                if any('(cid:' in line for line in results['text_lines']):
                    results['used_ocr'] = True
                    results['text_lines'] = []  # Очищаем для переизвлечения через OCR

    except Exception as e:
        logger.error(f"Ошибка pdfplumber на странице {page_num}: {e}")
        results['used_ocr'] = True

    # Если нужно использовать OCR или pdfplumber не сработал
    if results['used_ocr'] or (not results['text_lines'] and not results['tables']):
        image = crop_page_to_region(pdf_path, page_num, crop_region)
        if image:
            # Извлекаем текст через RapidOCR
            ocr_text = _ocr_image(image)
            lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
            results['text_lines'].extend(lines)
            results['used_ocr'] = True

    return results


def analyze_pdf_region(pdf_path, crop_region):
    """Анализирует только указанную область PDF"""
    results = []

    # Получаем количество страниц через fitz (PyMuPDF)
    doc = fitz.open(pdf_path)
    if doc.is_repaired:
        logger.warning(f"PDF восстановлен из повреждённого состояния: {pdf_path}")
    total_pages = len(doc)
    doc.close()

    for page_num in range(total_pages):
        logger.info(f"Обработка страницы {page_num + 1}/{total_pages}")

        page_result = {
            'page_number': page_num + 1,
            'region_data': extract_text_from_region(pdf_path, page_num, crop_region)
        }

        results.append(page_result)

    return results


def print_region_results(results):
    """Красивый вывод результатов из указанной области"""
    for page in results:
        print(f"\n{'='*80}")
        print(f"СТРАНИЦА {page['page_number']} - ОБЛАСТЬ (113,30,995,670)")
        print(f"{'='*80}")

        data = page['region_data']

        if data['used_ocr']:
            print("(Текст извлечен через OCR)")

        if data['tables']:
            print("\nТАБЛИЦЫ В ОБЛАСТИ:")
            print("-" * 50)
            for i, row in enumerate(data['tables']):
                if any(cell.strip() for cell in row):  # Пропускаем пустые строки
                    row_display = " | ".join([f"{cell:<25}" for cell in row])
                    print(f"{i+1:3d}: {row_display}")

        if data['text_lines']:
            print("\nТЕКСТ В ОБЛАСТИ (построчно):")
            print("-" * 50)
            for i, line in enumerate(data['text_lines']):
                print(f"{i+1:3d}: {line}")


def export_region_to_file(results, output_file):
    """Экспорт результатов области в текстовый файл"""
    result_list = []
    with open(output_file, 'w', encoding='utf-8') as f:
        for page in results:
            f.write(f"\n{'='*80}\n")
            f.write(f"СТРАНИЦА {page['page_number']} - ОБЛАСТЬ (113,30,995,670)\n")
            f.write(f"{'='*80}\n")

            data = page['region_data']

            if data['used_ocr']:
                f.write("(Текст извлечен через OCR)\n")

            if data['tables']:
                f.write("\nТАБЛИЦЫ В ОБЛАСТИ:\n")
                f.write("-" * 50 + "\n")
                for i, row in enumerate(data['tables']):
                    if any(cell.strip() for cell in row):
                        row_text = " | ".join(row)
                        result_list.append(f"{row_text}")

            if data['text_lines']:
                f.write("\nТЕКСТ В ОБЛАСТИ (построчно):\n")
                f.write("-" * 50 + "\n")
                for i, line in enumerate(data['text_lines']):
                    result_list.append(f"{line}")
    return result_list


def parse_excel_to_structure(file_path):
    """
    Безопасный парсер без использования регулярных выражений
    """
    result = []

    excel_file = pd.ExcelFile(file_path)

    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)

        for index, row in df.iterrows():
            # Пропускаем строки с недостаточными данными
            if any(pd.isna(row.iloc[i]) for i in [1]):
                continue

            # Преобразуем все в строки
            if not (any(pd.isna(row.iloc[i]) for i in [1, 3, 4])):
                name = str(row.iloc[1]).strip()
                model = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ''
                unit = str(row.iloc[3]).strip()
                quantity = row.iloc[4]
                if (unit not in ['', ' '] and
                    not pd.isna(quantity) and
                    quantity != 0):

                    try:
                        quantity_num = float(quantity)
                        # Объединяем название и модель, убираем nan
                        combined = (name + " " + model).strip() if model and model.lower() != 'nan' else name
                        # Убираем задублированные части (когда название повторяется дважды в ячейке)
                        # Ищем повторяющийся префикс: "A B C A B C X" -> "A B C X"
                        words = combined.split()
                        n = len(words)
                        deduped = False
                        for split in range(2, n // 2 + 1):
                            prefix = words[:split]
                            if words[split:split + split] == prefix:
                                combined = ' '.join(prefix + words[split * 2:])
                                deduped = True
                                break
                        result.append([combined, str(unit), str(quantity_num)])
                    except (ValueError, TypeError):
                        continue
            else:
                name = str(row.iloc[1]).strip()
                result.append([str(name)])

    return result
