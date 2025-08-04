import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import LOG_RETENTION_DAYS, logger
from bot.utils import cleanup_old_files

async def setup_scheduler():
    """Настройка периодических задач"""
    scheduler = AsyncIOScheduler()
    
    # Ежедневная очистка в 3:00
    scheduler.add_job(
        cleanup_old_files,
        CronTrigger(hour=3, minute=0),
        kwargs={"max_age_hours": LOG_RETENTION_DAYS * 24}
    )
    
    scheduler.start()
    logger.info("Планировщик задач запущен")
    return scheduler