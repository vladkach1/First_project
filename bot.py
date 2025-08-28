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
        # Проверка типа файла
        #if not update.message.document.mime_type == 'application/pdf':
        #    await update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF.")
        #    return
            
        # Проверка размера файла
        #if update.message.document.file_size > MAX_FILE_SIZE:
        #    await update.message.reply_text(f"❌ Размер файла превышает {MAX_FILE_SIZE // 1024 // 1024}MB. Пожалуйста, отправьте файл меньшего размера.")
        #    return
            
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Скачиваем файл
            #pdf_file = await context.bot.get_file(update.message.document.file_id)
            #pdf_path = os.path.join(tmp_dir, 'document.pdf')
            #await pdf_file.download_to_drive(pdf_path)
            
            # Уведомление пользователя
            #await update.message.reply_text("📥 Файл получен. Начинаю обработку...")
            
            # Этап 1: Конвертация PDF в изображения
            #await update.message.reply_text("🔄 Конвертирую PDF в изображения...")
            #img_paths = convert_pdf_to_images(pdf_path, tmp_dir)
            
            #if not img_paths:
            #    await update.message.reply_text("❌ Не удалось конвертировать PDF. Пожалуйста, убедитесь, что файл не поврежден.")
            #    return
            
            # Этап 2: OCR обработка
            #await update.message.reply_text("🔍 Распознаю текст с изображений...")
            #full_text = ""
            #for img_path in img_paths:
            #    text = extract_text_from_image(img_path)
            #    full_text += text + "\n\n"
            # Этап 3: Анализ текста
            #await update.message.reply_text("📊 Анализирую спецификацию оборудования...")
            #equipment_data = parse_equipment_spec(full_text)
            
            #if not equipment_data:
            #    await update.message.reply_text("❌ Не удалось найти данные оборудования в документе. Убедитесь, что в PDF есть таблица со спецификацией.")
            #    return

            # НАЧАЛО НОВОГО ЭТАПА В НАШЕЙ ЖИЗНИ
            
            user_text = update.message.text
            
            lines = user_text.split('\n')

            data=[]

            for i in lines:
                data.append(i.rsplit(' ',2))

            item={}

            equipment_data = []
            for i,elem in enumerate(data,1):
                if (len(elem)==3):
                    if bool(re.match(r'^[0-9]+[\.|\,]?[0-9]*$', elem[1])):
                        item = {
                                'name': elem[0],
                                'quantity': float(elem[1]),
                                'unit': elem[2]
                            }
                    else:
                        await update.message.reply_text(f"❌ Некоректная строка №{i}")
                        continue
                else:
                    await update.message.reply_text(f"❌ Некоректная строка №{i}")
                    continue
                equipment_data.append(item)

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