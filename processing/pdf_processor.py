import re
import pdfplumber
import logging
import camelot
from pathlib import Path
from typing import List, Dict
from config import logger
from .ocr_processor import extract_text_with_ocr

def process_pdf(pdf_path: Path, output_path: Path, user_id: int):
    """Основной процесс обработки PDF с использованием camelot"""
    logger.info(f"Начата обработка PDF: {pdf_path}")
    equipment = []
    
    try:
        # Этап 1: Обработка с помощью camelot (для таблиц с границами)
        try:
            tables = camelot.read_pdf(
                str(pdf_path),
                pages="all",
                flavor="lattice",
                strip_text="\n",
                suppress_stdout=True
            )
            
            for table in tables:
                if table.parsing_report["accuracy"] > 70:  # Фильтр по точности
                    equipment.extend(process_camelot_table(table))
        except Exception as e:
            logger.warning(f"Ошибка camelot: {e}")
        
        # Этап 2: Обработка с помощью pdfplumber (для текста и таблиц без границ)
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text() or ""
                    
                    # Если текст не извлекается, используем OCR
                    if not text.strip() or len(text.strip()) < 50:
                        logger.warning(f"Страница {page_num} содержит мало текста, используется OCR")
                        text = extract_text_with_ocr(pdf_path, page_num)
                    
                    # Обработка таблиц pdfplumber
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text"
                    })
                    
                    for table in tables:
                        equipment.extend(process_table(table, page_num))
                    
                    # Поиск оборудования в тексте
                    equipment.extend(find_equipment_in_text(text, page_num))
                    
                except Exception as e:
                    logger.error(f"Ошибка на странице {page_num}: {e}")
        
        # Этап 3: Резервные методы (если ничего не найдено)
        if not equipment:
            logger.warning("Оборудование не найдено, используется расширенный поиск")
            equipment = extended_equipment_search(pdf_path)
        
        if not equipment:
            raise ValueError("Не найдено оборудования в документе")
        
        # Анализ и генерация отчета
        from .equipment_analyzer import analyze_equipment
        equipment = analyze_equipment(equipment)
        
        from .excel_generator import generate_excel_report
        generate_excel_report(equipment, output_path)
        logger.info(f"Отчет сгенерирован: {output_path}")
    
    except Exception as e:
        logger.exception("Ошибка обработки PDF")
        raise

def process_camelot_table(table) -> List[Dict]:
    """Обработка таблиц из camelot"""
    equipment = []
    df = table.df
    headers = [str(cell).strip().lower() for cell in df.iloc[0]]
    
    # Определение колонок
    name_col = next((i for i, h in enumerate(headers) if "наименование" in h), 0)
    qty_col = next((i for i, h in enumerate(headers) if "количество" in h), None)
    unit_col = next((i for i, h in enumerate(headers) if "ед. изм" in h), None)
    
    for _, row in df.iloc[1:].iterrows():
        if not any(row.values): continue
        
        item = {
            "name": str(row[name_col]),
            "quantity": try_parse_quantity(row[qty_col] if qty_col else "1"),
            "unit": str(row[unit_col]).lower() if unit_col else "шт.",
            "source_page": table.page
        }
        equipment.append(item)
    
    return equipment

def try_parse_quantity(value: str) -> int:
    """Попытка преобразования количества"""
    try:
        return int(float(str(value).replace(",", ".")))
    except:
        return 1

def extended_equipment_search(pdf_path: Path) -> List[Dict]:
    """Расширенный поиск оборудования через OCR"""
    from .ocr_processor import extract_text_with_ocr
    full_text = extract_text_with_ocr(pdf_path)
    equipment = []
    
    # Поиск специфичных паттернов оборудования
    patterns = [
        r"(ВЗ–РиБСК-\d+|РН-\d+[А-Я]?|ИП \d+-\d+)",
        r"([А-Я]{2,}-\d+[А-Я]?)",
        r"(Кабель [\w\d-]+ \d+x\d+\.\d+)"
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, full_text):
            equipment.append({
                "name": match.group(),
                "quantity": 1,
                "unit": "шт.",
                "source_page": "OCR"
            })
    
    return equipment