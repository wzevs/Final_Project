import re

import pandas as pd

STORERA_CODE_COLUMN = "შიდა კოდი"
STORERA_ALT_CODE_COLUMN = "1C / FINA / FMG"

_DESC_PATTERNS = [
    # მაგ: 90LM0AE1-B01E70/ 164318 → 90LM0AE1-B01E70
    re.compile(r"\b(90LM[A-Z0-9]+-[A-Z0-9]+)\s*/\s*\d+", re.I),
    re.compile(r"Model/PN\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)", re.I),
    re.compile(r"მოდელი/კოდი\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)", re.I),
    re.compile(r"(?<![A-Za-z])Model\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)", re.I),
    re.compile(r"SKU\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)", re.I),
    re.compile(r"(?<![A-Za-z])PN\s*[:：]\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)", re.I),
    re.compile(
        r"Part\s*(?:Number|No|#)?\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\-\./_]+)",
        re.I,
    ),
]

_NAME_PARENS_PATTERN = re.compile(r"\(([A-Z0-9][A-Z0-9\-\./_]{4,})\)", re.I)
_NAME_EMBEDDED_PATTERN = re.compile(
    r"\b([A-Z]{2,}\d{2,}[A-Z0-9]*(?:-[A-Z0-9][A-Za-z0-9\-\./_]*)+)\b"
)
_DELL_STYLE_PATTERN = re.compile(r"\b(\d{3}-[A-Z]{3,}[A-Z0-9\-]*)\b", re.I)


def is_empty_code(value) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip().lower()
    if text in ("", "nan", "none"):
        return True
    # Excel ცარიელ 1C ველს ხშირად 0.0-ად აბრუნებს
    if text in ("0", "0.0"):
        return True
    if isinstance(value, (int, float)) and float(value) == 0:
        return True
    return False


def normalize_sku(value) -> str:
    """SKU შედარებისთვის: uppercase, /-მდე, პუნქტუაციის გარეშე."""
    if is_empty_code(value):
        return ""
    cleaned = _clean_token(str(value))
    return re.sub(r"[^A-Z0-9]", "", cleaned.upper())


def normalize_distributor_code(value) -> str:
    """მომწოდებლის შიდა კოდი (VRTX vrtx_code და ა.შ.) — რიცხვებზე წინა ნულების გარეშე."""
    if is_empty_code(value):
        return ""
    # Excel ხშირად აბრუნებს 14086.0 — არ გავხდათ 140860
    if isinstance(value, (int, float)):
        try:
            num = float(value)
            if num == int(num):
                return str(int(num)).lstrip("0") or "0"
        except (TypeError, ValueError):
            pass
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        return str(int(float(text))).lstrip("0") or "0"
    cleaned = re.sub(r"[^A-Z0-9]", "", text.upper())
    if cleaned.isdigit():
        return cleaned.lstrip("0") or "0"
    return cleaned


def _clean_token(token: str) -> str:
    # მაგ: 90LM0AE1-B01E70/164318 → მხოლოდ /-მდე ნაწილი
    return token.strip().split("/")[0].strip().rstrip(".,;")


def is_plausible_sku(token: str) -> bool:
    """ფილტრავს გენერიკულ სიტყვებს (მაგ. Nitro) და არასწორ ტოკენებს (AC100-240V)."""
    sku = _clean_token(token)
    if len(sku) < 5:
        return False
    if re.match(r"^AC\d+-\d+V$", sku, re.I):
        return False
    if sku.isalpha() and len(sku) < 8:
        return False
    if re.match(r"^90LM[A-Z0-9]+-[A-Z0-9]+$", sku, re.I):
        return True
    if re.match(r"^RZ\d{2}-", sku, re.I):
        return True
    if re.match(r"^\d{3}-[A-Z]", sku, re.I):
        return True
    if re.match(r"^[A-Z]{2,}\d", sku, re.I) and "-" in sku:
        return True
    if any(char.isdigit() for char in sku) and len(sku) >= 6:
        return True
    if len(sku) >= 10 and re.search(r"[A-Za-z]", sku) and re.search(r"\d", sku):
        return True
    return False


_VRTX_SOCKET_BLACKLIST = {
    "LGA1155", "LGA1150", "LGA1151", "LGA1200", "LGA1700", "LGA1851",
    "AM4", "AM5", "AM3", "FM2", "TR4", "STRX4", "SWRX8",
}


def extract_vrtx_sku_from_name(name: str) -> str:
    """Vertex: SKU სახელიდან (უნიკ. კოდი/ID იგნორირდება)."""
    text = str(name).strip()
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    if " - " in text:
        tail = text.split(" - ")[-1].strip().strip('"')
        if (
            tail.upper() not in _VRTX_SOCKET_BLACKLIST
            and re.match(r"^[A-Z0-9][A-Z0-9\-\./_]+$", tail, re.I)
            and len(tail) >= 4
        ):
            return tail
    for word in text.replace('"', " ").split():
        token = word.strip(",;")
        if len(token) < 4:
            continue
        if not re.search(r"\d", token) or not re.search(r"[A-Za-z]", token):
            continue
        if re.fullmatch(r"\d+(mm|cm|w|gb|tb|mhz|ghz)", token, re.I):
            continue
        upper = token.upper()
        if upper.startswith(("LGA", "AM", "DDR", "PCI", "USB", "802")):
            continue
        if re.match(r"^[A-Z0-9][A-Z0-9\-\./_]+$", token, re.I):
            return token
    return ""


def extract_sku_from_text(name: str, description: str) -> str | None:
    """SKU აღწერიდან ან სახელიდან. პრიორიტეტი: აღწერა → სახელი."""
    desc_text = str(description or "")
    for pattern in _DESC_PATTERNS:
        match = pattern.search(desc_text)
        if match:
            candidate = _clean_token(match.group(1))
            if is_plausible_sku(candidate):
                return candidate

    name_text = str(name or "")

    match = _NAME_PARENS_PATTERN.search(name_text)
    if match:
        candidate = _clean_token(match.group(1))
        if is_plausible_sku(candidate):
            return candidate

    for pattern in (_NAME_EMBEDDED_PATTERN, _DELL_STYLE_PATTERN):
        match = pattern.search(name_text)
        if match:
            candidate = _clean_token(match.group(1))
            if is_plausible_sku(candidate):
                return candidate

    return None
