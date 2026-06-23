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
from openpyxl.drawing.image import Image

# Настройка логирования
logger = logging.getLogger("ExcelGenerator")

# Путь к картинке шапки — относительно корня проекта
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HEADER_IMAGE_PATH = os.path.join(_PROJECT_ROOT, "asets", "Head.jpg")


def apply_style(ws):
    """Применяет стили к листу Excel"""
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border
            if cell.column_letter in ['B', 'C']:
                cell.alignment = Alignment(wrap_text=True)

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2) * 1.2
        ws.column_dimensions[column].width = adjusted_width


def _find_best_offer(need_item, site_results):
    """
    Находит лучшее предложение для позиции из результатов поиска.

    :param need_item: dict с 'name', 'quantity', 'unit'
    :param site_results: список результатов скрапинга для этой позиции
    :return: (best_offer_dict, count) или (None, 1)
    """
    need_name = need_item['name']
    need_unit = need_item['unit']
    candidates = []

    for item in site_results:
        # Определяем кратность упаковки
        count = 1
        if len(need_unit) > 1:
            escaped_unit = re.escape(need_unit[:-1])
            pattern = rf'\((\d+)\s*{escaped_unit}\)'
            match = re.search(pattern, item['name'])
            if match:
                count = int(match.group(1))

        coff = similarity(need_name, item['name'])
        candidates.append({
            'item': item,
            'score': coff[0],
            'extra_words': coff[1],
            'count': count
        })

    if not candidates:
        return None, 1

    # Сортируем: similarity desc → extra_words asc → price desc
    candidates.sort(key=lambda x: (-x['score'], x['extra_words'], -x['item']['price']))

    best = candidates[0]
    return best, best['count']


def create_search_report(equipment_data, scraped_data):
    """
    Создает отчет с результатами поиска.

    :param equipment_data: Данные оборудования из PDF/Excel
    :param scraped_data: Результаты поиска на сайтах
    :return: Workbook или None
    """
    try:
        if not equipment_data or not scraped_data:
            logger.warning("Пустые входные данные")
            return None

        logger.info("Создание отчета поиска оборудования")
        result = []

        for i, need_item in enumerate(equipment_data):
            if i >= len(scraped_data) or not scraped_data[i]:
                logger.warning(f"Нет данных поиска для '{need_item['name']}'")
                continue

            best, count = _find_best_offer(need_item, scraped_data[i])
            if best is None:
                logger.warning(f"Не найдено предложений для '{need_item['name']}'")
                continue

            result.append({
                '№': i + 1,
                'Наименование': best['item']['name'],
                'Количество': need_item['quantity'] / count,
                'Ед. изм.': need_item['unit'],
                'Цена': best['item']['price'],
                'Сайт': best['item']['site'],
                'Коэффициент совпадения': round(best['score'], 3),
                'Запрос': need_item['name'],
                'Лишних слов': best['extra_words'],
                'Статус': best['item']['status']
            })

        if not result:
            logger.warning("Не найдено ни одного подходящего предложения")
            return None

        df = pd.DataFrame(result)
        wb = Workbook()
        ws = wb.active
        ws.title = "Результаты поиска"

        START_ROW = 12

        headers = list(df.columns)
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=START_ROW, column=col_idx, value=header)

        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), START_ROW + 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if c_idx == len(headers):  # Последний столбец — Статус
                    status = value
                    color = COLOR_MAPPING.get(status, 'FFA500')
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

        apply_style(ws)
        return wb

    except Exception as e:
        logger.error(f"Ошибка создания отчета поиска: {e}", exc_info=True)
        return None


def create_commercial_offer(equipment_data, scraped_data, name_data):
    """
    Создает коммерческое предложение в формате Excel.

    :param equipment_data: Данные оборудования из PDF/Excel
    :param scraped_data: Результаты поиска на сайтах
    :param name_data: Список всех наименований (включая заголовки разделов)
    :return: Workbook или None
    """
    try:
        logger.info("Создание коммерческого предложения")
        result = []
        total_sum = 0
        shift = 0

        for i, need_item in enumerate(equipment_data):
            # Вставляем строки-заголовки разделов (без цены)
            while (i + shift) < len(name_data) and name_data[i + shift] != need_item['name']:
                result.append({
                    '№': i + 1,
                    'Наименование': name_data[i + shift],
                    'Ед. изм.': "",
                    'Кол-во': "",
                    'Цена за ед.': "",
                    'Сумма, руб.': ""
                })
                shift += 1

            if i >= len(scraped_data) or not scraped_data[i]:
                # Нет результатов — вставляем позицию без цены
                result.append({
                    '№': i + 1,
                    'Наименование': need_item['name'],
                    'Ед. изм.': need_item['unit'],
                    'Кол-во': need_item['quantity'],
                    'Цена за ед.': 0,
                    'Сумма, руб.': 0
                })
                continue

            best, count = _find_best_offer(need_item, scraped_data[i])
            if best is None:
                result.append({
                    '№': i + 1,
                    'Наименование': need_item['name'],
                    'Ед. изм.': need_item['unit'],
                    'Кол-во': need_item['quantity'],
                    'Цена за ед.': 0,
                    'Сумма, руб.': 0
                })
                continue

            quantity = need_item['quantity'] / count
            price = best['item']['price']
            row_sum = price * quantity

            result.append({
                '№': i + 1,
                'Наименование': best['item']['name'],
                'Ед. изм.': need_item['unit'],
                'Кол-во': quantity,
                'Цена за ед.': price,
                'Сумма, руб.': round(row_sum, 2)
            })
            total_sum += row_sum

        if not result:
            logger.warning("Нет данных для коммерческого предложения")
            return None

        df = pd.DataFrame(result)
        wb = Workbook()
        ws = wb.active
        ws.title = "Коммерческое предложение"

        # Вставляем картинку шапки, если файл существует
        if os.path.exists(_HEADER_IMAGE_PATH):
            img = Image(_HEADER_IMAGE_PATH)
            ws.add_image(img, 'A1')
        else:
            logger.warning(f"Файл шапки не найден: {_HEADER_IMAGE_PATH}")

        START_ROW = 12

        headers = list(df.columns)
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=START_ROW, column=col_idx, value=header)

        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), START_ROW + 1):
            for c_idx, value in enumerate(row, 1):
                ws.cell(row=r_idx, column=c_idx, value=value)

        # Итоговые строки
        total_formatted = f"{total_sum:.2f}"
        ws.append([''] + ["ИТОГО"] + [''] * 3 + [total_formatted])
        ws.append([''] + ["Расходные материалы"] + [''] * 3 + [total_formatted])
        ws.append([''] + ["Итого оборудование и расходные материалы"] + [''] * 3 + [total_formatted])
        ws.append([''] + ["Монтажные работы"] + [''] * 3 + [total_formatted])
        ws.append([''] + ["ВСЕГО С НДС 20%:"] + [''] * 3 + [f"{total_sum * 1.2:.2f}"])

        apply_style(ws)
        return wb

    except Exception as e:
        logger.error(f"Ошибка создания коммерческого предложения: {e}", exc_info=True)
        return None
