import re
import logging
from difflib import SequenceMatcher

# Настройка логирования
logger = logging.getLogger("TextAnalysis")

def similarity(a, b):
    """Вычисляет схожесть двух строк (0.0-1.0)"""
    return SequenceMatcher(None, a, b).ratio()

def parse_equipment_spec(text):
    """
    Анализирует распознанный текст и извлекает спецификацию оборудования
    
    :param text: Текст для анализа
    :return: Список словарей с данными оборудования
    """
    try:
        logger.info("Начало анализа текста оборудования")
        
        # Улучшенный шаблон для извлечения табличных данных
        table_pattern = re.compile(
            r'(\d+)\s*\|?\s*([^\|]+?)\s*\|?\s*([^\|]+?)\s*\|?\s*([^\|]+?)\s*\|?\s*(\d+)\s*\|?\s*([\d\s,\.]+)\s*\|?\s*([\d\s,\.]+)',
            re.DOTALL
        )
        
        matches = table_pattern.findall(text)
        
        if not matches:
            logger.warning("Не найдено совпадений в тексте")
            return []
        
        equipment_list = []
        for match in matches:
            try:
                # Обработка и очистка данных
                item = {
                    'number': match[0].strip(),
                    'name': re.sub(r'\s+', ' ', match[1].strip()),
                    'designation': re.sub(r'\s+', ' ', match[2].strip()),
                    'unit': match[3].strip(),
                    'quantity': int(match[4].replace(' ', '')),
                    'price': float(match[5].replace(' ', '').replace(',', '.')),
                    'total': float(match[6].replace(' ', '').replace(',', '.'))
                }
                
                # Проверка целостности данных
                if not all(item.values()):
                    logger.warning(f"Пропущена неполная запись: {item}")
                    continue
                
                if item['price'] * item['quantity'] != item['total']:
                    logger.warning(f"Несоответствие суммы для {item['name']}")
                
                equipment_list.append(item)
                logger.debug(f"Добавлено оборудование: {item['name']}")
                
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка обработки строки: {match} - {e}")
                continue
        
        logger.info(f"Успешно извлечено {len(equipment_list)} позиций оборудования")
        logger.info(f"Успешно извлечено {equipment_list[0]} позиций оборудования")
        return equipment_list
    
    except Exception as e:
        logger.error(f"Ошибка анализа текста: {e}")
        raise RuntimeError("Ошибка анализа спецификации оборудования.")