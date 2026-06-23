import os
import json
import time
import re
import hashlib
import logging
from config import CACHE_DIR, CACHE_TTL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cache")


class CacheManager:
    def __init__(self):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

    def _normalize_key(self, key):
        """
        Нормализация ключа кэша для лучшего процента попаданий.
        'tinko_Кабель  КВВГнг 4х1.5' и 'tinko_кабель кввгнг 4x1.5'
        дадут одинаковый хэш.
        """
        key = key.lower().strip()
        key = re.sub(r'\s+', ' ', key)
        key = key.replace('х', 'x')   # Кириллическая х → латинская x
        key = key.replace('ё', 'е')
        return key

    def _get_cache_path(self, key):
        """Генерирует путь к файлу кэша на основе нормализованного ключа"""
        normalized = self._normalize_key(key)
        key_hash = hashlib.md5(normalized.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{key_hash}.json")

    def get(self, key):
        """Получает данные из кэша"""
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if time.time() - data['timestamp'] > CACHE_TTL:
                os.remove(cache_path)
                return None

            logger.debug(f"Cache HIT: {key[:50]}")
            return data['content']
        except Exception as e:
            logger.error(f"Ошибка чтения кэша: {e}")
            return None

    def set(self, key, data):
        """Сохраняет данные в кэш"""
        cache_path = self._get_cache_path(key)
        try:
            cache_data = {
                'timestamp': time.time(),
                'content': data
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка записи в кэш: {e}")

    def clear_old_cache(self):
        """Очищает просроченный кэш"""
        now = time.time()
        removed = 0
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            try:
                if os.path.isfile(filepath):
                    file_time = os.path.getmtime(filepath)
                    if now - file_time > CACHE_TTL:
                        os.remove(filepath)
                        removed += 1
            except Exception as e:
                logger.error(f"Ошибка удаления кэша: {e}")
        if removed:
            logger.info(f"Очищено {removed} просроченных записей кэша")


# Глобальный экземпляр кэша
cache = CacheManager()
