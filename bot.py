import os
import logging
import asyncio
import tempfile
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import numpy as np
import cv2
import subprocess
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PDFEquipmentBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            "Я бот для конвертации PDF спецификаций оборудования в Excel.\n\n"
            "📋 Особенности обработки:\n"
            "• Автоматическое восстановление поврежденных PDF\n"
            "• Постраничное OCR распознавание\n"
            "• Обработка CID символов\n"
            "• Специализированный парсинг технических спецификаций\n\n"
            "📎 Просто отправь мне PDF файл!"
        )
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "ℹ️ Помощь по использованию бота:\n\n"
            "1. 📎 Отправь PDF файл с оборудованием\n"
            "2. ⏳ Я автоматически восстановлю файл если нужно\n"
            "3. 🔍 Использую высококачественное OCR\n"
            "4. 📊 Верну чистый Excel с данными\n\n"
            "Поддерживаю даже сильно поврежденные файлы!"
        )
        await update.message.reply_text(help_text)
    
    def repair_pdf_with_mutool(self, input_pdf_path: str) -> str:
        """Восстанавливает PDF с помощью mutool"""
        try:
            output_path = input_pdf_path.replace('.pdf', '_repaired.pdf')
            
            # Команда для восстановления PDF
            cmd = [
                'mutool', 'clean', '-d', '-g', '-z', '-s',
                input_pdf_path, output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("PDF успешно восстановлен с помощью mutool")
                return output_path
            else:
                logger.warning(f"mutool не смог восстановить PDF: {result.stderr}")
                return input_pdf_path
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.warning(f"Ошибка при использовании mutool: {e}")
            return input_pdf_path
    
    def convert_pdf_to_images(self, pdf_path: str) -> list:
        """Конвертирует PDF в список изображений с обработкой ошибок"""
        images = []
        try:
            # Пытаемся открыть PDF с восстановлением
            try:
                doc = fitz.open(pdf_path)
            except Exception as e:
                logger.warning(f"Ошибка открытия PDF: {e}, пробуем восстановить...")
                repaired_path = self.repair_pdf_with_mutool(pdf_path)
                doc = fitz.open(repaired_path)
            
            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    
                    # Высокое разрешение для качественного OCR
                    mat = fitz.Matrix(4.0, 4.0)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    images.append(img)
                    
                except Exception as page_error:
                    logger.warning(f"Ошибка обработки страницы {page_num}: {page_error}")
                    continue
            
            doc.close()
            logger.info(f"Конвертировано {len(images)} страниц в изображения")
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF: {e}")
        
        return images
    
    def enhance_image_for_technical_ocr(self, img: Image.Image) -> Image.Image:
        """Специальное улучшение изображения для технических документов"""
        try:
            img_array = np.array(img)
            
            if len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_array
            
            # Адаптивное пороговое преобразование
            gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 11, 2)
            
            # Морфологические операции для очистки
            kernel = np.ones((1, 1), np.uint8)
            gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            gray = cv2.medianBlur(gray, 3)
            
            # Увеличение резкости
            kernel_sharp = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            gray = cv2.filter2D(gray, -1, kernel_sharp)
            
            return Image.fromarray(gray)
            
        except Exception as e:
            logger.error(f"Ошибка улучшения изображения: {e}")
            return img
    
    def ocr_from_image(self, img: Image.Image) -> str:
        """Распознает текст с изображения с помощью OCR"""
        try:
            enhanced_img = self.enhance_image_for_technical_ocr(img)
            
            # Специальные настройки для технических документов
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789-–—.,()№"/\\|× '
            
            text = pytesseract.image_to_string(enhanced_img, lang='rus+eng', config=custom_config)
            return text
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            return ""
    
    def extract_text_from_pdf_via_ocr(self, pdf_path: str) -> str:
        """Извлекает текст из PDF через OCR изображений"""
        full_text = ""
        
        try:
            images = self.convert_pdf_to_images(pdf_path)
            
            if not images:
                logger.error("Не удалось конвертировать PDF в изображения")
                return ""
            
            for i, img in enumerate(images):
                logger.info(f"Обрабатываю страницу {i+1}/{len(images)}")
                
                page_text = self.ocr_from_image(img)
                
                if page_text.strip():
                    full_text += f"--- Страница {i+1} ---\n{page_text}\n\n"
                else:
                    logger.warning(f"Не удалось распознать текст на странице {i+1}")
            
            logger.info(f"Распознано {len(full_text)} символов текста")
            
        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
        
        return full_text
    
    def parse_technical_specification(self, text: str) -> list:
        """Специализированный парсер для технических спецификаций"""
        equipment_data = []
        lines = text.split('\n')
        
        current_section = ""
        in_table = False
        
        # Словарь для разделов оборудования
        section_keywords = {
            'прибор': 'Приборы и блоки',
            'блок': 'Приборы и блоки',
            'индикац': 'Индикаторы',
            'извещатель': 'Извещатели',
            'источник': 'Источники питания',
            'отображен': 'Отображение',
            'оповещатель': 'Оповещатели',
            'кабель': 'Кабели и провода',
            'материал': 'Материалы',
            'прочий': 'Прочие устройства'
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем служебные строки
            if any(x in line.lower() for x in ['страница', 'лист', 'дата', 'подпись']):
                continue
            
            # Определяем разделы
            line_lower = line.lower()
            for keyword, section in section_keywords.items():
                if keyword in line_lower:
                    current_section = section
                    in_table = True
                    break
            
            # Пропускаем заголовки таблиц
            if any(x in line_lower for x in ['наименован', 'техническ', 'характерист', 'тип', 'модель', 'код']):
                in_table = True
                continue
            
            # Парсим строки с оборудованием
            if in_table and current_section:
                equipment = self.parse_equipment_line(line, current_section)
                if equipment:
                    equipment_data.append(equipment)
        
        return equipment_data
    
    def parse_equipment_line(self, line: str, section: str) -> dict:
        """Парсит строку с оборудованием для технических спецификаций"""
        line = re.sub(r'\s+', ' ', line.strip())
        
        if len(line) < 5:
            return None
        
        # Пропускаем служебные строки
        if any(x in line.lower() for x in ['заказ', 'проект', 'смета', 'итого', 'всего']):
            return None
        
        # Ищем количество в конце строки
        quantity_match = re.search(r'(\d+)\s*(шт|м|кг|компл|уп|блок|лист|мм|см|м)?\.?\s*$', line.lower())
        if not quantity_match:
            return None
        
        quantity = quantity_match.group(1)
        unit = quantity_match.group(2) or 'шт'
        
        # Удаляем количество из строки
        line = line[:quantity_match.start()].strip()
        
        # Ищем модель/артикул (типа R1-PHEX-X 201, №330° X/2.5 PS-R3 и т.д.)
        model_patterns = [
            r'([A-ZА-Я0-9][A-ZА-Я0-9\-–—\.\/\s]+[A-ZА-Я0-9])\s*$',
            r'(№?\s*[0-9\-–—\.\/]+[A-ZА-Я]?[0-9]?)\s*$',
            r'([A-Z]{2,}[\-\s]*[0-9]+[A-Z0-9\-]*)',
            r'(Smart\s+[A-Z0-9\-]+)',
            r'([A-Z]+-[A-Z]+-[A-Z0-9]+)'  # Для формата типа R1-PHEX-X
        ]
        
        model = ""
        for pattern in model_patterns:
            match = re.search(pattern, line)
            if match:
                model = match.group(1).strip()
                line = line[:match.start()].strip()
                break
        
        # Оставшаяся часть - название оборудования
        name = line.strip()
        
        # Фильтруем мусор и слишком короткие названия
        if not name or len(name) < 3:
            return None
        
        return {
            'Раздел': section,
            'Наименование_оборудования': name,
            'Модель_Артикул': model,
            'Количество': quantity,
            'Единица_измерения': unit
        }
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик PDF документов"""
        document = update.message.document
        
        if not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("❌ Пожалуйста, отправьте PDF файл.")
            return
        
        status_message = await update.message.reply_text("🔄 Начинаю обработку PDF...")
        
        tmp_pdf_path = None
        tmp_excel_path = None
        
        try:
            # Создаем временные файлы
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_excel:
                tmp_excel_path = tmp_excel.name
            
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(tmp_pdf_path)
            
            await status_message.edit_text("🔧 Проверяю и восстанавливаю PDF...")
            
            # Извлекаем текст через OCR изображений
            text = self.extract_text_from_pdf_via_ocr(tmp_pdf_path)
            
            if not text or len(text.strip()) < 100:
                await status_message.edit_text("❌ Не удалось распознать текст из PDF.")
                return
            
            await status_message.edit_text("🔍 Анализирую технические спецификации...")
            
            # Парсим данные оборудования
            equipment_data = self.parse_technical_specification(text)
            
            if not equipment_data:
                # Покажем sample для диагностики
                sample = text[:500] + "..." if len(text) > 500 else text
                await update.message.reply_text(
                    f"❌ Не удалось найти данные оборудования.\n"
                    f"Пример распознанного текста:\n{sample}"
                )
                return
            
            await status_message.edit_text("💾 Создаю Excel файл...")
            
            # Создаем DataFrame
            df = pd.DataFrame(equipment_data)
            
            # Очищаем и структурируем данные
            df = df.drop_duplicates()
            df = df[df['Наименование_оборудования'].str.len() > 2]
            
            # Сохраняем в Excel
            df.to_excel(tmp_excel_path, index=False, engine='openpyxl')
            
            # Отправляем результат
            await status_message.edit_text("✅ Обработка завершена!")
            
            with open(tmp_excel_path, 'rb') as excel_file:
                await update.message.reply_document(
                    document=excel_file,
                    filename="Техническая_спецификация.xlsx",
                    caption=(
                        f"📋 Результат обработки технической спецификации:\n"
                        f"• Страниц обработано: {text.count('--- Страница')}\n"
                        f"• Позиций оборудования: {len(df)}\n"
                        f"• Качество: Высокое"
                    )
                )
            
            # Статистика
            if not df.empty:
                stats = df['Раздел'].value_counts()
                stats_text = "\n".join([f"• {k}: {v} поз." for k, v in stats.items()])
                await update.message.reply_text(f"📊 Распределение по разделам:\n{stats_text}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка обработки: {str(e)}")
        
        finally:
            # Очистка временных файлов
            for file_path in [tmp_pdf_path, tmp_excel_path]:
                if file_path and os.path.exists(file_path):
                    try:
                        os.unlink(file_path)
                    except:
                        pass
            try:
                await status_message.delete()
            except:
                pass
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот для обработки технических спецификаций запущен")
        print("🤖 Бот для обработки технических спецификаций запущен!")
        print("📎 Готов к приему PDF файлов...")
        self.application.run_polling()

# Токен бота
BOT_TOKEN = "8246578993:AAGaUxNEW2LCIdh6qLp3Ee9fyTY0z8muMc4"

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Укажите действительный BOT_TOKEN")
        exit(1)
    
    # Проверяем наличие Tesseract
    try:
        pytesseract.get_tesseract_version()
        print("✅ Tesseract OCR доступен")
    except:
        print("❌ Tesseract OCR не установлен")
        print("Установите: https://github.com/UB-Mannheim/tesseract/wiki")
        exit(1)
    
    # Проверяем наличие mutool
    try:
        subprocess.run(['mutool', '--version'], capture_output=True, check=True)
        print("✅ mutool доступен для восстановления PDF")
    except:
        print("⚠️  mutool не установлен (опционально для восстановления PDF)")
        print("Установите: https://mupdf.com/downloads/index.html")
    
    bot = PDFEquipmentBot(BOT_TOKEN)
    bot.run()