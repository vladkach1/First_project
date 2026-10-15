import os
import tempfile
import re
import logging
import asyncio
import io

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

from config import BOT_TOKEN, MAX_FILE_SIZE, SEARCH_SITES, PROGRESS_BATCH_SIZE
from utils.pdf_to_img import (
    analyze_pdf_region, print_region_results,
    export_region_to_file, parse_excel_to_structure
)
from utils.web_scraping import search_equipment_on_sites_async, close_browser
from utils.excel_generator import create_search_report, create_commercial_offer
from error_handler import handle_error
from cache import cache

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("TelegramBot")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start с инлайн-кнопкой"""
    user = update.effective_user

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
        # Сначала отправляем текстовое сообщение
        await query.edit_message_text(
            "📖 Вот примеры файлов, которые можно подать на вход:"
        )
        
        # Пути к файлам-примерам (нужно создать эти файлы в папке examples/)
        example_pdf_path = "examples/example_specification.pdf"
        example_excel_path = "examples/example_specification.xlsx"
        
        # Проверяем существование файлов и отправляем их
        if os.path.exists(example_pdf_path):
            with open(example_pdf_path, 'rb') as pdf_file:
                await query.message.reply_document(
                    document=InputFile(pdf_file, filename='example_specification.pdf'),
                    caption="📄 Пример PDF файла со спецификацией"
                )
        else:
            # Если файл не найден, отправляем сообщение-заглушку
            await query.message.reply_text(
                "⚠️ Файл примера PDF не найден. Пожалуйста, создайте файл example_specification.pdf в папке examples/"
            )
        
        if os.path.exists(example_excel_path):
            with open(example_excel_path, 'rb') as excel_file:
                await query.message.reply_document(
                    document=InputFile(excel_file, filename='example_specification.xlsx'),
                    caption="📊 Пример Excel файла со спецификацией"
                )
        else:
            # Если файл не найден, отправляем сообщение-заглушку
            await query.message.reply_text(
                "⚠️ Файл примера Excel не найден. Пожалуйста, создайте файл example_specification.xlsx в папке examples/"
            )
        
        # Отправляем полную инструкцию отдельным сообщением
        instruction_text = (
            "📖 **ПОЛНАЯ ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БОТА**\n\n"
            "**1. 📄 ПОДГОТОВЬТЕ ФАЙЛ**\n"
            "   • Формат: PDF или Excel (.xlsx)\n"
            "   • Данные должны быть в формате: 'Наименование Количество Единица'\n"
            "   • Пример: 'Кабель 305 м', 'Видеокамера 2 шт'\n\n"
            "**2. 📤 ОТПРАВЬТЕ ФАЙЛ БОТУ**\n"
            "   • Просто перетащите файл в чат или используйте скрепку\n"
            "   • Максимальный размер: 20MB\n\n"
            "**3. ⏳ ДОЖДИТЕСЬ ОБРАБОТКИ**\n"
            "   • Бот проанализирует файл (1-2 минуты)\n"
            "   • Выполнит поиск на сайтах поставщиков\n"
            "   • Сгенерирует отчеты\n\n"
            "**4. 📥 ПОЛУЧИТЕ РЕЗУЛЬТАТЫ**\n"
            "   • Search Report.xlsx - детальные результаты поиска\n"
            "   • Commercial Offer.xlsx - готовое коммерческое предложение\n\n"
            "**❓ ЕСЛИ ВОЗНИКЛИ ПРОБЛЕМЫ:**\n"
            "   • Проверьте формат данных в файле\n"
            "   • Убедитесь, что файл не поврежден\n"
            "   • Обратитесь к администраторам: @vlad_pash или @shishqo"
        )
        await query.message.reply_text(instruction_text, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов (PDF / XLSX)"""
    temp_path = None
    try:
        document = update.message.document
        file_name = document.file_name or ""
        mime_type = document.mime_type or ""

        # Проверка размера файла
        if document.file_size and document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ Файл слишком большой ({document.file_size // (1024*1024)} MB). "
                f"Максимум: {MAX_FILE_SIZE // (1024*1024)} MB."
            )
            return

        is_pdf = mime_type == 'application/pdf'
        is_xlsx = file_name.lower().endswith('.xlsx')

        if not is_pdf and not is_xlsx:
            await update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF или XLSX.")
            return

        await update.message.reply_text("🔄 Начинаю обработку файла...")

        # Скачиваем во временный файл
        suffix = '.pdf' if is_pdf else '.xlsx'
        tg_file = await context.bot.get_file(document.file_id)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = tmp.name
        tmp.close()
        await tg_file.download_to_drive(temp_path)

        # Парсим файл
        if is_pdf:
            crop_region = (113, 30, 995, 670)
            await update.message.reply_text("📄 Анализирую PDF файл...")
            results = await asyncio.to_thread(analyze_pdf_region, temp_path, crop_region)
            print_region_results(results)
            string_list = export_region_to_file(results, 'extracted_region_text.txt')

            data = []
            for i in string_list:
                data.append(i.rsplit(' ', 2))
        else:
            await update.message.reply_text("📊 Анализирую Excel файл...")
            data = await asyncio.to_thread(parse_excel_to_structure, temp_path)
            logger.info(f"Структура данных: {len(data)} строк")

        # Разбираем данные
        equipment_data = []
        name_data = []
        for i in data:
            if len(i) == 1:
                name_data.append(i[0])
            elif len(i) == 3:
                if re.fullmatch(r'\d+\.?\d*', i[2]):
                    equipment_data.append({
                        'name': i[0],
                        'quantity': float(i[2]),
                        'unit': i[1]
                    })
                    name_data.append(i[0])
                else:
                    logger.warning(f"Неправильное количество: '{i[2]}' в строке {i}")
            else:
                logger.warning(f"Неправильный формат строки: {i}")

        if not equipment_data:
            await update.message.reply_text(
                "❌ Не удалось извлечь данные оборудования из файла.\n"
                "Проверьте формат данных."
            )
            return

        # ── Этап 1: Поиск на сайтах (с дедупликацией и батчами) ──────

        # Дедупликация: ищем только уникальные наименования
        unique_names = list(dict.fromkeys(item['name'] for item in equipment_data))
        total_unique = len(unique_names)
        total_all = len(equipment_data)
        dedup_saved = total_all - total_unique

        info_msg = f"🌐 Ищу {total_unique} уникальных позиций на {len(SEARCH_SITES)} сайтах..."
        if dedup_saved > 0:
            info_msg += f"\n(пропущено {dedup_saved} дубликатов)"
        await update.message.reply_text(info_msg)

        # Прогресс-сообщение (одно, обновляется)
        progress_msg = await update.message.reply_text(
            f"⏳ 0/{total_unique} позиций..."
        )

        # Батчевая обработка с прогрессом
        unique_results = {}
        batch_size = PROGRESS_BATCH_SIZE

        for batch_start in range(0, total_unique, batch_size):
            batch = unique_names[batch_start:batch_start + batch_size]
            tasks = [search_equipment_on_sites_async(name) for name in batch]
            batch_results = await asyncio.gather(*tasks)

            for name, result in zip(batch, batch_results):
                unique_results[name] = result

            processed = min(batch_start + batch_size, total_unique)
            try:
                await progress_msg.edit_text(
                    f"⏳ {processed}/{total_unique} позиций обработано..."
                )
            except Exception:
                pass  # Telegram rate limit на edit

        # Маппинг обратно на все позиции (включая дубликаты)
        scraped_data = [unique_results.get(item['name'], []) for item in equipment_data]

        try:
            await progress_msg.edit_text(f"✅ Поиск завершён: {total_unique} позиций")
        except Exception:
            pass

        # ── Этап 2: Генерация отчётов ────────────────────────────────

        await update.message.reply_text("📊 Формирую отчеты...")

        search_report = await asyncio.to_thread(
            create_search_report, equipment_data, scraped_data
        )
        if search_report:
            report_buffer = io.BytesIO()
            search_report.save(report_buffer)
            report_buffer.seek(0)
            await update.message.reply_document(
                document=InputFile(report_buffer, filename='search_report.xlsx'),
                caption=(
                    "✅ Результаты поиска оборудования\n\n"
                    "Цветовая маркировка статусов:\n"
                    "🟢 Зеленый - полностью доступно\n"
                    "🔵 Синий - требуется запрос на покупку\n"
                    "🟠 Оранжевый - мало по наличию\n"
                    "🔴 Красный - недоступно\n"
                    "🟡 Желтый - санкционное оборудование"
                )
            )
        else:
            await update.message.reply_text("⚠️ Не удалось найти подходящие предложения для отчёта.")

        await update.message.reply_text("💼 Формирую коммерческое предложение...")
        commercial_report = await asyncio.to_thread(
            create_commercial_offer, equipment_data, scraped_data, name_data
        )
        if commercial_report:
            commercial_buffer = io.BytesIO()
            commercial_report.save(commercial_buffer)
            commercial_buffer.seek(0)
            await update.message.reply_document(
                document=InputFile(commercial_buffer, filename='commercial_offer.xlsx'),
                caption="✅ Коммерческое предложение сформировано"
            )
        else:
            await update.message.reply_text("⚠️ Не удалось сформировать коммерческое предложение.")

        await update.message.reply_text(
            "🎉 Обработка завершена!\n\n"
            "Если у вас есть еще файлы, отправьте их сейчас.\n\n"
            "❓ Нужна помощь? Обращайтесь к администраторам: @vlad_pash или @shishqo"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке вашего файла.\n\n"
            "Пожалуйста:\n"
            "1. Проверьте формат файла\n"
            "2. Убедитесь, что данные соответствуют примеру\n"
            "3. Попробуйте позже или обратитесь к администраторам: @vlad_pash или @shishqo"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def post_shutdown(application):
    """Cleanup при остановке бота — закрываем shared-браузер."""
    await close_browser()


def main():
    """Основная функция запуска бота"""
    try:
        cache.clear_old_cache()

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_shutdown(post_shutdown)
            .build()
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_error_handler(handle_error)

        logger.info("Бот запущен и ожидает сообщений...")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        os._exit(1)


if __name__ == '__main__':
    main()
