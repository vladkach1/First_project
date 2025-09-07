import os
import pandas as pd
import pdfplumber
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import tempfile
import logging
import asyncio
import re
from openpyxl import Workbook, load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PDFToExcelBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(self.token).build()
        
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для конвертации PDF спецификаций в Excel. "
            "Просто отправь мне PDF-файл, и я преобразую его в таблицу Excel."
        )
    
    def pdf_to_excel(self, pdf_path, excel_path):
        """Конвертирует PDF в Excel, сохраняя структуру данных"""
        try:
            wb = Workbook()
            wb.remove(wb.active)  # Удаляем дефолтный лист
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Обработка страницы {page_num + 1}")
                    
                    # Создаем лист для каждой страницы
                    ws = wb.create_sheet(title=f"Страница_{page_num + 1}")
                    
                    # Извлекаем текст со страницы
                    text = page.extract_text()
                    if text:
                        # Записываем текст в Excel
                        lines = text.split('\n')
                        for row_idx, line in enumerate(lines, 1):
                            if line.strip():
                                ws.cell(row=row_idx, column=1, value=line.strip())
                    
                    # Пытаемся извлечь таблицы
                    tables = page.extract_tables()
                    logger.info(f"Найдено таблиц: {len(tables)}")
                    
                    for table_num, table in enumerate(tables):
                        if table:
                            # Создаем отдельный лист для каждой таблицы
                            table_ws = wb.create_sheet(title=f"Таблица_{page_num+1}_{table_num+1}")
                            
                            # Записываем таблицу в Excel
                            for row_idx, row in enumerate(table, 1):
                                for col_idx, cell in enumerate(row, 1):
                                    if cell:
                                        table_ws.cell(row=row_idx, column=col_idx, value=str(cell).strip())
            
            # Сохраняем Excel файл
            wb.save(excel_path)
            logger.info(f"Excel файл создан: {excel_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при конвертации PDF в Excel: {e}")
            return False
    
    def extract_data_from_excel(self, excel_path):
        """Извлекает и анализирует данные из Excel файла"""
        all_data = []
        
        try:
            wb = load_workbook(excel_path)
            logger.info(f"Открыт Excel файл с листами: {wb.sheetnames}")
            
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                logger.info(f"Анализ листа: {sheet_name}")
                
                # Собираем все данные с листа
                sheet_data = []
                for row in ws.iter_rows(values_only=True):
                    if any(cell for cell in row):
                        cleaned_row = [str(cell).strip() if cell else '' for cell in row]
                        sheet_data.append(cleaned_row)
                
                if sheet_data:
                    logger.info(f"На листе '{sheet_name}' найдено {len(sheet_data)} строк")
                    all_data.extend(sheet_data)
            
            return all_data
            
        except Exception as e:
            logger.error(f"Ошибка при чтении Excel: {e}")
            return []
    
    def process_to_final_excel(self, data, output_path):
        """Создает финальный Excel с обработанными данными"""
        if not data:
            return False
        
        try:
            # Создаем новый Excel файл для результата
            result_wb = Workbook()
            result_ws = result_wb.active
            result_ws.title = "Обработанные_данные"
            
            # Записываем данные
            for row_idx, row in enumerate(data, 1):
                for col_idx, value in enumerate(row, 1):
                    result_ws.cell(row=row_idx, column=col_idx, value=value)
            
            # Автоподбор ширины колонок
            for column in result_ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                result_ws.column_dimensions[column_letter].width = max_length + 2
            
            result_wb.save(output_path)
            logger.info(f"Финальный Excel создан: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при создании финального Excel: {e}")
            return False
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик документов (PDF файлов)"""
        user = update.message.from_user
        document = update.message.document
        
        # Проверяем, что файл является PDF
        if not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("Пожалуйста, отправьте PDF-файл.")
            return
        
        await update.message.reply_text("🔍 Начинаю обработку PDF-файла...")
        logger.info(f"Начата обработка файла: {document.file_name}")
        
        tmp_pdf_path = None
        tmp_intermediate_excel = None
        tmp_final_excel = None
        
        try:
            # Создаем временные файлы
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='_intermediate.xlsx') as tmp_excel:
                tmp_intermediate_excel = tmp_excel.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='_final.xlsx') as tmp_final:
                tmp_final_excel = tmp_final.name
            
            # Скачиваем PDF файл
            file_id = document.file_id
            file = await context.bot.get_file(file_id)
            await file.download_to_drive(tmp_pdf_path)
            logger.info(f"PDF файл скачан: {tmp_pdf_path}")
            
            # Шаг 1: Конвертируем PDF в промежуточный Excel
            await update.message.reply_text("📊 Конвертирую PDF в Excel...")
            conversion_success = self.pdf_to_excel(tmp_pdf_path, tmp_intermediate_excel)
            
            if not conversion_success:
                await update.message.reply_text("❌ Не удалось конвертировать PDF в Excel.")
                return
            
            # Шаг 2: Извлекаем данные из промежуточного Excel
            await update.message.reply_text("🔍 Анализирую данные в Excel...")
            excel_data = self.extract_data_from_excel(tmp_intermediate_excel)
            
            if not excel_data:
                await update.message.reply_text("⚠️ В Excel файле не найдено данных для обработки.")
                return
            
            logger.info(f"Извлечено {len(excel_data)} строк данных из Excel")
            
            # Шаг 3: Создаем финальный Excel
            await update.message.reply_text("💾 Создаю финальную таблицу...")
            final_success = self.process_to_final_excel(excel_data, tmp_final_excel)
            
            if not final_success:
                await update.message.reply_text("❌ Не удалось создать финальную таблицу.")
                return
            
            # Шаг 4: Отправляем результат пользователю
            with open(tmp_final_excel, 'rb') as final_file:
                await update.message.reply_document(
                    document=final_file,
                    filename=document.file_name.replace('.pdf', '_обработанный.xlsx'),
                    caption="✅ Файл успешно обработан! 📊"
                )
            
            # Также отправляем промежуточный Excel для отладки
            with open(tmp_intermediate_excel, 'rb') as intermediate_file:
                await update.message.reply_document(
                    document=intermediate_file,
                    filename=document.file_name.replace('.pdf', '_промежуточный.xlsx'),
                    caption="📋 Промежуточный файл (все данные)"
                )
            
            await update.message.reply_text(
                f"🎉 Обработка завершена успешно!\n"
                f"• Извлечено строк данных: {len(excel_data)}\n"
                f"• Отправлено 2 файла: обработанный и промежуточный"
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
        
        finally:
            # Удаляем временные файлы
            await asyncio.sleep(3)
            self.cleanup_files([tmp_pdf_path, tmp_intermediate_excel, tmp_final_excel])
    
    def cleanup_files(self, file_paths):
        """Удаляет временные файлы"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
                except PermissionError as e:
                    logger.warning(f"Не удалось удалить {file_path}: {e}")
    
    def run(self):
        """Запускает бота"""
        print("🤖 Бот запущен. Ожидание PDF файлов...")
        logger.info("Бот запущен")
        self.application.run_polling()

# Токен вашего бота
BOT_TOKEN = "8246578993:AAGaUxNEW2LCIdh6qLp3Ee9fyTY0z8muMc4"

if __name__ == "__main__":
    bot = PDFToExcelBot(BOT_TOKEN)
    bot.run()