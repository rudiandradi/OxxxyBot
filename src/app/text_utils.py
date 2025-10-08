# text_utils.py
import re, unicodedata

ALLOWED_LINES = 3
SIGNATURE_HTML = "<i>©oxxxymiron</i>"

def sanitize_punch(text: str) -> str:
    if not text:
        return text

    s = unicodedata.normalize("NFC", text)
    s = s.replace("\r", "\n").strip().strip(' \n"\'`“”„«»')

    # нормализация символов © и префиксов
    s = s.replace("¬", "©").replace("(c)", "©").replace("(C)", "©")
    s = re.sub(r"^\s*(?:Oxxxymiron|Оксимирон)\s*:?\s*", "", s, flags=re.I)

    # убираем двойные пустые строки и пробельные «хвосты»
    lines = [re.sub(r"[ \t\u00A0]+$", "", ln).strip() for ln in s.split("\n")]
    lines = [ln for ln in lines if ln]  # только непустые

    # если модель выдала много «строф» — берём самые первые смысловые 1–3 строки
    # (часто первые строки — самые цельные)
    lines = lines[:ALLOWED_LINES] or ["..."]

    # дедуп строк (без сохранения повторов типа «Заводной апельсин…»)
    seen, deduped = set(), []
    for ln in lines:
        key = ln.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ln)
    lines = deduped

    body = "\n\n".join(lines)

    # убрать любую собственную подпись, если проскочила
    body = re.sub(r"\n+\s*(?:<i>)?\s*[©cC]\s*oxx?x?ymiron\s*(?:</i>)?\s*$", "", body, flags=re.I)

    # финально — правильная подпись
    return body.rstrip() + f"\n\n{SIGNATURE_HTML}"