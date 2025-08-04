import asyncio
import logging
from telegram.ext import Application
from config import TOKEN, logger
from bot.handlers import register_handlers
from bot.scheduler import setup_scheduler
from scraping.proxy_manager import test_proxies

async def main():
    """Основная функция запуска бота"""
    try:
        logger.info("Запуск бота...")
        
        # Тестирование прокси
        test_proxies()
        
        # Создание и настройка приложения
        application = Application.builder().token(TOKEN).build()
        register_handlers(application)
        
        # Настройка планировщика задач
        await setup_scheduler()
        
        # Запуск бота
        logger.info("Бот запущен и готов к работе")
        await application.run_polling()
        
    except Exception as e:
        logger.critical(f"Критическая ошибка запуска: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())