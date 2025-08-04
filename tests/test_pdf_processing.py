import unittest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from processing.pdf_processor import process_pdf
from config import BASE_DIR

class TestPdfProcessing(unittest.TestCase):
    
    def setUp(self):
        self.sample_pdf = BASE_DIR / "tests" / "samples" / "sample_spec.pdf"
        self.output_path = BASE_DIR / "tests" / "output" / "report.xlsx"
        self.output_path.parent.mkdir(exist_ok=True, parents=True)
        
    @patch("processing.pdf_processor.extract_text_with_ocr")
    @patch("processing.pdf_processor.logger")
    def test_pdf_processing(self, mock_logger, mock_ocr):
        # Подготовка тестовых данных
        mock_ocr.return_value = "Тестовый текст OCR"
        
        # Вызов тестируемой функции
        process_pdf(self.sample_pdf, self.output_path, 123)
        
        # Проверки
        self.assertTrue(self.output_path.exists())
        mock_logger.info.assert_called_with(f"Отчет сгенерирован: {self.output_path}")
        
    def test_invalid_pdf(self):
        invalid_pdf = BASE_DIR / "tests" / "samples" / "invalid.pdf"
        with self.assertRaises(Exception):
            process_pdf(invalid_pdf, self.output_path, 123)

if __name__ == '__main__':
    unittest.main()