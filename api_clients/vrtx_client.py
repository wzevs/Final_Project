import html
import os
import re

import requests
from dotenv import load_dotenv

from models.product import Product
from utils.logger import logger
from utils.sku_utils import extract_vrtx_sku_from_name

load_dotenv()

DEFAULT_API_URL = (
    "https://vrtx.ge/index.php?route=api/app/items&token={token}"
)

# API category_name → ჩვენი კატეგორია
CATEGORY_MAP = {
    "cpu": "პროცესორები",
    "პროცესორები": "პროცესორები",
    "motherboard": "დედა დაფები",
    "დედა დაფები": "დედა დაფები",
    "cooler": "ქულერები",
    "ქულერები": "ქულერები",
    "case": "ქეისები",
    "ქეისები": "ქეისები",
    "power supply": "კვების ბლოკები",
    "კვების ბლოკები": "კვების ბლოკები",
    "monitor": "მონიტორები",
    "მონიტორები": "მონიტორები",
    "mouse": "მაუსები",
    "მაუსები": "მაუსები",
    "keyboard": "კლავიატურები",
    "კლავიატურები": "კლავიატურები",
    "headphone": "ყურსასმენები",
    "ყურსასმენები": "ყურსასმენები",
    "video card": "ვიდეო ბარათები",
    "vga": "ვიდეო ბარათები",
    "ssd": "მყარი დისკები",
    "hdd": "მყარი დისკები",
    "hard disk": "მყარი დისკები",
    "მყარი დისკები": "მყარი დისკები",
    "ram": "ოპერატიული",
    "memory": "ოპერატიული",
    "ოპერატიული": "ოპერატიული",
    "thermopasta": "თერმოპასტა",
    "თერმოპასტა": "თერმოპასტა",
    "gaming chair": "სკამები/მაგიდები",
    "გეიმერული სავარძელები": "სკამები/მაგიდები",
    "notebook": "ლეპტოპები",
    "ნოუთბუქები": "ლეპტოპები",
    "mini pc": "დესკტოპები",
}


class VrtxClient:
    """Vertex (vrtx.ge) B2B API — საქონლის სია token-ით."""

    def __init__(self):
        token = os.getenv("VRTX_API_TOKEN", "").strip()
        self.api_url = os.getenv("VRTX_API_URL", "").strip()
        if not self.api_url and token:
            self.api_url = DEFAULT_API_URL.format(token=token)
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ka,ge;q=0.9,en;q=0.8",
        }

    def _ensure_configured(self):
        if not self.api_url:
            raise ValueError("VRTX_API_TOKEN ან VRTX_API_URL საჭიროა .env-ში.")

    @staticmethod
    def _normalize_category(raw: str) -> str:
        text = html.unescape(str(raw or "")).strip().lower()
        for key, formal in CATEGORY_MAP.items():
            if key in text:
                return formal
        return ""

    @staticmethod
    def _parse_price(value) -> float:
        try:
            return float(str(value).replace(",", ".").strip() or 0)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_qty(value) -> int:
        if value is None:
            return 0
        text = str(value).strip()
        if not text:
            return 0
        if text.endswith("+") or text.startswith(">="):
            digits = re.sub(r"\D", "", text)
            return int(digits) if digits else 10
        try:
            return max(0, int(float(text.replace(",", "."))))
        except (ValueError, TypeError):
            digits = re.sub(r"\D", "", text)
            return int(digits) if digits else 0

    def fetch_items_raw(self) -> list[dict]:
        self._ensure_configured()
        logger.info("VRTX API-დან მონაცემების წამოღება...")
        response = requests.get(self.api_url, headers=self.headers, timeout=120)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("products") or []
        else:
            items = []

        by_pid: dict[str, dict] = {}
        for item in items:
            pid = str(item.get("product_id") or item.get("id") or "").strip()
            if pid and pid not in by_pid:
                by_pid[pid] = item

        logger.info(f"VRTX API: მიღებულია {len(by_pid)} უნიკალური პროდუქტი.")
        return list(by_pid.values())

    def _item_to_product(self, item: dict) -> Product | None:
        name = str(item.get("name") or "").strip()
        if not name:
            return None

        category_raw = str(item.get("category_name") or "").strip()
        category = self._normalize_category(category_raw)
        if not category:
            category = html.unescape(category_raw) or "სხვა"

        price = self._parse_price(item.get("price"))
        special = self._parse_price(item.get("special_price"))
        if special > 0:
            price = special
        if price <= 0:
            return None

        rrp = self._parse_price(item.get("rrp"))
        if rrp <= 0:
            rrp = round(price * 1.10, 2)

        sku = extract_vrtx_sku_from_name(name)
        brand = str(item.get("manufacturer") or "Unknown").strip()
        vrtx_code = str(item.get("vrtx_code") or "").strip()

        return Product(
            brand=brand,
            name=name,
            quantity=self._parse_qty(item.get("quantity")),
            price=price,
            rrp_price=rrp,
            category=category,
            sku=sku,
            distributor_code=vrtx_code,
        )

    def fetch_products(self) -> list[Product]:
        products = []
        for item in self.fetch_items_raw():
            product = self._item_to_product(item)
            if product:
                products.append(product)
        logger.info(f"VRTX API: დამუშავდა {len(products)} პროდუქტი.")
        return products

    def test_connection(self) -> dict:
        items = self.fetch_items_raw()
        return {"ok": True, "total": len(items), "sample": items[0] if items else None}
