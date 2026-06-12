import os
import re
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

from models.product import Product
from utils.logger import logger

load_dotenv()

SOAP_NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "ext": "http://extra.alta.com.ge",
}


class AltaClient:
    """Alta B2B SOAP API — http://extra.alta.com.ge/b2b/b2bEWS

    დოკუმენტაცია: GetPriceList(user, password, item?)
    - user / password: ALTA_USERNAME / ALTA_PASSWORD
    - item: ცარიელი = სრული ფასლისტი; კონკრეტული კოდი = ერთი პროდუქტი
    - პირველ მიმართვაზე ფიქსირდება IP (საჭიროა საქართველოს IP, VPN გამორთული)
  SKU: item_model (მოდელი), არა item (შიდა კოდი)
    """

    def __init__(self):
        self.service_url = os.getenv(
            "ALTA_SOAP_URL", "http://extra.alta.com.ge/b2b/b2bEWS"
        ).strip()
        self.username = os.getenv("ALTA_USERNAME", "").strip()
        self.password = os.getenv("ALTA_PASSWORD", "").strip()

        self.category_map = {
            "Cooling": ["ქულერი", "cooler", "fan", "heatsink", "lga1700", "am4", "am5"],
            "Processors": ["cpu", "processor", "intel core", "amd ryzen", "პროცესორი", "xeon"],
            "Video Cards": ["vga", "gpu", "geforce", "nvidia", "radeon", "rtx", "gtx", " rx", "ვიდეო"],
            "Motherboards": ["motherboard", "დედა დაფა", " h610", " b760", " z790", " a620", " b650"],
            "Storage": ["ssd", "hdd", "nvme", "m.2", "sata", "მყარი დისკი"],
            "PSU": ["psu", "power supply", "კვების ბლოკი", " 500w", " 600w", " 750w", " 850w"],
            "RAM": ["ram", "memory", "ddr3", "ddr4", "ddr5", "dimm", "ოპერატიული"],
            "Cases": ["case", "chassis", "tower", "ქეისი", "rack server"],
            "მონიტორები": ["monitor", "მონიტორი"],
            "ლეპტოპები": ["notebook", "laptop", "ლეპტოპ", "ნოუთბუქ"],
            "კლავიატურები": ["keyboard", "კლავიატურა"],
            "მაუსები": ["mouse", "მაუსი"],
            "ყურსასმენები": ["headset", "headphone", "speaker", "ყურსასმენ"],
            "პრინტერები": ["printer", "პრინტერი", "multifunction"],
        }

    def _ensure_credentials(self):
        if not self.username or not self.password:
            raise ValueError(
                "Alta SOAP API: დაამატეთ ALTA_USERNAME და ALTA_PASSWORD .env-ში."
            )

    def _build_envelope(self, item: str = "") -> str:
        self._ensure_credentials()
        item_xml = item.strip()
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ext="http://extra.alta.com.ge">
  <soapenv:Header/>
  <soapenv:Body>
    <ext:GetPriceList>
      <user>{self._xml_escape(self.username)}</user>
      <password>{self._xml_escape(self.password)}</password>
      <item>{self._xml_escape(item_xml)}</item>
    </ext:GetPriceList>
  </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def _xml_escape(value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _call_get_price_list(self, item: str = "") -> ET.Element:
        body = self._build_envelope(item)
        response = requests.post(
            self.service_url,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "",
            },
            timeout=180,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        fault = root.find(".//soap:Fault", SOAP_NS)
        if fault is not None:
            fault_str = fault.findtext("faultstring") or ET.tostring(fault, encoding="unicode")
            raise RuntimeError(f"Alta SOAP Fault: {fault_str}")

        price_list = root.find(".//ext:PriceList", SOAP_NS)
        if price_list is None:
            raise RuntimeError("Alta SOAP: PriceList ველი პასუხში ვერ მოიძებნა")

        error_id = price_list.attrib.get("error_id", "0")
        error_desc = price_list.attrib.get("error_desc", "")
        if error_id not in ("0", "0.0", ""):
            if error_id == "1" or "ip" in error_desc.lower():
                raise RuntimeError(
                    f"Alta API: {error_desc} — IP მისამართი არ ემთხვევა დაფიქსირებულს. "
                    "VPN გამორთეთ და Alta-ს მიწერეთ IP-ის გადაყენებისთვის (წინა მიმართვა WARP/თურქეთიდან შეიძლება დაფიქსირდა)."
                )
            raise RuntimeError(f"Alta API შეცდომა: {error_desc} (error_id={error_id})")

        return price_list

    @staticmethod
    def _parse_price(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", ".")
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_qty(value) -> int:
        if value is None:
            return 0
        text = str(value).strip()
        if not text or text == "0":
            return 0
        if text.startswith(">="):
            digits = re.sub(r"\D", "", text)
            return int(digits) if digits else 10
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else 0

    def _identify_category(self, name: str, category: str = "") -> str:
        blob = f"{name} {category}".lower()
        for formal, keywords in self.category_map.items():
            if any(kw in blob for kw in keywords):
                return formal
        return category.strip() if category else "Other"

    @staticmethod
    def _extract_price_list_items(price_list: ET.Element) -> list[dict]:
        """Alta პასუხში <item> ხშირად namespace-ის გარეშეა <items> კონტეინერში."""
        nodes = price_list.findall("ext:items/ext:item", SOAP_NS)
        if not nodes:
            nodes = price_list.findall(".//item")
        return [dict(node.attrib) for node in nodes if node.attrib]

    def fetch_price_list_raw(self, item: str = "") -> list[dict]:
        """SOAP GetPriceList — აბრუნებს ყველა item ჩანაწერს dict-ებად."""
        logger.info("Alta SOAP: GetPriceList მოთხოვნა...")
        price_list = self._call_get_price_list(item)
        rows = self._extract_price_list_items(price_list)
        logger.info(f"Alta SOAP: მიღებულია {len(rows)} ჩანაწერი.")
        return rows

    def _row_to_product(self, row: dict) -> Product | None:
        name = (row.get("item_full_name") or "").strip()
        if not name:
            return None

        price = self._parse_price(row.get("price_unit"))
        if price <= 0:
            return None

        qty = self._parse_qty(row.get("qty_text"))
        brand = str(row.get("brand") or "Alta").strip()
        category_raw = str(row.get("category") or "").strip()
        category = self._identify_category(name, category_raw)

        sku = str(row.get("item_model") or row.get("item") or "").strip()

        return Product(
            brand=brand,
            name=name,
            quantity=qty,
            price=price,
            rrp_price=round(price * 1.10, 2),
            category=category,
            sku=sku,
        )

    def fetch_products(self, pc_only: bool = True) -> list[Product]:
        logger.info("Alta SOAP API-დან მონაცემების წამოღება დაიწყო...")
        rows = self.fetch_price_list_raw()
        products: list[Product] = []
        for row in rows:
            product = self._row_to_product(row)
            if not product:
                continue
            if pc_only and product.category == "Other":
                continue
            products.append(product)

        logger.info(f"Alta SOAP: დამუშავდა {len(products)} პროდუქტი.")
        return products

    def test_connection(self) -> dict:
        """ერთი ჩანაწერით შემოწმება — ცარიელი სია არის ნორმალური IP-ის დაფიქსირებისას."""
        rows = self.fetch_price_list_raw()
        return {"ok": True, "items_received": len(rows), "sample": rows[0] if rows else None}
