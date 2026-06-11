import re
import unicodedata

ALLOWED_LINES = 2
SIGNATURE_HTML = "<i>©oxxxymiron</i>"


def sanitize_punch(text: str) -> str:
    """Приводит панч к аккуратному виду и добавляет подпись."""
    if not text:
        return text

    s = unicodedata.normalize("NFC", text)
    s = s.replace("\r", "\n").strip().strip(" \n\"'`“”„«»")

    # нормализация © и частых артефактов
    s = (
        s.replace("¬", "©")
         .replace("(c)", "©")
         .replace("(C)", "©")
         .replace("&copy;", "©")
    )

    # убрать префиксы типа "Oxxxymiron:" и т.п.
    s = re.sub(r"^\s*(?:Oxxxymiron|Оксимирон|Oxxxy)\s*:?\s*", "", s, flags=re.I)

    # разбивка и чистка строк
    raw_lines = s.split("\n")
    lines = []
    for ln in raw_lines:
        ln_clean = re.sub(r"[ \t\u00A0]+$", "", ln).strip().strip(" \n\"'`“”„«»")
        if not ln_clean:
            continue
        
        # Проверяем, не является ли строка подписью
        ln_lower = ln_clean.lower()
        is_sig = False
        for sig_word in ["oxx", "окси", "мирон янович", "©", "copyright"]:
            if sig_word in ln_lower:
                # Если строка короткая (до 35 символов), то это подпись
                if len(ln_clean) < 35:
                    is_sig = True
                    break
        if is_sig:
            continue
            
        lines.append(ln_clean)

    # дедуп с сохранением порядка
    seen, deduped = set(), []
    for ln in lines:
        key = ln.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ln)
    lines = deduped

    # ограничение 1–3 строки
    if not lines:
        lines = ["..."]
    lines = lines[:ALLOWED_LINES]

    body = "\n".join(lines)
    return body.rstrip() + f"\n\n{SIGNATURE_HTML}"


def strip_signature(text: str) -> str:
    """Удаляет финальную подпись ©oxxxymiron (если есть), чтобы не подсказывать в игре."""
    if not text:
        return text or ""
    s = unicodedata.normalize("NFC", text).replace("\r", "\n")
    s = re.sub(
        r"(?:\n|<br\s*/?>)+\s*(?:<i>)?\s*[©cC]?\s*(?:oxx?x?ymiron|мирон янович)\s*(?:</i>)?\s*$",
        "",
        s,
        flags=re.I,
    )
    return s.strip()