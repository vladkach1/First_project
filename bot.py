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
    ContextTypes,
    CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
from utils.pdf_to_img import crop_page_to_region,extract_text_from_region,analyze_pdf_region,print_region_results,export_region_to_file,parse_excel_to_structure
from utils.ocr_processing import extract_text_from_image
from utils.text_analysis import parse_equipment_spec
from utils.web_scraping import search_equipment_on_sites
from utils.excel_generator import create_search_report, create_commercial_offer
from error_handler import handle_error
from cache import cache
from config import BOT_TOKEN, MAX_FILE_SIZE, SEARCH_SITES
import os
import logging
import asyncio
import tempfile
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import re
from openpyxl import load_workbook
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("TelegramBot")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start с инлайн-кнопкой"""
    user = update.effective_user
    
    # Создаем инлайн-клавиатуру
    keyboard = [
        [InlineKeyboardButton("📖 Инструкция", callback_data='instruction')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для анализа спецификаций оборудования. Просто отправь мне PDF или Excel файл со списком оборудования, и я:\n\n"
        "• Проанализирую спецификацию 📋\n"
        "• Найду лучшие цены на сайтах поставщиков 🌐\n"
        "• Предоставлю отчет и коммерческое предложение 📊\n\n"
        "Формат данных в файле должен быть:\n"
        "• Кабель 305 м\n"
        "• Тросс 4 мм\n"
        "• Видеокамера 2 шт\n\n"
        "Каждое наименование с новой строки!\n\n"
        "Нажми кнопку 'Инструкция' для подробного руководства 👇"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'instruction':
        instruction_text = (
            "📖 ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БОТА\n\n"
            "1. 📄 ПОДГОТОВЬТЕ ФАЙЛ\n"
            "   • Формат: PDF или Excel (.xlsx)\n"
            "   • Данные должны быть в формате: 'Наименование Количество Единица'\n"
            "   • Пример: 'Кабель 305 м', 'Видеокамера 2 шт'\n\n"
            "2. 📤 ОТПРАВЬТЕ ФАЙЛ БОТУ\n"
            "   • Просто перетащите файл в чат или используйте скрепку\n"
            "   • Максимальный размер: 20MB\n\n"
            "3. ⏳ ДОЖДИТЕСЬ ОБРАБОТКИ\n"
            "   • Бот проанализирует файл (1-2 минуты)\n"
            "   • Выполнит поиск на сайтах поставщиков\n"
            "   • Сгенерирует отчеты\n\n"
            "4. 📥 ПОЛУЧИТЕ РЕЗУЛЬТАТЫ\n"
            "   • Search Report.xlsx - детальные результаты поиска\n"
            "   • Commercial Offer.xlsx - готовое коммерческое предложение\n\n"
            "❓ ЕСЛИ ВОЗНИКЛИ ПРОБЛЕМЫ:\n"
            "   • Проверьте формат данных в файле\n"
            "   • Убедитесь, что файл не поврежден\n"
            "   • Обратитесь к администраторам: @vlad_pash или @shishqo"
        )
        await query.edit_message_text(instruction_text)

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик PDF файлов"""
    try:
        pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'
        document = update.message.document
        file_id = document.file_id
        file_name = document.file_name
        file = await context.bot.get_file(file_id)
        string_list=[]

        # Отправляем сообщение о начале обработки
        await update.message.reply_text("🔄 Начинаю обработку файла...")
        
        if update.message.document.mime_type == 'application/pdf':
            await file.download_to_drive("temp.pdf")
            pdf_path = "temp.pdf"
    
            if not os.path.exists(pdf_path):
                await update.message.reply_text("❌ Файл не найден после загрузки!")
                return
    
            # Область для обработки: (x0, y0, x1, y1) в пунктах
            crop_region = (113, 30, 995, 670)
    
            await update.message.reply_text("📄 Анализирую PDF файл...")
            results = analyze_pdf_region(pdf_path, crop_region)
    
            # Вывод результатов в консоль
            print_region_results(results)
    
            # Экспорт в файл
            output_file = 'extracted_region_text.txt'
            string_list = export_region_to_file(results, output_file)
        elif file_name and file_name.lower().endswith('.xlsx'):
            await file.download_to_drive("temp.xlsx")
            pdf_path = "temp.xlsx"
            await update.message.reply_text("📊 Анализирую Excel файл...")
            # Загружаем Excel файл
            data = parse_excel_to_structure(pdf_path)

        # Выводим результат
            print("Структура данных:")
            print(data)               
        else:
            await update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF или XLSX.")
            return
            
            
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as tmp_dir:
            
            if update.message.document.mime_type == 'application/pdf':
                data=[]

                for i in string_list:
                    data.append(i.rsplit(' ',2))

            equipment_data = []
            name_data = []
            for i in data:
                if (len(i)==1):
                    name_data.append(i[0])
                elif (len(i)==3):
                    if bool(re.fullmatch(r'\d+\.?\d*', i[2])):
                        item = {
                                'name': i[0],
                                'quantity': float(i[2]),
                                'unit': i[1]
                            }
                        name_data.append(i[0])
                        equipment_data.append(item)
                    else:
                        print("неправильное количество ",i[2])
                else:
                    print("неправильное list ",i,len(i))
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
                    "🔵 Синий - требуется запрос на покупку\n"
                    "🟠 Оранжевый - мало по наличию\n"
                    "🔴 Красный - недоступно\n"
                    "🟡 Желтый - санкционное оборудование"
            )
            
            # Отчет 2: Коммерческое предложение
            await update.message.reply_text("💼 Формирую коммерческое предложение...")
            commercial_report = create_commercial_offer(equipment_data, scraped_data,name_data)
            commercial_buffer = io.BytesIO()
            commercial_report.save(commercial_buffer)  # Сохраняем в буфер
            commercial_buffer.seek(0)  # Перемещаем указатель в начало
        
            await update.message.reply_document(
                document=InputFile(commercial_buffer, filename='commercial_offer.xlsx'),
                caption="✅ Коммерческое предложение сформировано"
            )
            # Финализация
            await update.message.reply_text(
                "🎉 Обработка завершена успешно!\n\n"
                "Если у вас есть еще файлы, отправьте их сейчас.\n\n"
                "❓ Нужна помощь? Обращайтесь к администраторам: @vlad_pash или @shishqo"
            )
            
        # Очистка временных файлов
        if os.path.exists("temp.pdf"):
            os.unlink("temp.pdf")
        if os.path.exists("temp.xlsx"):
            os.unlink("temp.xlsx")
    
    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке вашего файла.\n\n"
            "Пожалуйста:\n"
            "1. Проверьте формат файла\n"
            "2. Убедитесь, что данные соответствуют примеру\n"
            "3. Попробуйте позже или обратитесь к администраторам: @vlad_pash или @shishqo"
        )

def main():
    """Основная функция запуска бота"""
    try:
        # Очистка старого кэша
        cache.clear_old_cache()
        
        # Создаем экземпляр Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
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