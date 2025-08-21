import re
import time
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import SEARCH_SITES, REQUEST_TIMEOUT, MAX_THREADS
from cache import cache
from .parallel_processing import run_in_parallel

# Настройка логирования
logger = logging.getLogger("WebScraping")

def setup_driver():
    """Настраивает и возвращает экземпляр веб-драйвера"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(REQUEST_TIMEOUT)
    return driver

def scrape_tinko(item_name):
    """Парсинг сайта Tinko.ru"""
    try:
        cache_key = f"tinko_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        driver = setup_driver()
        driver.get(f"https://www.tinko.ru/search/?q={item_name}")
        
        # Ожидание загрузки результатов
        WebDriverWait(driver, REQUEST_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".catalog-item"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('.catalog-item')
        
        results = []
        for item in items[:3]:  # Первые 3 результата
            name_elem = item.select_one('.item-title')
            price_elem = item.select_one('.price')
            stock_elem = item.select_one('.stock-status')
            
            if not name_elem or not price_elem:
                continue
                
            name = name_elem.text.strip()
            price = float(price_elem.text.replace(' ', '').replace('₽', '').replace(',', '.'))
            stock = stock_elem.text.strip() if stock_elem else "Доступно"
            
            # Определение статуса
            status = 'available'
            if "под заказ" in stock.lower():
                status = 'on_request'
            elif "нет в наличии" in stock.lower():
                status = 'out_of_stock'
            
            results.append({
                'site': 'Tinko',
                'name': name,
                'price': price,
                'status': status,
                'url': driver.current_url
            })
        
        driver.quit()
        
        if results:
            cache.set(cache_key, results)
        
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга Tinko: {e}")
        return []

def scrape_luis(item_name):
    """Парсинг сайта Luis.ru"""
    # Реализация аналогична scrape_tinko
    # ...
    return []

# Функции для других сайтов...

SITE_SCRAPERS = {
    "https://www.tinko.ru": scrape_tinko,
    "https://www.luis.ru": scrape_luis,
    # Добавьте другие сайты здесь...
}

def search_equipment_on_sites(equipment_name):
    """
    Ищет оборудование на всех сайтах параллельно
    
    :param equipment_name: Название оборудования
    :return: Список результатов со всех сайтов
    """
    try:
        logger.info(f"Поиск оборудования: {equipment_name}")
        
        # Подготовка задач для параллельного выполнения
        tasks = [(scraper, [equipment_name]) for scraper in SITE_SCRAPERS.values()]
        
        # Параллельный запуск
        results = run_in_parallel(tasks, max_workers=MAX_THREADS)
        
        # Сбор всех результатов
        all_results = []
        for result in results:
            if result:
                all_results.extend(result)
        
        logger.info(f"Найдено {len(all_results)} предложений для {equipment_name}")
        return all_results
    except Exception as e:
        logger.error(f"Ошибка поиска оборудования: {e}")
        return []