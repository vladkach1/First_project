import os
import time
import asyncio
import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import MAX_FILE_SIZE, logger, ADMIN_USER_ID
from bot.utils import get_file_path, generate_unique_filename
from processing.pdf_processor import process_pdf
from processing.excel_generator import generate_excel_report

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    help_text = (
        f"👋 Привет {user.first_name}!\n\n"
        "Я бот для анализа спецификаций оборудования в PDF.\n\n"
        "📌 Просто отправь мне PDF-файл, и я:\n"
        "1. Извлеку список оборудования\n"
        "2. Проверю наличие и цены на ведущих площадках\n"
        "3. Отмечу санкционное и устаревшее оборудование\n"
        "4. Сгенерирую Excel-отчет с результатами\n\n"
        f"⚠️ Максимальный размер файла: {MAX_FILE_SIZE//1024//1024}MB\n"
        "⏱ Обработка занимает 1-5 минут в зависимости от размера файла"
    )
    
    await update.message.reply_text(help_text)

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученного PDF-файла"""
    user = update.effective_user
    file = update.message.document
    
    # Проверка размера файла
    if file.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"⚠️ Файл слишком большой ({file.file_size//1024//1024}MB). "
            f"Максимальный размер: {MAX_FILE_SIZE//1024//1024}MB"
        )
        return
    
    # Подготовка путей
    pdf_path = generate_unique_filename(prefix=f"user_{user.id}", extension=".pdf")
    excel_path = generate_unique_filename(prefix=f"report_{user.id}", extension=".xlsx")
    
    # Скачивание файла
    start_time = time.time()
    msg_progress = await update.message.reply_text("📥 Загружаю файл...")
    
    try:
        tg_file = await file.get_file()
        await tg_file.download_to_drive(custom_path=pdf_path)
        download_time = time.time() - start_time
        logger.info(f"Файл {file.file_name} скачан за {download_time:.1f}с")
        await msg_progress.edit_text("🔍 Анализирую документ...")
    except Exception as e:
        logger.error(f"Ошибка скачивания файла: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке файла. Попробуйте еще раз.")
        return
    
    # Обработка PDF
    try:
        # Запуск обработки в отдельной задаче
        await asyncio.to_thread(process_pdf, pdf_path, excel_path, user.id)
        
        # Отправка результата
        await msg_progress.delete()
        with open(excel_path, 'rb') as report_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(report_file, filename=f"Отчет_{file.file_name}.xlsx"),
                caption="✅ Готово! Результаты анализа спецификации",
            )
        logger.info(f"Отчет для {user.id} успешно отправлен")
        
    except Exception as e:
        logger.exception(f"Ошибка обработки PDF: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке файла. "
            "Убедитесь, что это файл со спецификацией оборудования."
        )
    finally:
        # Очистка временных файлов
        for path in [pdf_path, excel_path]:
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    logger.warning(f"Не удалось удалить {path}: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке сообщения: {context.error}", exc_info=True)
    
    if update.message:
        await update.message.reply_text(
            "⚠️ Произошла непредвиденная ошибка. "
            "Попробуйте отправить файл еще раз или обратитесь к администратору."
        )
    
    # Отправка уведомления админу
    if ADMIN_USER_ID:
        error_msg = f"Ошибка в боте: {context.error}\n\nUser: {update.effective_user}"
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=error_msg)

def register_handlers(application):
    """Регистрация обработчиков"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    application.add_error_handler(error_handler)