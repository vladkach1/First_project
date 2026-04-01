import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR
)
logger = logging.getLogger("ErrorHandler")

async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асинхронный обработчик глобальных ошибок"""
    try:
        # Логируем ошибку
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)

        error_message = (
            f"Exception while handling an update:\n"
            f"Update: {update}\n"
            f"Context: {context}\n"
            f"Traceback:\n{tb_string}"
        )

        logger.error(error_message)

        # Уведомляем пользователя
        if update and update.message:
            user_message = (
                "⚠️ Произошла непредвиденная ошибка при обработке вашего запроса. "
                "Попробуйте повторить операцию позже или обратитесь к администратору."
            )
            await update.message.reply_text(user_message)
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")
