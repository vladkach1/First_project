import os
import re
from dotenv import load_dotenv

load_dotenv()

# Основные настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Настройки OCR
# TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Для Windows
# TESSERACT_PATH = '/usr/bin/tesseract'  # Для Linux
TESSERACT_PATH = '/opt/homebrew/bin/tesseract'

CHROMEDRIVER_PATH = '/opt/homebrew/bin/chromedriver'

OCR_LANGUAGE = 'rus+eng'

# Настройки поиска
SEARCH_SITES = [
    "https://www.tinko.ru",
    "https://www.luis.ru",
    "https://www.laita.ru",
    "https://www.eltex.ru",
    "https://www.ltv.ru",
    "https://www.rviai.ru"
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
    r'^до \d+ дней': 'FFA500',   # Оранжевый - Время доставки
    'Ошибка': 'FF0000'       # Красное - Ошибка неизвестный статус
}

# Настройки Excel
DEFAULT_CURRENCY = "руб."