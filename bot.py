import os
import logging
import asyncio
import tempfile
import pandas as pd
import pdfplumber
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import numpy as np
import cv2

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
            "📋 Что я умею:\n"
            "• Извлекать данные об оборудовании из PDF\n"
            "• Конвертировать в удобный Excel формат\n"
            "• Распознавать модели, количества и характеристики\n\n"
            "📎 Просто отправь мне PDF файл со спецификацией!"
        )
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "ℹ️ Помощь по использованию бота:\n\n"
            "1. 📎 Отправь мне PDF файл со спецификацией оборудования\n"
            "2. ⏳ Подожди немного пока я обработаю файл\n"
            "3. 📊 Получи Excel файл с извлеченными данными\n\n"
            "Поддерживаю даже сложные PDF с особыми шрифтами!"
        )
        await update.message.reply_text(help_text)
    
    def has_cid_text(self, pdf_path: str) -> bool:
        """Проверяет, содержит ли PDF CID текст"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                # Если текст содержит CID-символы или очень короткий
                return not text or len(text.strip()) < 50 or '(cid:' in text
        except:
            return True
    
    def extract_text_with_ocr(self, pdf_path: str) -> str:
        """Извлекает текст из PDF с помощью OCR"""
        full_text = ""
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Получаем изображение страницы с высоким разрешением
                mat = fitz.Matrix(3, 3)  # Высокое разрешение для лучшего OCR
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Преобразуем в изображение PIL
                img = Image.open(io.BytesIO(img_data))
                
                # Улучшаем изображение для OCR
                img = self.enhance_image(img)
                
                # Применяем OCR
                text = pytesseract.image_to_string(img, lang='rus+eng')
                full_text += f"--- Страница {page_num + 1} ---\n{text}\n\n"
            
            doc.close()
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
        
        return full_text
    
    def enhance_image(self, img: Image.Image) -> Image.Image:
        """Улучшает изображение для лучшего распознавания OCR"""
        try:
            # Конвертируем в numpy array
            img_array = np.array(img)
            
            # Конвертируем RGB в BGR для OpenCV
            if len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Увеличиваем контраст
            lab = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced_lab = cv2.merge((cl, a, b))
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Конвертируем обратно в RGB
            enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            return Image.fromarray(enhanced_rgb)
            
        except Exception as e:
            logger.error(f"Ошибка улучшения изображения: {e}")
            return img
    
    def extract_equipment_data(self, pdf_path: str) -> list:
        """Извлекает данные об оборудовании из PDF"""
        equipment_data = []
        
        # Проверяем тип PDF
        if self.has_cid_text(pdf_path):
            logger.info("Обнаружен PDF с CID текстом, использую OCR")
            text = self.extract_text_with_ocr(pdf_path)
            equipment_data = self.parse_text_data(text)
        else:
            logger.info("Обычный PDF, использую стандартное извлечение")
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            page_data = self.parse_text_data(text)
                            equipment_data.extend(page_data)
            except Exception as e:
                logger.error(f"Ошибка стандартного извлечения: {e}")
                # Пробуем OCR как fallback
                text = self.extract_text_with_ocr(pdf_path)
                equipment_data = self.parse_text_data(text)
        
        return equipment_data
    
    def parse_text_data(self, text: str) -> list:
        """Парсит текст для извлечения данных об оборудовании"""
        equipment_list = []
        lines = text.split('\n')
        
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем разделы
            section_keywords = {
                'приборы': 'Приборы и блоки',
                'блоки': 'Приборы и блоки',
                'индикаторы': 'Индикаторы',
                'источники': 'Источники питания',
                'отображение': 'Отображение',
                'устройства': 'Прочие устройства',
                'кабели': 'Кабели и провода'
            }
            
            for keyword, section in section_keywords.items():
                if keyword in line.lower():
                    current_section = section
                    break
            
            # Парсим строки с оборудованием
            equipment = self.parse_equipment_line(line, current_section)
            if equipment:
                equipment_list.append(equipment)
        
        return equipment_list
    
    def parse_equipment_line(self, line: str, section: str = "") -> dict:
        """Парсит строку для извлечения информации об оборудовании"""
        # Очищаем строку
        line = re.sub(r'\s+', ' ', line.strip())
        
        # Пропускаем служебные строки
        skip_keywords = ['страница', 'лист', 'дата', 'подпись', 'заказ', 'проект', 'смета']
        if any(keyword in line.lower() for keyword in skip_keywords):
            return None
        
        # Ищем количество
        quantity_patterns = [
            r'(\d+)\s*шт\.?$', r'(\d+)\s*м\.?$', r'(\d+)\s*кг\.?$',
            r'(\d+)\s*компл\.?$', r'(\d+)\s*уп\.?$', r'(\d+)\s*$'
        ]
        
        quantity = None
        unit = "шт."
        
        for pattern in quantity_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                quantity = match.group(1)
                # Определяем единицу измерения
                if 'м.' in pattern: unit = "м"
                elif 'кг.' in pattern: unit = "кг"
                elif 'компл.' in pattern: unit = "компл"
                elif 'уп.' in pattern: unit = "упак."
                line = line[:match.start()].strip()
                break
        
        if not quantity:
            return None
        
        # Ищем модель/артикул (обычно содержит цифры, буквы, дефисы)
        model_patterns = [
            r'([A-ZА-Я0-9\-–—\.\/]+(?:\s+[A-ZА-Я0-9\-–—\.\/]+)*)$',
            r'([A-ZА-Я]{2,}[\-\s]*[0-9]+[A-ZА-Я0-9\-]*)',
            r'(№?\s*[0-9\-–—]+[A-ZА-Я]*)'
        ]
        
        model = ""
        for pattern in model_patterns:
            match = re.search(pattern, line)
            if match:
                model = match.group(1).strip()
                line = line.replace(model, '').strip()
                break
        
        # Остаток - название
        name = line.strip()
        
        # Очищаем название от мусора
        name = re.sub(r'[^\w\sа-яА-ЯёЁ\-–—\.]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        if len(name) < 2:  # Слишком короткое название
            return None
        
        return {
            'Раздел': section,
            'Наименование': name,
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
        
        status_message = await update.message.reply_text("🔄 Обрабатываю PDF файл...")
        
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
            
            await status_message.edit_text("📊 Извлекаю данные...")
            
            # Извлекаем данные
            equipment_data = self.extract_equipment_data(tmp_pdf_path)
            
            if not equipment_data:
                await status_message.edit_text(
                    "❌ Не удалось извлечь данные оборудования.\n"
                    "Файл может быть защищен или иметь очень сложное форматирование."
                )
                return
            
            # Создаем Excel
            await status_message.edit_text("💾 Формирую Excel...")
            
            df = pd.DataFrame(equipment_data)
            df.to_excel(tmp_excel_path, index=False, engine='openpyxl')
            
            # Отправляем результат
            await status_message.edit_text("✅ Готово!")
            
            with open(tmp_excel_path, 'rb') as excel_file:
                await update.message.reply_document(
                    document=excel_file,
                    filename=f"Спецификация_{document.file_name.replace('.pdf', '.xlsx')}",
                    caption=f"📋 Извлечено {len(equipment_data)} позиций оборудования"
                )
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}")
            await update.message.reply_text("❌ Ошибка обработки файла. Попробуйте другой PDF.")
        
        finally:
            # Удаляем временные файлы
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
        logger.info("Бот запущен")
        print("🤖 Бот для обработки PDF с оборудованием запущен!")
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
    except:
        print("⚠️  Tesseract OCR не установлен. Установите:")
        print("Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("Linux: sudo apt install tesseract-ocr tesseract-ocr-rus")
        print("Mac: brew install tesseract tesseract-lang")
    
    bot = PDFEquipmentBot(BOT_TOKEN)
    bot.run()