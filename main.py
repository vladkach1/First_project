import asyncio
import logging
from telegram.ext import Application
from config import TOKEN, logger
from bot.handlers import register_handlers
from bot.scheduler import setup_scheduler
from scraping.proxy_manager import test_proxies

async def main():
    """Основная функция запуска бота"""
    application = None
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
        await application.initialize()  # Явная инициализация
        await application.start()
        await application.updater.start_polling()  # Для версий 20.x+
        
        # Бесконечный цикл работы бота
        while True:
            await asyncio.sleep(3600)  # Просто ждем
            
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Получен сигнал на остановку")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
    finally:
        if application:
            if application.updater:
                await application.updater.stop()
            await application.stop()
            await application.shutdown()
        logger.info("Бот завершил работу")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")