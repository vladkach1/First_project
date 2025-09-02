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
            EC.presence_of_element_located((By.CSS_SELECTOR, ".catalog-product"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('.catalog-product')
        results = []
        
        if len(items)==0:
            results.append({
                'site': 'Tinko',
                'name': name,
                'price': 0,
                'status': "Не найдено",
                'url': driver.current_url
            })
            return results
        
        for item in items[:3]:  # Первый результата
            name1_elem=item.select_one('p.catalog-product__subtitle.textTailor[itemprop="description"]')
            name2_elem =item.select_one('.catalog-product__title[itemprop="name"] a')
            price_elem = item.select_one('[itemprop="price"]')
            stock_elem = item.select_one('.vue-stock')
            
            if not name2_elem or not price_elem or not name1_elem:
                continue
                
            name = name1_elem.text.strip()+" "+name2_elem.text.strip()
            price = float(price_elem.text.replace(' ', '').replace('₽', '').replace(',', '.'))
            stock = stock_elem.text.strip() #if stock_elem else "Доступно"
            
            # Определение статуса
            if "в наличии" in stock.lower():
                status = 'В наличии'
            elif "под заказ" in stock.lower():
                status = 'Под заказ'
            elif bool(re.match(r'^до \d+ дней', stock.lower())):
                status = stock.lower()
            else:
                status = "Ошибка"
            
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
    """Парсинг сайта luis.ru"""
    try:
        cache_key = f"luis_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        driver = setup_driver()
        driver.get(f"https://luis.ru/catalog/search?searchString={item_name}")
        
        # Ожидание загрузки результатов
        WebDriverWait(driver, REQUEST_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[style*="transition-delay"]'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('div[style*="transition-delay"]')
        results = []
        
        if len(items)==0:
            results.append({
                'site': 'luis',
                'name': name,
                'price': 0,
                'status': "Не найдено",
                'url': driver.current_url
            })
            return results
        
        for item in items[:3]:  # Первый результата
            name_elem=item.select_one('a.T9HTPK.CIG0OA')
            price_elem = item.select_one('.QG9RHe > span')
            stock_elem = item.select_one('.QG9RHe > span')
            
            if not name_elem or not price_elem:
                continue
                
            name = name_elem.text.strip()
            if price_elem.text.strip()!="Цена":
                price = float(price_elem.text.replace(' ', '').replace('₽', '').replace(',', '.'))
            else:
                price = 0
            stock = stock_elem.text.strip() 
            
            # Определение статуса
            if "цена" in stock.lower():
                status = 'Под заказ'
            elif bool(re.match(r'^[0-9]+[\.|\,]?[0-9]*$', price_elem.text.replace(' ', '').replace('₽', '').replace(',', '.'))):
                status = "В наличии"
            else:
                status = "Ошибка"
            
            results.append({
                'site': 'luis',
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
        logger.error(f"Ошибка парсинга luis: {e}")
        return []
    
def scrape_layta(item_name):
    """Парсинг сайта layta.ru"""
    try:
        cache_key = f"layta_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        driver = setup_driver()
        driver.set_page_load_timeout(30000)
        driver.implicitly_wait(10000)
        time.sleep(10)
        driver.get(f"https://www.layta.ru/?digiSearch=true&term={item_name}&params=%7Csort%3DDEFAULT")
        # Ожидание загрузки результатов
        WebDriverWait(driver, REQUEST_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.digi-product'))
        )
        time.sleep(10)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('.digi-product')
        results = []
        if len(items)==0:
            results.append({
                'site': 'layta',
                'name': name,
                'price': 0,
                'status': "Не найдено",
                'url': driver.current_url
            })
            return results
        for item in items[:3]:  # Первый результата
            name_elem=item.select_one('.digi-product__label')
            # Поиск элемента цены
            price_elem = item.select_one('.digi-product__price')
            if not price_elem:
                price_elem = item.select_one('.digi-product__unavailable')
            if not price_elem:
                print("Ошибка1")
            
            # Поиск элемента наличия
            stock_elem = item.select_one('.digi-product__available-count')
            if not stock_elem:
                stock_elem = item.select_one('.digi-product__unavailable')
            if not stock_elem:
                print("Ошибка2")

            if not name_elem:
                print("Ошибка3")

            print(name_elem.text.strip())
            print(price_elem.text.strip())
            print(stock_elem.text.strip())
            if not name_elem or not price_elem:
                continue
                
            name = name_elem.text.strip()
            
            if price_elem.text.strip()!="Уточняйте у менеджера":
                numbers = re.findall(r'[\d\s,]+', price_elem.text.strip())
                prices = []

                for num in numbers:
                    # Заменяем запятую на точку и убираем пробелы
                    clean_num = num.strip().replace(' ', '').replace(',', '.')
                    if clean_num:  # проверяем, что строка не пустая
                        try:
                            prices.append(float(clean_num))
                        except ValueError:
                            continue

                # Берем большую цену
                price = max(prices) if prices else 0.0
            else:
                price = 0
                status = 'Под заказ'
            stock = stock_elem.text.strip() 
            
            # Определение статуса
            if "в наличии" in stock.lower():
                status = 'В наличии'
            elif "под заказ" in stock.lower():
                status = "Под заказ"
            
            results.append({
                'site': 'layta',
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
        logger.error(f"Ошибка парсинга layta: {e}")
        return []

def scrape_etm(item_name):
    """Парсинг сайта etm.ru"""
    try:
        cache_key = f"etm_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        driver = setup_driver()
        driver.get(f"https://www.etm.ru/catalog?searchValue={item_name}")
        
        # Ожидание загрузки результатов
        WebDriverWait(driver, REQUEST_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.tss-o60ib4-grid_item'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('.tss-o60ib4-grid_item')
        results = []
        
        if len(items)==0:
            results.append({
                'site': 'etm',
                'name': name,
                'price': 0,
                'status': "Не найдено",
                'url': driver.current_url
            })
            return results
        
        for item in items[:3]:  # Первый результата
            name1_elem=item.select_one('a[data-testid="link-good-name"]')
            name2_elem=item.select_one('.tss-9cdrin-good_descr_value')
            price_elem = item.select_one('p.MuiTypography-title4.mui-1rtbk0o')
            stock_elem = item.select_one('button[data-testid^="availability_link-"]')
            
            if not name2_elem or not price_elem or not name1_elem:
                continue
                
            name = name1_elem.text.strip()+" "+name2_elem.text.strip()
            if (price_elem.text.strip()!="По запросу") and (price_elem.text.strip()!="Свяжитесь с нами"):
                price = float(price_elem.text.replace(' ', '').replace('₽/шт', '').replace(',', '.'))
            else:
                price = 0
            stock = stock_elem.text.strip() #Выдаёт иногда На заказ
            
            # Определение статуса
            if "по запросу" in stock.lower():
                status = 'Под заказ'
            else:
                status = stock
            
            results.append({
                'site': 'etm',
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
        logger.error(f"Ошибка парсинга etm: {e}")
        return []

# Функции для других сайтов...

SITE_SCRAPERS = {
    "https://www.tinko.ru": scrape_tinko,
    "https://www.luis.ru": scrape_luis,
    "https://www.layta.ru": scrape_layta,
    "https://www.etm.ru": scrape_etm
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
        tasks = [(scraper, equipment_name) for scraper in SITE_SCRAPERS.values()]
        
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