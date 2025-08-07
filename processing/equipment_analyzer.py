import re
import time
import logging
from typing import List, Dict
from config import logger
from bot.utils import setup_cache, cache_get, cache_set
from scraping.price_scraper import find_equipment_price
from .cid_decoder import decode_cid_text
import time
from config import MAX_PARSE_TIME

def analyze_equipment(equipment: List[Dict]) -> List[Dict]:
    start_time = time.time()
    for item in equipment:
        # Проверка времени
        if time.time() - start_time > MAX_PARSE_TIME:
            logger.warning("Превышено время анализа. Часть оборудования не обработана.")
            break
def normalize_name(name: str) -> str:
    """Нормализация названия оборудования"""
    # Декодирование CID в первую очередь
    name = decode_cid_text(name)
    
    # Удаление лишних пробелов
    name = re.sub(r"\s+", " ", name).strip()
    
    # Остальная нормализация...
def analyze_equipment(equipment: List[Dict]) -> List[Dict]:
    """Анализ оборудования и поиск цен"""
    logger.info(f"Начат анализ {len(equipment)} позиций")
    cache_conn = setup_cache()
    analyzed_count = 0
    
    for item in equipment:
        try:
            # Нормализация названия
            item["name"] = normalize_name(item["name"])
            
            # Проверка статуса
            item["status"] = check_equipment_status(item["name"])
            
            # Поиск цены для доступного оборудования
            if item["status"] == "В наличии":
                # Проверка кеша
                cache_key = f"price:{item['name']}"
                cached_price = cache_get(cache_conn, cache_key)
                
                if cached_price:
                    item["price"] = cached_price
                    item["source"] = "Кеш"
                else:
                    price_info = find_equipment_price(item["name"])
                    item.update(price_info)
                    
                    # Сохранение в кеш
                    if price_info.get("price"):
                        cache_set(cache_conn, cache_key, price_info["price"])
            
            analyzed_count += 1
            
            # Логирование прогресса
            if analyzed_count % 10 == 0:
                logger.info(f"Проанализировано {analyzed_count}/{len(equipment)} позиций")
                
        except Exception as e:
            logger.error(f"Ошибка анализа позиции '{item.get('name')}': {e}")
            item["status"] = "Ошибка анализа"
            item["price"] = "N/A"
            item["source"] = "Система"
    
    cache_conn.close()
    logger.info(f"Анализ завершен для {analyzed_count} позиций")
    return equipment

def normalize_name(name: str) -> str:
    """Нормализация названия оборудования"""
    # Удаление лишних пробелов
    name = re.sub(r"\s+", " ", name).strip()
    
    # Стандартизация брендов
    brand_mappings = {
        "ВЗ–РиБСК": "Bolid",
        "Smart": "Siemens",
        "ОПОП": "Optima",
        "ИП": "ИПД",
        "РН-": "Relay",
        "Рубеж-": "Rubezh",
        "КПСС": "KPS",
        "PVCLS": "ПВКЛС",
    }
    
    for old, new in brand_mappings.items():
        name = name.replace(old, new)
    
    return name

def check_equipment_status(name: str) -> str:
    """Проверка статуса оборудования"""
    # Проверка санкционных брендов
    sanctioned_brands = ["RIT", "PVCLS", "Bolid", "LTV", "RVi"]
    if any(brand in name for brand in sanctioned_brands):
        return "Санкционное"
    
    # Проверка устаревших моделей
    if any(year in name for year in [str(y) for y in range(2010, 2020)]):
        return "Снято с производства"
    
    # Проверка на необходимость запроса
    if any(keyword in name for keyword in ["под заказ", "запрос", "по запросу"]):
        return "Требует запроса"
    
    return "В наличии"