import os
import re
import time
import hashlib
import sqlite3
import logging
from pathlib import Path
from config import TEMP_DIR, logger

def get_file_path(filename: str, subdir: str = "") -> Path:
    """Получение безопасного пути к файлу"""
    safe_name = re.sub(r'[^\w\d_.-]', '', filename)
    path = TEMP_DIR / subdir / safe_name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def generate_unique_filename(prefix: str = "", extension: str = "") -> Path:
    """Генерация уникального имени файла"""
    timestamp = int(time.time())
    random_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    filename = f"{prefix}_{timestamp}_{random_str}{extension}"
    return TEMP_DIR / filename

def setup_cache() -> sqlite3.Connection:
    """Настройка кеширования в SQLite"""
    cache_db = TEMP_DIR / "cache.db"
    conn = sqlite3.connect(cache_db)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cache
                 (key TEXT PRIMARY KEY, value TEXT, timestamp REAL)''')
    conn.commit()
    return conn

def cache_get(conn: sqlite3.Connection, key: str) -> str:
    """Получение значения из кеша"""
    c = conn.cursor()
    c.execute("SELECT value FROM cache WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def cache_set(conn: sqlite3.Connection, key: str, value: str):
    """Сохранение значения в кеше"""
    c = conn.cursor()
    timestamp = time.time()
    c.execute("INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)", 
              (key, value, timestamp))
    conn.commit()

def cleanup_old_files(max_age_hours: int = 24):
    """Очистка старых временных файлов"""
    now = time.time()
    for file_path in TEMP_DIR.glob("**/*"):
        if file_path.is_file():
            file_age = now - file_path.stat().st_mtime
            if file_age > max_age_hours * 3600:
                try:
                    file_path.unlink()
                    logger.info(f"Удален старый файл: {file_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {file_path}: {e}")