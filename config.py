import os
import re
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
MAX_THREADS = 10
REQUEST_TIMEOUT = 30

# Настройки кэша
CACHE_DIR = "cache"
CACHE_TTL = 3600  # 1 час

# Цвета для статусов оборудования
COLOR_MAPPING = {
    'В наличии': '00FF00',      # Зеленый - полностью доступно
    'Под заказ': 'ADD8E6',     # Синий - требуется запрос
    # Оранжевый - Время доставки
    'Ошибка': 'FF0000'       # Красное - Ошибка неизвестный статус
}

# Настройки Excel
DEFAULT_CURRENCY = "руб."