import re
import os
import logging
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from config import COLOR_MAPPING, DEFAULT_CURRENCY
from utils.text_analysis import similarity

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
        
        report_data = [] #Список подходящих по наименованию
        result = [] #Список подходящих по наименованиям и самых дешёвых


        # Создаем DataFrame
        #Выбираем самое дещёвое предложение
        for i, need_item in enumerate(equipment_data):

            report_data.clear()
            need_name = need_item['name']
            need_quantity = need_item['quantity']
            need_unit = need_item['unit']
            
            for item in scraped_data[i]:
                if similarity(item['name'],need_name) > 0.0001:
                    report_data.append({
                    '№': i+1,
                    'Наименование': item['name'],
                    'Количество': need_quantity,
                    'Ед. изм.': need_unit, 
                    'Цена': item['price'],
                    'Сайт': item['site'],
                    'Статус': item['status'] 
                    })
            report_data.sort(key=lambda x: x['Цена'])
            best_offer = report_data[0]
            result.append({
                    '№': i+1,
                    'Наименование': best_offer['Наименование'],
                    'Количество': need_quantity,
                    'Ед. изм.': need_unit, 
                    'Цена': best_offer['Цена'],
                    'Сайт': best_offer['Сайт'],
                    'Статус': best_offer['Статус'] 
                    })
        df = pd.DataFrame(result)

        #Создаём книгу ексель
        wb = Workbook()
        ws = wb.active
        ws.title = "Результаты поиска"

        #Заголовки
        headers = list(df.columns)
        ws.append(headers)

        #Заполняем даными
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
        
        report_data = [] #Список подходящих по наименованию
        result = [] #Список подходящих по наименованиям и самых дешёвых
        total_sum = 0


        # Создаем DataFrame
        #Выбираем самое дещёвое предложение
        for i, need_item in enumerate(equipment_data):

            report_data.clear()
            need_name = need_item['name']
            need_quantity = need_item['quantity']
            need_unit = need_item['unit']
            
            for item in scraped_data[i]:
                if similarity(item['name'],need_name) > 0.0001:
                    report_data.append({
                    '№': i+1, 
                    'Наименование': item['name'], 
                    'Обозначение': "1", 
                    'Ед. изм.': need_unit, 
                    'Кол-во': need_quantity, 
                    'Цена за ед.': item['price'], 
                    'Сумма, руб.': item['price']*need_quantity
                    })
            report_data.sort(key=lambda x: x['Цена за ед.'])
            best_offer = report_data[0]
            result.append({
                    '№': i+1, 
                    'Наименование': best_offer['Наименование'], 
                    'Обозначение': "1", 
                    'Ед. изм.': need_unit, 
                    'Кол-во': need_quantity, 
                    'Цена за ед.': best_offer['Цена за ед.'], 
                    'Сумма, руб.': best_offer['Цена за ед.']*need_quantity
                    })
            total_sum += best_offer['Сумма, руб.']
        df = pd.DataFrame(result)

        #Создаём книгу ексель
        wb = Workbook()
        ws = wb.active
        ws.title = "Результаты поиска"

        #Заголовки
        headers = list(df.columns)
        ws.append(headers)

        #Заполняем даными
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                # Раскрашиваем статус
                if c_idx == len(headers):  # Последний столбец
                    status = value
                    color = COLOR_MAPPING.get(status, 'FFFFFF')
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

        # Добавляем итоговую строку
        ws.append(['']+["ИТОГО"]+['']*4+[f"{total_sum:.2f}"])
        ws.append(['']+["Расходные материалы"]+['']*4+[f"{total_sum:.2f}"])
        ws.append(['']+["Итого оборудование и расходные материалы"]+['']*4+[f"{total_sum:.2f}"])
        ws.append(['']+["Монтажные работы"]+['']*4+[f"{total_sum:.2f}"])
        ws.append(['']+["ВСЕГО С НДС 20%:"]+['']*4+[f"{total_sum:.2f}"])
        # Применяем стили
        apply_style(ws)

        return wb
    
    except Exception as e:

        logger.error(f"Ошибка создания коммерческого предложения: {e}")
        raise RuntimeError("Ошибка генерации коммерческого предложения.")