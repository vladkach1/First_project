import re
import logging
from rapidfuzz import fuzz

# Настройка логирования
logger = logging.getLogger("TextAnalysis")

# Вес токена-кода модели vs обычного слова
MODEL_TOKEN_WEIGHT = 3.0
GENERIC_TOKEN_WEIGHT = 1.0


def _normalize(text):
    """Нормализация строки: нижний регистр, лишние пробелы"""
    return re.sub(r'\s+', ' ', text.lower()).strip()


def _is_model_token(token):
    """
    Определяет, является ли токен кодом модели / параметром.

    Коды моделей:
      - Содержат цифры + буквы:  "кввгнг", "ds-2cd2143g2-i", "4х1.5"
      - Содержат спецсимволы:    "кввгнг-ls", "rg-6/u", "0.75х2"
      - Чисто числовые параметры: "4х1.5", "305", "10.0"

    Общие слова:
      - Только буквы без цифр и спецсимволов: "кабель", "видеокамера", "силовой"
    """
    # Содержит цифру — это параметр или код
    if re.search(r'\d', token):
        return True
    # Содержит спецсимволы типичные для моделей
    if re.search(r'[-/\\.]', token):
        return True
    # Смесь латиницы и кириллицы — скорее всего код
    has_latin = bool(re.search(r'[a-z]', token))
    has_cyrillic = bool(re.search(r'[а-яё]', token))
    if has_latin and has_cyrillic:
        return True
    # Короткая аббревиатура из заглавных (до нормализации были заглавные)
    # После lower() не определить, но типичные коды: кввгнг, ввгнг, кпсэнг
    # — они содержат необычные сочетания согласных, но это ненадёжно.
    # Оставляем как generic.
    return False


def similarity(get_string, site_string):
    """
    Вычисляет схожесть строки запроса и строки результата.
    Код модели имеет в 3 раза больший вес, чем общее слово.

    Пример:
      Запрос:    "Кабель КВВГнг-LS 4х1.5"
      Результат: "КВВГнг-LS 4х1.5 Кабель силовой медный"

      Токены запроса:
        "кабель"    → generic (вес 1)
        "кввгнг-ls" → модель  (вес 3)
        "4х1.5"     → модель  (вес 3)

      Совпали "кввгнг-ls" и "4х1.5" = 6 из 7 весовых единиц → 0.86+
      Без весов было бы: 2 из 3 = 0.67

    :return: (score 0.0-1.0, разница_в_количестве_слов)
    """
    get_norm = _normalize(get_string)
    site_norm = _normalize(site_string)

    get_tokens = get_norm.split()
    site_tokens = site_norm.split()

    if not get_tokens:
        return (0.0, len(site_tokens))

    total_weight = 0.0
    matched_weight = 0.0

    for g_token in get_tokens:
        weight = MODEL_TOKEN_WEIGHT if _is_model_token(g_token) else GENERIC_TOKEN_WEIGHT
        total_weight += weight

        # Ищем лучшее совпадение среди токенов результата
        best_score = 0.0
        for s_token in site_tokens:
            score = fuzz.ratio(g_token, s_token) / 100.0
            if score > best_score:
                best_score = score

        matched_weight += weight * best_score

    score = matched_weight / total_weight if total_weight > 0 else 0.0
    extra_words = len(site_tokens) - len(get_tokens)

    return (score, extra_words)
    

def parse_equipment_spec(text):
    """
    Анализирует распознанный текст и извлекает спецификацию оборудования
    
    :param text: Текст для анализа
    :return: Список словарей с данными оборудования
    """
    try:
        logger.info("Начало анализа текста оборудования")
        
        # Улучшенный шаблон для извлечения табличных данных
        table_pattern = re.compile(
            r'(\d+)\s*\|?\s*([^\|]+?)\s*\|?\s*([^\|]+?)\s*\|?\s*([^\|]+?)\s*\|?\s*(\d+)\s*\|?\s*([\d\s,\.]+)\s*\|?\s*([\d\s,\.]+)',
            re.DOTALL
        )
        
        matches = table_pattern.findall(text)
        
        if not matches:
            logger.warning("Не найдено совпадений в тексте")
            return []
        
        equipment_list = []
        for match in matches:
            try:
                # Обработка и очистка данных
                item = {
                    'number': match[0].strip(),
                    'name': re.sub(r'\s+', ' ', match[1].strip()),
                    'designation': re.sub(r'\s+', ' ', match[2].strip()),
                    'unit': match[3].strip(),
                    'quantity': int(match[4].replace(' ', '')),
                    'price': float(match[5].replace(' ', '').replace(',', '.')),
                    'total': float(match[6].replace(' ', '').replace(',', '.'))
                }
                
                # Проверка целостности данных
                if not all(item.values()):
                    logger.warning(f"Пропущена неполная запись: {item}")
                    continue
                
                if item['price'] * item['quantity'] != item['total']:
                    logger.warning(f"Несоответствие суммы для {item['name']}")
                
                equipment_list.append(item)
                logger.debug(f"Добавлено оборудование: {item['name']}")
                
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка обработки строки: {match} - {e}")
                continue
        
        logger.info(f"Успешно извлечено {len(equipment_list)} позиций оборудования")
        logger.info(f"Успешно извлечено {equipment_list[0]} позиций оборудования")
        return equipment_list
    
    except Exception as e:
        logger.error(f"Ошибка анализа текста: {e}")
        raise RuntimeError("Ошибка анализа спецификации оборудования.")