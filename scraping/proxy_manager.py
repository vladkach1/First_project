import random
import requests
import logging
from config import PROXY_ENABLED, PROXY_LIST, logger

proxy_rotation_index = 0
working_proxies = []

def get_proxy() -> dict:
    """Получение рабочего прокси для запроса"""
    if not PROXY_ENABLED or not working_proxies:
        return {}
    
    global proxy_rotation_index
    proxy = working_proxies[proxy_rotation_index % len(working_proxies)]
    proxy_rotation_index += 1
    
    logger.debug(f"Используется прокси: {proxy}")
    return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

def test_proxies() -> list:
    """Тестирование работоспособности прокси"""
    global working_proxies
    
    if not PROXY_ENABLED or not PROXY_LIST:
        working_proxies = []
        return []
    
    test_url = "http://httpbin.org/ip"
    working_proxies = []
    
    for proxy in PROXY_LIST:
        try:
            response = requests.get(
                test_url,
                proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                timeout=10
            )
            if response.status_code == 200:
                working_proxies.append(proxy)
                logger.info(f"Прокси {proxy} рабочий")
            else:
                logger.warning(f"Прокси {proxy} вернул статус {response.status_code}")
        except Exception as e:
            logger.warning(f"Прокси {proxy} не работает: {e}")
    
    logger.info(f"Найдено {len(working_proxies)} рабочих прокси")
    return working_proxies

def rotate_proxy():
    """Ротация прокси"""
    global working_proxies
    if working_proxies:
        working_proxies.append(working_proxies.pop(0))
        logger.info("Прокси ротированы")