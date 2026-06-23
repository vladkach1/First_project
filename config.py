import os
from dotenv import load_dotenv

load_dotenv()

# Основные настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Настройки OCR (RapidOCR — без внешних бинарников)

# Настройки поиска
SEARCH_SITES = [
    "https://www.luis.ru",
    "https://www.tinko.ru",
    #"https://www.layta.ru",
    "https://www.etm.ru"
]
REQUEST_TIMEOUT = 30

# Настройки скрапинга
MAX_CONCURRENT_PAGES = 10          # макс. параллельных вкладок в браузере
SCRAPE_SELECTOR_TIMEOUT = 180        # сек. ожидания селектора результатов (быстрый fallback)
PROGRESS_BATCH_SIZE = 20           # размер батча для прогресс-сообщений

# Настройки кэша
CACHE_DIR = "cache"
CACHE_TTL = 86400  # 24 часа (было 3600 = 1 час)

# Цвета для статусов оборудования
COLOR_MAPPING = {
    'В наличии': '00FF00',      # Зеленый - полностью доступно
    'Под заказ': 'ADD8E6',     # Синий - требуется запрос
    # Оранжевый - Время доставки
    'Ошибка': 'FF0000'       # Красное - Ошибка неизвестный статус
}

# Настройки Excel
DEFAULT_CURRENCY = "руб."
