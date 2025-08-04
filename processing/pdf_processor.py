import re
import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict
from config import logger
from .ocr_processor import extract_text_with_ocr

def process_pdf(pdf_path: Path, output_path: Path, user_id: int):
    """Основной процесс обработки PDF"""
    logger.info(f"Начата обработка PDF: {pdf_path}")
    equipment = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Документ содержит {total_pages} страниц")
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # Извлечение текста
                    text = page.extract_text() or ""
                    
                    # Проверка на сканированный документ
                    if not text.strip() or len(text.strip()) < 50:
                        logger.warning(f"Страница {page_num} содержит мало текста, используется OCR")
                        text = extract_text_with_ocr(pdf_path)
                    
                    # Обработка таблиц
                    if "Наименование" in text and "техническая характеристика" in text:
                        table = page.extract_table()
                        if table:
                            equipment.extend(process_table(table, page_num))
                    
                    # Обработка кабелей
                    cable_matches = re.findall(r"([A-Z0-9-]+\s+[0-9x.]+[A-Z]+)", text)
                    for cable in cable_matches:
                        equipment.append({
                            "name": cable,
                            "quantity": 100,  # Типовая длина
                            "unit": "м",
                            "source_page": page_num
                        })
                    
                    logger.debug(f"Страница {page_num}/{total_pages} обработана")
                
                except Exception as e:
                    logger.error(f"Ошибка на странице {page_num}: {e}")
                    continue
        
        logger.info(f"Извлечено {len(equipment)} позиций оборудования")
        
        if not equipment:
            raise ValueError("Не найдено оборудования в документе")
        
        # Анализ оборудования
        from .equipment_analyzer import analyze_equipment
        equipment = analyze_equipment(equipment)
        
        # Генерация отчета
        from .excel_generator import generate_excel_report
        generate_excel_report(equipment, output_path)
        logger.info(f"Отчет сгенерирован: {output_path}")
    
    except Exception as e:
        logger.exception("Ошибка обработки PDF")
        raise