import unittest
from unittest.mock import patch
from scraping.price_scraper import find_equipment_price, scrape_site, clean_price

class TestPriceScraping(unittest.TestCase):
    
    @patch("scraping.price_scraper.requests.get")
    def test_price_scraping(self, mock_get):
        # Мокирование ответа сервера
        mock_response = MagicMock()
        mock_response.text = '<div class="product-card-price__current">1 234,56 ₽</div>'
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Вызов тестируемой функции
        result = find_equipment_price("Датчик дыма")
        
        # Проверки
        self.assertEqual(result["price"], "1 234,56 ₽")
        self.assertEqual(result["source"], "ETM")
        
    def test_price_cleaning(self):
        test_cases = [
            ("Цена: 1 234,56 ₽", 1234.56),
            ("99.99 USD", 99.99),
            ("1,000.50", 1000.5),
            ("Нет цены", None),
            ("Стоимость: 75 рублей", 75.0)
        ]
        
        for input_val, expected in test_cases:
            with self.subTest(input=input_val):
                result = clean_price(input_val)
                self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()