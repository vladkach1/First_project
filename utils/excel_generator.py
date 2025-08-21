import os
import logging
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from config import COLOR_MAPPING, DEFAULT_CURRENCY

# Настройка логирования
logger = logging.getLogger("ExcelGenerator")

def apply_style(ws):
    """Применяет стили к листу Excel"""
    # Шрифт заголовков
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Стиль границ
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Применение стилей к заголовкам
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Применение стилей к данным
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border
            if cell.column_letter in ['B', 'C']:  # Наименование и Обозначение
                cell.alignment = Alignment(wrap_text=True)
    
    # Автонастройка ширины столбцов
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        
        adjusted_width = (max_length + 2) * 1.2
        ws.column_dimensions[column].width = adjusted_width

def create_search_report(equipment_data, scraped_data):
    """
    Создает первый отчет с результатами поиска
    
    :param equipment_data: Данные оборудования из PDF
    :param scraped_data: Результаты поиска на сайтах
    :return: Объект Workbook Excel
    """
    try:
        logger.info("Создание отчета поиска оборудования")
        
        # Создаем DataFrame
        report_data = []
        
        for i, item in enumerate(equipment_data):
            item_name = item['name']
            quantity = item['quantity']
            
            # Фильтруем результаты для текущего оборудования
            item_results = [r for r in scraped_data if similarity(r['name'], item_name) > 0.7]
            
            if not item_results:
                report_data.append({
                    '№': i+1,
                    'Наименование': item_name,
                    'Количество': quantity,
                    'Цена': 'Не найдено',
                    'Сайт': '',
                    'Статус': 'out_of_stock'
                })
                continue
            
            # Сортируем по цене (дешевле сначала)
            item_results.sort(key=lambda x: x['price'])
            
            # Выбираем лучший вариант
            best_offer = item_results[0]
            
            report_data.append({
                '№': i+1,
                'Наименование': item_name,
                'Количество': quantity,
                'Цена': f"{best_offer['price']} {DEFAULT_CURRENCY}",
                'Сайт': best_offer['site'],
                'Статус': best_offer['status']
            })
        
        df = pd.DataFrame(report_data)
        
        # Создаем Excel книгу
        wb = Workbook()
        ws = wb.active
        ws.title = "Результаты поиска"
        
        # Заголовки
        headers = list(df.columns)
        ws.append(headers)
        
        # Добавляем данные
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                
                # Раскрашиваем статус
                if c_idx == len(headers):  # Последний столбец
                    status = value
                    color = COLOR_MAPPING.get(status, 'FFFFFF')
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        
        # Применяем стили
        apply_style(ws)
        
        return wb
    except Exception as e:
        logger.error(f"Ошибка создания отчета поиска: {e}")
        raise RuntimeError("Ошибка генерации отчета поиска.")

def create_commercial_offer(equipment_data, scraped_data):
    """
    Создает коммерческое предложение в формате Excel
    
    :param equipment_data: Данные оборудования из PDF
    :param scraped_data: Результаты поиска на сайтах
    :return: Объект Workbook Excel
    """
    try:
        logger.info("Создание коммерческого предложения")
        
        # Создаем Excel книгу
        wb = Workbook()
        ws = wb.active
        ws.title = "Коммерческое предложение"
        
        # Заголовки таблицы
        headers = [
            '№', 
            'Наименование', 
            'Обозначение', 
            'Ед. изм.', 
            'Кол-во', 
            'Цена за ед.', 
            'Сумма, руб.'
        ]
        ws.append(headers)
        
        total_sum = 0
        
        # Добавляем данные
        for i, item in enumerate(equipment_data):
            item_name = item['name']
            quantity = item['quantity']
            
            # Ищем лучшую цену
            best_price = None
            item_results = [r for r in scraped_data if similarity(r['name'], item_name) > 0.7]
            
            if item_results:
                best_offer = min(item_results, key=lambda x: x['price'])
                best_price = best_offer['price']
            else:
                # Используем цену из PDF, если не нашли
                best_price = item['price']
            
            # Рассчитываем сумму
            total = best_price * quantity
            total_sum += total
            
            # Форматируем значения
            price_str = f"{best_price:.2f} {DEFAULT_CURRENCY}" if best_price else "Цена не найдена"
            total_str = f"{total:.2f} {DEFAULT_CURRENCY}" if best_price else "-"
            
            ws.append([
                i+1,
                item['name'],
                item['designation'],
                item['unit'],
                quantity,
                price_str,
                total_str
            ])
        
        # Добавляем итоговую строку
        ws.append([''] * 6 + [f"ИТОГО: {total_sum:.2f} {DEFAULT_CURRENCY}"])
        
        # Применяем стили
        apply_style(ws)
        
        # Настройка итоговой строки
        last_row = ws.max_row
        for col in range(1, 8):
            cell = ws.cell(row=last_row, column=col)
            if col == 7:
                cell.font = Font(bold=True, size=12)
                cell.alignment = Alignment(horizontal='right')
        
        return wb
    except Exception as e:
        logger.error(f"Ошибка создания коммерческого предложения: {e}")
        raise RuntimeError("Ошибка генерации коммерческого предложения.")