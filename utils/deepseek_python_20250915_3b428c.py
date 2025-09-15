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
logger = logging.getLogger(__name__)

class ExcelEquipmentBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            "Я бот для обработки Excel файлов с оборудованием.\n\n"
            "📋 Что я умею:\n"
            "• Анализировать Excel файлы со спецификациями\n"
            "• Извлекать данные об оборудовании\n"
            "• Конвертировать в читаемый текстовый формат\n"
            "• Форматировать технические спецификации\n\n"
            "📎 Просто отправь мне Excel файл!"
        )
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "ℹ️ Помощь по использованию бота:\n\n"
            "1. 📎 Отправь Excel файл (.xlsx, .xls) с оборудованием\n"
            "2. ⏳ Я проанализирую структуру файла\n"
            "3. 📊 Извлеку данные об оборудовании\n"
            "4. 📝 Представлю в удобном текстовом формате\n\n"
            "Поддерживаю различные форматы технических спецификаций!"
        )
        await update.message.reply_text(help_text)
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text.lower()
        if text in ['привет', 'hello', 'hi', 'start']:
            await self.start_command(update, context)
        else:
            await update.message.reply_text(
                "Я понимаю команды и Excel файлы. "
                "Используй /help для справки или отправь мне Excel файл с оборудованием."
            )
    
    def detect_sheet_structure(self, df: pd.DataFrame) -> dict:
        """Определяет структуру листа Excel"""
        structure = {
            'has_headers': False,
            'columns_found': [],
            'data_start_row': 0,
            'equipment_columns': []
        }
        
        # Ищем заголовки
        for i, row in df.iterrows():
            row_text = ' '.join([str(cell) for cell in row if pd.notna(cell)])
            if any(keyword in row_text.lower() for keyword in 
                  ['наименование', 'название', 'оборудование', 'модель', 'артикул', 'количество']):
                structure['has_headers'] = True
                structure['data_start_row'] = i + 1
                structure['columns_found'] = [str(cell) for cell in row if pd.notna(cell)]
                break
        
        # Определяем колонки с оборудованием
        equipment_keywords = [
            'наименование', 'название', 'оборудование', 'модель', 
            'артикул', 'количество', 'единица', 'шт', 'компл'
        ]
        
        for col in df.columns:
            col_name = str(col).lower()
            if any(keyword in col_name for keyword in equipment_keywords):
                structure['equipment_columns'].append(col)
        
        return structure
    
    def extract_equipment_data(self, df: pd.DataFrame, structure: dict) -> list:
        """Извлекает данные об оборудовании из DataFrame"""
        equipment_data = []
        
        # Определяем колонки для извлечения
        name_col = None
        model_col = None
        quantity_col = None
        unit_col = None
        
        for col in df.columns:
            col_str = str(col).lower()
            if any(x in col_str for x in ['наименование', 'название', 'оборудование']):
                name_col = col
            elif any(x in col_str for x in ['модель', 'артикул', 'тип']):
                model_col = col
            elif any(x in col_str for x in ['количество', 'кол-во']):
                quantity_col = col
            elif any(x in col_str for x in ['единица', 'ед', 'шт', 'компл']):
                unit_col = col
        
        # Если не нашли автоматически, используем первые колонки
        if not name_col and len(df.columns) > 0:
            name_col = df.columns[0]
        if not model_col and len(df.columns) > 1:
            model_col = df.columns[1]
        if not quantity_col and len(df.columns) > 2:
            quantity_col = df.columns[2]
        if not unit_col:
            unit_col = 'шт'  # Значение по умолчанию
        
        # Извлекаем данные
        for index, row in df.iterrows():
            if index < structure['data_start_row']:
                continue
                
            # Пропускаем пустые строки
            if pd.isna(row.get(name_col, '')) and pd.isna(row.get(model_col, '')):
                continue
            
            equipment = {
                'Наименование': str(row.get(name_col, '')).strip(),
                'Модель': str(row.get(model_col, '')).strip(),
                'Количество': str(row.get(quantity_col, '1')).strip(),
                'Единица': str(row.get(unit_col, 'шт')).strip()
            }
            
            # Фильтруем пустые записи
            if equipment['Наименование'] or equipment['Модель']:
                equipment_data.append(equipment)
        
        return equipment_data
    
    def format_equipment_text(self, equipment_data: list, filename: str) -> str:
        """Форматирует данные оборудования в текстовый вид"""
        if not equipment_data:
            return "❌ Не удалось найти данные об оборудовании в файле."
        
        # Группируем по разделам (если есть категории)
        text_output = f"📋 СПЕЦИФИКАЦИЯ ОБОРУДОВАНИЯ\n"
        text_output += f"📄 Файл: {filename}\n"
        text_output += f"📊 Всего позиций: {len(equipment_data)}\n"
        text_output += "=" * 50 + "\n\n"
        
        # Форматируем каждую позицию
        for i, item in enumerate(equipment_data, 1):
            text_output += f"{i}. {item['Наименование']}\n"
            
            if item['Модель']:
                text_output += f"   Модель: {item['Модель']}\n"
            
            text_output += f"   Количество: {item['Количество']} {item['Единица']}\n"
            
            # Разделитель между позициями
            if i < len(equipment_data):
                text_output += "─" * 30 + "\n"
        
        # Добавляем итоги
        text_output += "\n" + "=" * 50 + "\n"
        text_output += f"ИТОГО: {len(equipment_data)} позиций оборудования\n"
        
        return text_output
    
    def process_excel_file(self, excel_path: str, filename: str) -> str:
        """Обрабатывает Excel файл и возвращает текстовый результат"""
        try:
            # Загружаем Excel файл
            wb = load_workbook(excel_path)
            all_equipment = []
            
            # Обрабатываем каждый лист
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                
                # Конвертируем в DataFrame
                data = ws.values
                cols = next(data)
                df = pd.DataFrame(data, columns=cols)
                
                # Определяем структуру
                structure = self.detect_sheet_structure(df)
                
                # Извлекаем данные
                sheet_equipment = self.extract_equipment_data(df, structure)
                all_equipment.extend(sheet_equipment)
            
            # Форматируем результат
            result_text = self.format_equipment_text(all_equipment, filename)
            return result_text
            
        except Exception as e:
            logger.error(f"Ошибка обработки Excel: {e}")
            return f"❌ Ошибка обработки файла: {str(e)}"
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик документов (Excel файлов)"""
        document = update.message.document
        filename = document.file_name
        
        # Проверяем, что файл является Excel
        if not filename.lower().endswith(('.xlsx', '.xls')):
            await update.message.reply_text("❌ Пожалуйста, отправьте Excel файл (.xlsx или .xls).")
            return
        
        status_message = await update.message.reply_text("🔄 Начинаю обработку Excel файла...")
        
        tmp_excel_path = None
        
        try:
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_excel:
                tmp_excel_path = tmp_excel.name
            
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(tmp_excel_path)
            
            await status_message.edit_text("📊 Анализирую структуру файла...")
            
            # Обрабатываем файл
            result_text = self.process_excel_file(tmp_excel_path, filename)
            
            # Разбиваем текст на части если он слишком длинный для Telegram
            max_length = 4000  # Лимит Telegram для сообщений
            if len(result_text) > max_length:
                parts = [result_text[i:i+max_length] for i in range(0, len(result_text), max_length)]
                
                for i, part in enumerate(parts, 1):
                    if i == 1:
                        await status_message.edit_text(f"📝 Часть {i}:\n{part}")
                    else:
                        await update.message.reply_text(f"📝 Часть {i}:\n{part}")
                    
                    # Небольшая пауза между сообщениями
                    await asyncio.sleep(1)
            else:
                await status_message.edit_text(result_text)
            
            logger.info(f"Успешно обработан файл: {filename}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Произошла ошибка при обработке файла: {str(e)}")
        
        finally:
            # Удаляем временный файл
            if tmp_excel_path and os.path.exists(tmp_excel_path):
                try:
                    os.unlink(tmp_excel_path)
                except:
                    pass
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот для обработки Excel файлов запущен")
        print("🤖 Бот для обработки Excel файлов с оборудованием запущен!")
        print("📎 Готов к приему Excel файлов...")
        self.application.run_polling()

# Токен бота
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Укажите действительный BOT_TOKEN")
        exit(1)
    
    # Проверяем наличие необходимых библиотек
    try:
        import pandas as pd
        from openpyxl import load_workbook
        print("✅ Все необходимые библиотеки установлены")
    except ImportError as e:
        print(f"❌ Не установлены необходимые библиотеки: {e}")
        print("Установите: pip install pandas openpyxl python-telegram-bot")
        exit(1)
    
    bot = ExcelEquipmentBot(BOT_TOKEN)
    bot.run()