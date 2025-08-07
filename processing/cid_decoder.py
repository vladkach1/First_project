import re
from pdfminer.cmapdb import CMapDB
from pdfminer.cmapdb import CMap

def decode_cid_text(text: str) -> str:
    """Декодирование текста с CID-символами в читаемый текст"""
    # Регулярное выражение для поиска CID-последовательностей
    cid_pattern = r'\(cid\:(\d+)\)'
    decoded_text = text
    
    # Создаем кэш для CMAP
    CMapDB()
    
    def replace_cid(match):
        cid = int(match.group(1))
        try:
            # Пробуем декодировать через Unicode
            char = CMap.to_unichr(cid)
            return char if char != '\ufffd' else f'[CID:{cid}]'
        except:
            return f'[CID:{cid}]'
    
    # Заменяем все CID-последовательности
    decoded_text = re.sub(cid_pattern, replace_cid, decoded_text)
    
    return decoded_text