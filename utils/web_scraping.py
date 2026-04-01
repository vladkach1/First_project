import re
import logging
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from config import SEARCH_SITES, REQUEST_TIMEOUT, MAX_THREADS
from cache import cache

# Настройка логирования
logger = logging.getLogger("WebScraping")


async def _get_page_html(url, wait_selector, timeout=REQUEST_TIMEOUT):
    """
    Открывает URL в headless Chromium через Playwright,
    ждёт появления селектора и возвращает (html, final_url).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=timeout * 1000)
            await page.wait_for_selector(wait_selector, timeout=timeout * 1000)
            html = await page.content()
            final_url = page.url
            return html, final_url
        finally:
            await browser.close()


async def scrape_tinko(item_name):
    """Парсинг сайта Tinko.ru"""
    try:
        cache_key = f"tinko_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        url = f"https://www.tinko.ru/search/?q={item_name}"
        html, final_url = await _get_page_html(url, ".catalog-product")

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.catalog-product')
        results = []

        if len(items) == 0:
            results.append({
                'site': 'Tinko',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
            return results

        for item in items[:3]:
            name1_elem = item.select_one('p.catalog-product__subtitle.textTailor[itemprop="description"]')
            name2_elem = item.select_one('.catalog-product__title[itemprop="name"] a')
            price_elem = item.select_one('[itemprop="price"]')
            stock_elem = item.select_one('.vue-stock')

            if not name2_elem or not price_elem or not name1_elem:
                continue

            name = name1_elem.text.strip() + " " + name2_elem.text.strip()
            price = float(price_elem.text.replace(' ', '').replace('₽', '').replace(',', '.'))
            stock = stock_elem.text.strip()

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
                'url': final_url
            })

        if results:
            cache.set(cache_key, results)

        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга Tinko: {e}")
        return []


async def scrape_luis(item_name):
    """Парсинг сайта luis.ru"""
    try:
        cache_key = f"luis_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        url = f"https://luis.ru/catalog/search?searchString={item_name}"
        html, final_url = await _get_page_html(url, 'div[style*="transition-delay"]')

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('div[style*="transition-delay"]')
        results = []

        if len(items) == 0:
            results.append({
                'site': 'luis',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
            return results

        for item in items[:3]:
            name_elem = item.select_one('a.T9HTPK.CIG0OA')
            price_elem = item.select_one('.QG9RHe > span')
            stock_elem = item.select_one('.QG9RHe > span')

            if not name_elem or not price_elem:
                continue

            name = name_elem.text.strip()
            if price_elem.text.strip() != "Цена":
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
                'url': final_url
            })

        if results:
            cache.set(cache_key, results)

        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга luis: {e}")
        return []


async def scrape_layta(item_name):
    """Парсинг сайта layta.ru"""
    try:
        cache_key = f"layta_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            try:
                url = f"https://www.layta.ru/?digiSearch=true&term={item_name}&params=%7Csort%3DDEFAULT"
                await page.goto(url, timeout=30000)
                await page.wait_for_selector('.digi-product', timeout=REQUEST_TIMEOUT * 1000)

                html = await page.content()
                final_url = page.url
            finally:
                await browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.digi-product')
        results = []

        if len(items) == 0:
            results.append({
                'site': 'layta',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
            return results

        for item in items[:3]:
            name_elem = item.select_one('.digi-product__label')
            price_elem = item.select_one('.digi-product__price')
            if not price_elem:
                price_elem = item.select_one('.digi-product__unavailable')

            stock_elem = item.select_one('.digi-product__available-count')
            if not stock_elem:
                stock_elem = item.select_one('.digi-product__unavailable')

            if not name_elem or not price_elem:
                continue

            name = name_elem.text.strip()

            if price_elem.text.strip() != "Уточняйте у менеджера":
                numbers = re.findall(r'[\d\s,]+', price_elem.text.strip())
                prices = []
                for num in numbers:
                    clean_num = num.strip().replace(' ', '').replace(',', '.')
                    if clean_num:
                        try:
                            prices.append(float(clean_num))
                        except ValueError:
                            continue
                price = max(prices) if prices else 0.0
                status = 'В наличии'
            else:
                price = 0
                status = 'Под заказ'

            if stock_elem:
                stock = stock_elem.text.strip()
                if "в наличии" in stock.lower():
                    status = 'В наличии'
                elif "под заказ" in stock.lower():
                    status = "Под заказ"

            results.append({
                'site': 'layta',
                'name': name,
                'price': price,
                'status': status,
                'url': final_url
            })

        if results:
            cache.set(cache_key, results)

        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга layta: {e}")
        return []


async def scrape_etm(item_name):
    """Парсинг сайта etm.ru"""
    try:
        cache_key = f"etm_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        url = f"https://www.etm.ru/catalog?searchValue={item_name}"
        html, final_url = await _get_page_html(url, '.tss-o60ib4-grid_item')

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.tss-o60ib4-grid_item')
        results = []

        if len(items) == 0:
            results.append({
                'site': 'etm',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
            return results

        for item in items[:3]:
            name1_elem = item.select_one('a[data-testid="link-good-name"]')
            name2_elem = item.select_one('.tss-9cdrin-good_descr_value')
            price_elem = item.select_one('p.MuiTypography-title4.mui-1rtbk0o')
            stock_elem = item.select_one('button[data-testid^="availability_link-"]')

            if not name2_elem or not price_elem or not name1_elem:
                continue

            name = name1_elem.text.strip() + " " + name2_elem.text.strip()

            if (price_elem.text.strip() != "По запросу") and \
               (price_elem.text.strip() != "Свяжитесь с нами") and \
               (price_elem.text.strip() != "н/д"):
                price = float(
                    price_elem.text
                    .replace(' ', '')
                    .replace('₽/шт', '')
                    .replace(',', '.')
                    .replace('₽/компл', '')
                    .replace('₽/м', '')
                    .replace('₽/упак', '')
                    .replace('₽/уп', '')
                    .replace('₽/рул', '')
                )
            else:
                price = 0

            stock = stock_elem.text.strip()

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
                'url': final_url
            })

        if results:
            cache.set(cache_key, results)
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга etm: {e}")
        return []


# Маппинг сайтов на async-скраперы
SITE_SCRAPERS = {
    "https://www.tinko.ru": scrape_tinko,
    "https://www.luis.ru": scrape_luis,
    #"https://www.layta.ru": scrape_layta,
    "https://www.etm.ru": scrape_etm
}


async def search_equipment_on_sites_async(equipment_name):
    """
    Асинхронный поиск оборудования на всех сайтах параллельно.
    Использует Playwright async API — не блокирует event loop.

    :param equipment_name: Название оборудования
    :return: Список результатов со всех сайтов
    """
    try:
        logger.info(f"Поиск оборудования: {equipment_name}")

        # Запускаем все скраперы параллельно через asyncio.gather
        tasks = [
            scraper(equipment_name)
            for scraper in SITE_SCRAPERS.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка в скрапере: {result}")
                continue
            if result:
                all_results.extend(result)

        logger.info(f"Найдено {len(all_results)} предложений для {equipment_name}")
        return all_results
    except Exception as e:
        logger.error(f"Ошибка поиска оборудования: {e}")
        return []
