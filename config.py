import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Загрузка переменных окружения
load_dotenv()
MAX_PARSE_TIME = int(os.getenv("MAX_PARSE_TIME", 300))  # 5 минут
# Базовые пути
BASE_DIR = Path(__file__).parent.resolve()
STORAGE_DIR = BASE_DIR / "storage"
TEMP_DIR = STORAGE_DIR / "temp_files"
LOG_DIR = STORAGE_DIR / "logs"

# Создание директорий
for directory in [STORAGE_DIR, TEMP_DIR, LOG_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# Основные настройки
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 20)) * 1024 * 1024  # в байтах

# Настройки OCR
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "rus+eng")

# Настройки парсинга
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", 3))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 1.5))
SCRAPE_ENABLED = os.getenv("SCRAPE_ENABLED", "true").lower() == "true"

# Настройки прокси
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true"
PROXY_LIST = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []

# Настройки логгирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))

# Валидация конфигурации
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")

# Настройка логгирования
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Вывод информации о конфигурации
logger.info(f"Конфигурация загружена. Базовая директория: {BASE_DIR}")
logger.info(f"OCR {'включен' if OCR_ENABLED else 'отключен'}")
logger.info(f"Парсинг {'включен' if SCRAPE_ENABLED else 'отключен'}")
logger.info(f"Прокси {'включены' if PROXY_ENABLED else 'отключены'}")