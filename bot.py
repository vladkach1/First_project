import os
import tempfile
import re
import logging
import asyncio
import io
from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
import PyPDF2
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import os
import fitz
import io
from config import BOT_TOKEN, MAX_FILE_SIZE
from utils.pdf_to_img import crop_page_to_region,extract_text_from_region,analyze_pdf_region,print_region_results,export_region_to_file
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для анализа спецификаций оборудования. Просто отправь мне список оборудования, который будет выглядеть следующим образом: наименовиние(кабель; датчик), колличество(1, 2, 3), единица измерения(шт; см; м; л) "
        "и я выполню следующие действия:\n\n"
        "1. Проанализирую ваш список \n"
        "2. Проанализирую спецификацию оборудования\n"
        "3. Найду лучшие цены на сайтах поставщиков\n"
        "4. Предоставлю отчет и коммерческое предложение основанное на отчете\n\n"
        "Отправь мне Список, подобный нижнему, чтобы начать!\n\n"
        "Кабель 305 м\n"
        "Тросс 4 мм\n"                                                                              
        "Видеокамера 2 шт\n\n"
        "И так далее по списку, каждое наименование с новой строки, соблюдайте обязательно все пробелы, как указано в примере!"
    )
    await update.message.reply_text(welcome_message)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик PDF файлов"""
    try:
        pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
        # Проверка типа файла
        if not update.message.document.mime_type == 'application/pdf':
            await update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF.")
            return
            
        # Проверка размера файла
        if update.message.document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f"❌ Размер файла превышает {MAX_FILE_SIZE // 1024 // 1024}MB. Пожалуйста, отправьте файл меньшего размера.")
            return
            
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as tmp_dir:

            pdf_path = 'qwer.pdf'  # Замените на путь к вашему PDF
    
            if not os.path.exists(pdf_path):
                print(f"Файл {pdf_path} не найден!")
                return
    
        # Область для обработки: (x0, y0, x1, y1) в пунктах
            crop_region = (113, 30, 995, 670)
    
            print("Начинаем анализ указанной области PDF...")
            results = analyze_pdf_region(pdf_path, crop_region)
    
    # Вывод результатов в консоль
            print_region_results(results)
    
    # Экспорт в файл
            output_file = 'extracted_region_text.txt'
            export_region_to_file(results, output_file)
            print(f"\nРезультаты области сохранены в файл: {output_file}")

            # Этап 1: Поиск оборудования на сайтах (web_scraping)
            await update.message.reply_text(f"🌐 Ищу оборудование на {len(SEARCH_SITES)} сайтах...")
            scraped_data = []
            for item in equipment_data:
                results = search_equipment_on_sites(item['name'])
                scraped_data.append(results)
            
            # Этап 2: Генерация отчетов (excel_generator)
            await update.message.reply_text("📊 Формирую отчеты...")
            
            # Отчет 1: Результаты поиска
            search_report = create_search_report(equipment_data, scraped_data)
            report_buffer = io.BytesIO()
            search_report.save(report_buffer)  # Сохраняем в буфер
            report_buffer.seek(0)  # Перемещаем указатель в начало
        
            await update.message.reply_document(
                document=InputFile(report_buffer, filename='search_report.xlsx'),
                caption="✅ Результаты поиска оборудования\n\n"
                    "Цветовая маркировка статусов:\n"
                    "🟢 Зеленый - полностью доступно\n"
                    "🔵 Синий - требуется запрос\n"
                    "🟠 Оранжевый - мало остаток\n"
                    "🔴 Красный - недоступно\n"
                    "🟡 Желтый - санкционное оборудование"
            )
            
            # Отчет 2: Коммерческое предложение
            await update.message.reply_text("💼 Формирую коммерческое предложение...")
            commercial_report = create_commercial_offer(equipment_data, scraped_data)
            commercial_buffer = io.BytesIO()
            commercial_report.save(commercial_buffer)  # Сохраняем в буфер
            commercial_buffer.seek(0)  # Перемещаем указатель в начало
        
            await update.message.reply_document(
                document=InputFile(commercial_buffer, filename='commercial_offer.xlsx'),
                caption="✅ Коммерческое предложение сформировано"
            )
            
            # Финализация
            await update.message.reply_text("🎉 Обработка завершена успешно! Если у вас есть еще файлы, отправьте их сейчас.")
    
    except Exception as e:
        logger.error(f"Ошибка обработки PDF: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке вашего файла. Пожалуйста, попробуйте позже или обратитесь к администратору.")

def main():
    """Основная функция запуска бота"""
    try:
        # Очистка старого кэша
        cache.clear_old_cache()
        
        # Создаем экземпляр Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Text(), handle_text))
        application.add_error_handler(handle_error)
        
        # Запускаем бота
        logger.info("Бот запущен и ожидает сообщений...")
        
        # Запускаем polling в отдельном event loop
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        # Принудительный выход при критической ошибке
        os._exit(1)

if __name__ == '__main__':
    main()