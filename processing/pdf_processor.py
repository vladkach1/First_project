import re
import logging
import pdfplumber
import camelot
from pathlib import Path
from typing import List, Dict
from config import logger
from .ocr_processor import extract_text_with_ocr
from .cid_decoder import decode_cid_text
def process_table(table: list, page_num: int) -> List[Dict]:
    equipment = []
    headers = [decode_cid_text(str(cell).strip()).lower() if cell else "" for cell in table[0]]
    
    # Определение индексов колонок (исправленная версия)
    name_col = 0
    qty_col = None
    unit_col = None
    
    for i, h in enumerate(headers):
        if "наименование" in h:
            name_col = i
        if "количество" in h:
            qty_col = i
        if "ед. изм" in h:
            unit_col = i
    
    for row in table[1:]:
        if not any(row): 
            continue
        
        quantity = 1
        if qty_col is not None and row[qty_col] and str(row[qty_col]).strip():
            try:
                qty_str = str(row[qty_col]).replace(",", ".")
                quantity = int(float(qty_str))
            except (ValueError, TypeError):
                quantity = 1
        
        item = {
            "name": decode_cid_text(str(row[name_col]).strip()) if name_col is not None and row[name_col] else "Неизвестное оборудование",
            "quantity": quantity,
            "unit": str(row[unit_col]).lower().strip() if unit_col is not None and row[unit_col] else "шт.",
            "source_page": page_num
        }
        equipment.append(item)
    
    return equipment

def find_equipment_in_text(text: str, page_num: int) -> List[Dict]:
    """Поиск оборудования в тексте"""
    equipment = []
    
    # Паттерны для поиска оборудования
    patterns = [
        r"(?P<name>[А-ЯA-Z].+?)\s+(?P<quantity>\d+)\s*(?P<unit>шт|м|кг|компл|л|см)\b",
        r"(?P<name>[А-ЯA-Z][^0-9\n]+?)\s+-\s+(?P<quantity>\d+)",
        r"^(?P<name>[А-ЯA-Z].+?)\s+(?P<quantity>\d+)$"
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            equipment.append({
                "name": match.group("name").strip(),
                "quantity": int(match.group("quantity")),
                "unit": match.groupdict().get("unit", "шт."),
                "source_page": page_num
            })
    
    return equipment

def process_camelot_table(table) -> List[Dict]:
    """Обработка таблиц из camelot"""
    equipment = []
    df = table.df
    headers = [str(cell).strip().lower() for cell in df.iloc[0]]
    
    # Определение индексов колонок (исправленная версия)
    name_col = 0
    qty_col = None
    unit_col = None
    
    for i, h in enumerate(headers):
        if "наименование" in h:
            name_col = i
        if "количество" in h:
            qty_col = i
        if "ед. изм" in h:
            unit_col = i
    
    for _, row in df.iloc[1:].iterrows():
        if not any(row.values): 
            continue
        
        quantity = 1
        if qty_col is not None and row[qty_col] and str(row[qty_col]).strip():
            try:
                qty_str = str(row[qty_col]).replace(",", ".")
                quantity = int(float(qty_str))
            except (ValueError, TypeError):
                quantity = 1
        
        item = {
            "name": str(row[name_col]).strip() if name_col is not None and row[name_col] else "Неизвестное оборудование",
            "quantity": quantity,
            "unit": str(row[unit_col]).lower().strip() if unit_col is not None and row[unit_col] else "шт.",
            "source_page": table.page
        }
        equipment.append(item)
    
    return equipment

def process_pdf(pdf_path: Path, output_path: Path, user_id: int):
    """Основной процесс обработки PDF"""
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
                if table.parsing_report["accuracy"] > 70:
                    equipment.extend(process_camelot_table(table))
        except Exception as e:
            logger.warning(f"Ошибка camelot: {e}")

        # Этап 2: Обработка с помощью pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text() or ""
                    
                    if not text.strip() or len(text.strip()) < 50:
                        text = extract_text_with_ocr(pdf_path, page_num)
                    
                    # Обработка таблиц pdfplumber
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text"
                    })
                    
                    for table in tables:
                        equipment.extend(process_table(table, page_num))
                    
                    # Поиск в тексте
                    equipment.extend(find_equipment_in_text(text, page_num))
                    
                except Exception as e:
                    logger.error(f"Ошибка на странице {page_num}: {e}")
        
        if not equipment:
            raise ValueError("Не найдено оборудования в документе")
        
        # Анализ и генерация отчета
        from .equipment_analyzer import analyze_equipment
        from .excel_generator import generate_excel_report
        generate_excel_report(analyze_equipment(equipment), output_path)
        logger.info(f"Отчет сгенерирован: {output_path}")
    
    except Exception as e:
        logger.exception("Ошибка обработки PDF")
        raise