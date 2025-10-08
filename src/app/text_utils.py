import re
import unicodedata

ALLOWED_LINES = 3
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
    lines = [re.sub(r"[ \t\u00A0]+$", "", ln).strip() for ln in s.split("\n")]
    lines = [ln for ln in lines if ln]  # только непустые

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

    body = "\n\n".join(lines)

    # убрать уже проскочившие подписи любых видов
    body = re.sub(
        r"\n+\s*(?:<i>)?\s*[©cC]\s*oxx?x?ymiron\s*(?:</i>)?\s*$",
        "",
        body,
        flags=re.I,
    )

    # добавить правильную подпись
    return body.rstrip() + f"\n\n{SIGNATURE_HTML}"