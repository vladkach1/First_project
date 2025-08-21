import os
import tempfile
import logging
from telegram import Update, InputFile
from telegram.ext import (
    Updater, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackContext
)
from config import BOT_TOKEN, MAX_FILE_SIZE
from utils.pdf_to_img import convert_pdf_to_images
from utils.ocr_processing import extract_text_from_image
from utils.text_analysis import parse_equipment_spec
from utils.web_scraping import search_equipment_on_sites
from utils.excel_generator import create_search_report, create_commercial_offer
from error_handler import handle_error
from cache import cache
from config import BOT_TOKEN, MAX_FILE_SIZE, SEARCH_SITES
# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("TelegramBot")

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для анализа спецификаций оборудования. Просто отправь мне PDF файл с таблицей оборудования, "
        "и я выполню следующие действия:\n\n"
        "1. Конвертирую PDF в изображения\n"
        "2. Распознаю текст с помощью OCR\n"
        "3. Проанализирую спецификацию оборудования\n"
        "4. Найду лучшие цены на сайтах поставщиков\n"
        "5. Предоставлю отчет и коммерческое предложение\n\n"
        "Отправь мне PDF файл, чтобы начать!"
    )
    update.message.reply_text(welcome_message)

def handle_pdf(update: Update, context: CallbackContext) -> None:
    """Обработчик PDF файлов"""
    try:
        # Проверка типа файла
        if not update.message.document.mime_type == 'application/pdf':
            update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF.")
            return
            
        # Проверка размера файла
        if update.message.document.file_size > MAX_FILE_SIZE:
            update.message.reply_text(f"❌ Размер файла превышает {MAX_FILE_SIZE // 1024 // 1024}MB. Пожалуйста, отправьте файл меньшего размера.")
            return
            
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Скачиваем файл
            pdf_file = context.bot.get_file(update.message.document.file_id)
            pdf_path = os.path.join(tmp_dir, 'document.pdf')
            pdf_file.download(pdf_path)
            
            # Уведомление пользователя
            update.message.reply_text("📥 Файл получен. Начинаю обработку...")
            
            # Этап 1: Конвертация PDF в изображения
            update.message.reply_text("🔄 Конвертирую PDF в изображения...")
            img_paths = convert_pdf_to_images(pdf_path, tmp_dir)
            
            if not img_paths:
                update.message.reply_text("❌ Не удалось конвертировать PDF. Пожалуйста, убедитесь, что файл не поврежден.")
                return
            
            # Этап 2: OCR обработка
            update.message.reply_text("🔍 Распознаю текст с изображений...")
            full_text = ""
            for img_path in img_paths:
                text = extract_text_from_image(img_path)
                full_text += text + "\n\n"
            
            # Этап 3: Анализ текста
            update.message.reply_text("📊 Анализирую спецификацию оборудования...")
            equipment_data = parse_equipment_spec(full_text)
            
            if not equipment_data:
                update.message.reply_text("❌ Не удалось найти данные оборудования в документе. Убедитесь, что в PDF есть таблица со спецификацией.")
                return
                
            # Этап 4: Поиск оборудования на сайтах
            update.message.reply_text(f"🌐 Ищу оборудование на {len(SEARCH_SITES)} сайтах...")
            scraped_data = []
            for item in equipment_data:
                results = search_equipment_on_sites(item['name'])
                scraped_data.append(results)
            
            # Этап 5: Генерация отчетов
            update.message.reply_text("📊 Формирую отчеты...")
            
            # Отчет 1: Результаты поиска
            search_report = create_search_report(equipment_data, scraped_data)
            report_path = os.path.join(tmp_dir, 'search_report.xlsx')
            search_report.save(report_path)
            
            update.message.reply_document(
                document=InputFile(report_path),
                caption="✅ Результаты поиска оборудования\n\n"
                        "Цветовая маркировка статусов:\n"
                        "🟢 Зеленый - полностью доступно\n"
                        "🔵 Синий - требуется запрос\n"
                        "🟠 Оранжевый - мало остаток\n"
                        "🔴 Красный - недоступно\n"
                        "🟡 Желтый - санкционное оборудование"
            )
            
            # Отчет 2: Коммерческое предложение
            update.message.reply_text("💼 Формирую коммерческое предложение...")
            commercial_offer = create_commercial_offer(equipment_data, scraped_data)
            offer_path = os.path.join(tmp_dir, 'commercial_offer.xlsx')
            commercial_offer.save(offer_path)
            
            update.message.reply_document(
                document=InputFile(offer_path),
                caption="✅ Коммерческое предложение сформировано"
            )
            
            # Финализация
            update.message.reply_text("🎉 Обработка завершена успешно! Если у вас есть еще файлы, отправьте их сейчас.")
    
    except Exception as e:
        logger.error(f"Ошибка обработки PDF: {e}")
        update.message.reply_text("❌ Произошла ошибка при обработке вашего файла. Пожалуйста, попробуйте позже или обратитесь к администратору.")

def main():
    """Основная функция запуска бота"""
    try:
        # Очистка старого кэша
        cache.clear_old_cache()
        
        # Создаем экземпляр Updater
        updater = Updater(BOT_TOKEN)
        dispatcher = updater.dispatcher
        
        # Регистрируем обработчики
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(MessageHandler(filters.document, handle_pdf))
        dispatcher.add_error_handler(handle_error)
        
        # Запускаем бота
        updater.start_polling()
        logger.info("Бот запущен и ожидает сообщений...")
        updater.idle()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")

if __name__ == '__main__':
    main()