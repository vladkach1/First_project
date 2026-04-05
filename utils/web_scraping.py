import re
import logging
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from config import SEARCH_SITES, REQUEST_TIMEOUT, MAX_CONCURRENT_PAGES, SCRAPE_SELECTOR_TIMEOUT
from cache import cache

logger = logging.getLogger("WebScraping")

# ── Browser pool (singleton) ──────────────────────────────────────────────
# Один браузер на весь процесс, один контекст, семафор ограничивает
# количество одновременных вкладок.

_playwright_instance = None
_browser = None
_context = None
_semaphore = None
_browser_lock = None


def _get_semaphore():
    """Lazy-init семафора (должен создаваться внутри event loop)."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
    return _semaphore


def _get_browser_lock():
    """Lazy-init lock (должен создаваться внутри event loop)."""
    global _browser_lock
    if _browser_lock is None:
        _browser_lock = asyncio.Lock()
    return _browser_lock


async def _ensure_browser():
    """Запускает браузер если ещё не запущен или упал. Lock предотвращает гонку."""
    global _playwright_instance, _browser, _context
    lock = _get_browser_lock()
    async with lock:
        if _browser is not None and _browser.is_connected():
            return
        # Браузер мёртв или ещё не запущен — (пере)создаём
        _context = None
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
        if _playwright_instance is None:
            _playwright_instance = await async_playwright().start()
        _browser = await _playwright_instance.chromium.launch(headless=True)
        _context = await _browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        logger.info("Браузер запущен")


async def close_browser():
    """Закрывает shared-браузер. Вызывать при остановке бота."""
    global _browser, _context, _playwright_instance
    if _context:
        try:
            await _context.close()
        except Exception:
            pass
        _context = None
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright_instance:
        try:
            await _playwright_instance.stop()
        except Exception:
            pass
        _playwright_instance = None
    logger.info("Браузер закрыт")


# ── Получение HTML страницы ───────────────────────────────────────────────

async def _get_page_html(url, wait_selector, timeout=REQUEST_TIMEOUT):
    """
    Открывает URL в shared-браузере, ждёт селектор до SCRAPE_SELECTOR_TIMEOUT сек.
    Если селектор не появился — возвращает страницу как есть (парсер обработает 0 items).
    Семафор ограничивает параллельность до MAX_CONCURRENT_PAGES.
    """
    sem = _get_semaphore()
    async with sem:
        await _ensure_browser()
        page = await _context.new_page()
        try:
            await page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
            try:
                await page.wait_for_selector(
                    wait_selector, timeout=SCRAPE_SELECTOR_TIMEOUT * 1000
                )
            except PlaywrightTimeout:
                # Селектор не найден за 8с — скорее всего нет результатов
                logger.debug(f"Селектор не найден за {SCRAPE_SELECTOR_TIMEOUT}с: {url}")
            html = await page.content()
            return html, page.url
        finally:
            await page.close()


# ── Скраперы сайтов ──────────────────────────────────────────────────────

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
            cache.set(cache_key, results)
            return results

        for item in items[:3]:
            name_elem = item.select_one('.catalog-product__title a')
            subtitle_elem = item.select_one('.catalog-product__subtitle')
            price_elem = item.select_one('.catalog-product__price-block-value')
            stock_elem = item.select_one('[class*=status]')

            if not name_elem or not price_elem:
                continue

            name = name_elem.text.strip()
            if subtitle_elem:
                name = subtitle_elem.text.strip() + " " + name
            try:
                price_text = price_elem.text.strip()
                # Берём только цифры и разделители до первого пробела/символа единицы
                price = float(re.sub(r'[^\d,]', '', price_text.split('/')[0]).replace(',', '.'))
            except (ValueError, AttributeError):
                price = 0
            stock = stock_elem.text.strip() if stock_elem else ""

            if "в наличии" in stock.lower():
                status = 'В наличии'
            elif "под заказ" in stock.lower():
                status = 'Под заказ'
            elif bool(re.match(r'^до \d+ дней', stock.lower())):
                status = stock.lower()
            else:
                status = 'Под заказ'

            results.append({
                'site': 'Tinko',
                'name': name,
                'price': price,
                'status': status,
                'url': final_url
            })

        if not results:
            results.append({
                'site': 'Tinko',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
        cache.set(cache_key, results)
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга Tinko: {e}")
        fallback = [{'site': 'Tinko', 'name': item_name, 'price': 0, 'status': 'Не найдено', 'url': ''}]
        cache.set(f"tinko_{item_name}", fallback)
        return fallback


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
            cache.set(cache_key, results)
            return results

        for item in items[:3]:
            name_elem = item.select_one('.app-product-card-title, [class*=tile-product__name]')
            price_elem = item.select_one('.app-price__value')

            if not name_elem or not price_elem:
                continue

            name = name_elem.text.strip()
            try:
                digits = re.sub(r'[^\d]', '', price_elem.text.split('₽')[0])
                price = float(digits) if digits else 0
            except (ValueError, AttributeError):
                price = 0

            status = 'В наличии' if price > 0 else 'Под заказ'

            results.append({
                'site': 'luis',
                'name': name,
                'price': price,
                'status': status,
                'url': final_url
            })

        if not results:
            results.append({
                'site': 'luis',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
        cache.set(cache_key, results)
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга luis: {e}")
        fallback = [{'site': 'luis', 'name': item_name, 'price': 0, 'status': 'Не найдено', 'url': ''}]
        cache.set(f"luis_{item_name}", fallback)
        return fallback


async def scrape_layta(item_name):
    """Парсинг сайта layta.ru"""
    try:
        cache_key = f"layta_{item_name}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        url = f"https://www.layta.ru/?digiSearch=true&term={item_name}&params=%7Csort%3DDEFAULT"
        html, final_url = await _get_page_html(url, '.digi-product', timeout=30)

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
            cache.set(cache_key, results)
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
                digits = re.sub(r'[^\d]', '', price_elem.text.split('₽')[0])
                price = float(digits) if digits else 0.0
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

        if not results:
            results.append({
                'site': 'layta',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
        cache.set(cache_key, results)
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга layta: {e}")
        fallback = [{'site': 'layta', 'name': item_name, 'price': 0, 'status': 'Не найдено', 'url': ''}]
        cache.set(f"layta_{item_name}", fallback)
        return fallback


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
        items = soup.select('[data-testid*=catalog-list-item]')
        results = []

        if len(items) == 0:
            results.append({
                'site': 'etm',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
            cache.set(cache_key, results)
            return results

        for item in items[:3]:
            # Имя — ссылка на товар или длинный текст без лишних меток
            name_elem = item.select_one('a[data-testid="link-good-name"]')
            if not name_elem:
                typography = item.select('[class*=MuiTypography]')
                name_elem = next(
                    (t for t in typography
                     if len(t.text.strip()) > 15
                     and t.name in ('p', 'span', 'a')
                     and 'Сделано' not in t.text
                     and 'ЕАЭС' not in t.text),
                    None
                )
            price_elem = item.select_one('[class*=price]') or item.select_one('[class*=Price]')
            stock_elem = item.select_one('[data-testid*=availability]')

            if not name_elem or not price_elem:
                continue

            name = name_elem.text.strip()

            try:
                price_text = price_elem.text.strip()
                price = float(
                    re.sub(r'[^\d,.]', '', price_text.split('₽')[0])
                    .replace(',', '.')
                )
            except (ValueError, AttributeError):
                price = 0

            stock = stock_elem.text.strip() if stock_elem else ""

            if "по запросу" in stock.lower() or not stock:
                status = 'Под заказ'
            else:
                status = 'В наличии'

            results.append({
                'site': 'etm',
                'name': name,
                'price': price,
                'status': status,
                'url': final_url
            })

        if not results:
            results.append({
                'site': 'etm',
                'name': item_name,
                'price': 0,
                'status': "Не найдено",
                'url': final_url
            })
        cache.set(cache_key, results)
        return results
    except Exception as e:
        logger.error(f"Ошибка парсинга etm: {e}")
        fallback = [{'site': 'etm', 'name': item_name, 'price': 0, 'status': 'Не найдено', 'url': ''}]
        cache.set(f"etm_{item_name}", fallback)
        return fallback


# ── Маппинг сайтов ───────────────────────────────────────────────────────

SITE_SCRAPERS = {
    "https://www.tinko.ru": scrape_tinko,
    "https://www.luis.ru": scrape_luis,
    "https://www.layta.ru": scrape_layta,
    "https://www.etm.ru": scrape_etm
}


async def search_equipment_on_sites_async(equipment_name):
    """
    Асинхронный поиск оборудования на всех сайтах параллельно.
    Браузер shared, семафор ограничивает кол-во вкладок.
    """
    try:
        logger.info(f"Поиск: {equipment_name}")

        tasks = [scraper(equipment_name) for scraper in SITE_SCRAPERS.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка в скрапере: {result}")
                continue
            if result:
                all_results.extend(result)

        logger.info(f"Найдено {len(all_results)} предложений для '{equipment_name}'")
        return all_results
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return []
