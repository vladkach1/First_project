import os
from dotenv import load_dotenv

load_dotenv()

# Основные настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Настройки OCR
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Для Windows
# TESSERACT_PATH = '/usr/bin/tesseract'  # Для Linux
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
    'available': '00FF00',      # Зеленый - полностью доступно
    'on_request': 'ADD8E6',     # Синий - требуется запрос
    'out_of_stock': 'FF0000',   # Красный - недоступно
    'sanctioned': 'FFFF00',     # Желтый - санкционное
    'low_stock': 'FFA500'       # Оранжевый - мало остаток
}

# Настройки Excel
DEFAULT_CURRENCY = "руб."