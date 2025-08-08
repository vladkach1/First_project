import re
from pdfminer.cmapdb import CMapDB, CMap

def decode_cid_text(text: str) -> str:
    """Улучшенное декодирование CID-символов"""
    if not text:
        return text
        
    # Инициализация CMAP
    CMapDB()
    
    # Регулярное выражение для поиска CID
    cid_pattern = r'\(cid\:(\d+)\)'
    
    def decode_match(match):
        cid = int(match.group(1))
        try:
            char = CMap.to_unichr(cid)
            return char if char != '\ufffd' else f'[CID:{cid}]'
        except Exception:
            return f'[CID:{cid}]'
    
    return re.sub(cid_pattern, decode_match, text)