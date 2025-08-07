import time
import random
import requests
import yaml
import re
from bs4 import BeautifulSoup
from pathlib import Path
from config import REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_DELAY, logger
from .proxy_manager import get_proxy
from processing.cid_decoder import decode_cid_text

def find_equipment_price(equipment_name: str) -> dict:
    """Поиск цены на оборудование"""
    # Декодируем имя оборудования перед поиском
    equipment_name = decode_cid_text(equipment_name)
    
    # Остальной код без изменений...
# Загрузка селекторов
SELECTORS_FILE = Path(__file__).parent / "site_selectors.yaml"
with open(SELECTORS_FILE, 'r', encoding='utf-8') as f:
    SITE_CONFIG = yaml.safe_load(f)["sites"]

def find_equipment_price(equipment_name: str) -> dict:
    """Поиск цены на оборудование"""
    result = {"price": "Не найдено", "source": "Не определен"}
    
    # Сайты в случайном порядке для распределения нагрузки
    sites = list(SITE_CONFIG.items())
    random.shuffle(sites)
    
    for site_name, config in sites:
        for attempt in range(REQUEST_RETRIES):
            try:
                price_info = scrape_site(
                    config["url"].format(query=equipment_name.replace(" ", "+")),
                    site_name,
                    config["price_selector"]
                )
                
                if price_info["price"]:
                    return price_info
            
            except Exception as e:
                logger.warning(f"Ошибка при запросе к {site_name} (попытка {attempt+1}): {e}")
            
            time.sleep(REQUEST_DELAY * (attempt + 1))
    
    return result

def scrape_site(url: str, site_name: str, price_selector: str) -> dict:
    """Парсинг конкретного сайта"""
    result = {"price": None, "source": site_name}
    
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
            },
            proxies=get_proxy(),
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        price_tag = soup.select_one(price_selector)
        
        if price_tag:
            price_text = price_tag.get_text().strip()
            cleaned_price = clean_price(price_text)
            
            if cleaned_price:
                result["price"] = f"{cleaned_price} ₽"
                return result
    
    except Exception as e:
        logger.error(f"Ошибка парсинга {site_name}: {e}")
        raise
    
    return result

def clean_price(price_text: str) -> float:
    """Очистка и преобразование цены"""
    try:
        # Удаление нецифровых символов, кроме точки и запятой
        cleaned = re.sub(r"[^\d.,]", "", price_text)
        
        # Замена запятых на точки
        cleaned = cleaned.replace(",", ".")
        
        # Извлечение первого числа
        match = re.search(r"[\d]+\.?[\d]*", cleaned)
        if match:
            return float(match.group(0))
    
    except Exception as e:
        logger.warning(f"Ошибка очистки цены '{price_text}': {e}")
    
    return None