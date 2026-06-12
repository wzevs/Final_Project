import os
import requests
from dotenv import load_dotenv
from models.product import Product
from utils.logger import logger

# ტვირთავს მონაცემებს .env ფაილიდან
load_dotenv()


class GitecClient:
    def __init__(self):
        self.base_url = "https://b2b.gitec.ge/restapi/products"

        # მონაცემები მოაქვს .env-დან, თუ იქ არ არის - იყენებს ცარიელ სტრინგს
        self.headers = {
            "username": os.getenv("GITEC_USERNAME", ""),
            "password": os.getenv("GITEC_PASSWORD", "")
        }

        # GITEC-ისთვის მორგებული საკვანძო სიტყვები
        self.category_map = {
            # 1. Cooling გადმოვიტანეთ წინ და დავამატეთ ქართული ტერმინი
            "Cooling": ["ქეისის ქულერი", "cooler", "fan", "heatsink", "ქულერი", "lga1700", "am4", "am5"],
            "Processors": ["cpu", "processor", "intel core", "amd ryzen", "პროცესორი"],
            "Video Cards": ["vga", "gpu", "geforce", "nvidia", "radeon", "rtx", "gtx", "rx ", "ვიდეო ბარათი"],
            "Motherboards": ["motherboard", "mb ", " h610", " b760", " z790", " a620", " b650", "დედა დაფა"],
            "Storage": ["ssd", "hdd", "nvme", "m.2", "sata", "internal drive", "მყარი დისკი"],
            "PSU": ["psu", "power supply", "კვების ბლოკი", " 500w", " 600w", " 750w", " 850w"],
            "RAM": ["ram ", "memory", "ddr4", "ddr5", "dimm", "ოპერატიული"],
            "Cases": ["case", "chassis", "tower", "ქეისი"]
        }

    def _identify_category(self, name: str) -> str:
        """აკლასიფიცირებს პროდუქტს დასახელების მიხედვით"""
        name_low = name.lower()
        for category, keywords in self.category_map.items():
            if any(kw in name_low for kw in keywords):
                return category
        return "Other"

    def fetch_products(self) -> list[Product]:
        logger.info("GITEC API-დან მონაცემების წამოღება დაიწყო...")
        try:
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params={"language": "ge"}
            )
            response.raise_for_status()
            data = response.json()

            products = []
            for item in data:
                name = item.get("Name", "")
                price_info = item.get("ProductPrice", {})
                price_value = price_info.get("PriceValue", 0)

                custom_props = item.get("CustomProperties", {})
                sku = (
                    item.get("Sku")
                    or item.get("SKU")
                    or item.get("Code")
                    or item.get("Article")
                    or custom_props.get("Sku")
                    or custom_props.get("SKU")
                    or custom_props.get("Code")
                    or custom_props.get("Article")
                    or ""
                )
                sku = str(sku).strip() if sku else ""
                qty_raw = (
                        custom_props.get("Available Quantity") or
                        custom_props.get("Avaliable Quantity") or
                        "0"
                )

                try:
                    quantity = int(float(str(qty_raw).replace(',', '.')))
                except (ValueError, TypeError):
                    quantity = 0

                category = self._identify_category(name)

                if category != "Other":
                    p = Product(
                        brand="GITEC",
                        name=name,
                        quantity=quantity,
                        price=float(price_value) if price_value else 0.0,
                        rrp_price=0.0,
                        category=category,
                        sku=sku,
                    )
                    products.append(p)

            logger.info(f"GITEC API: წარმატებით დამუშავდა {len(products)} კომპონენტი.")
            return products

        except Exception as e:
            logger.error(f"GITEC API შეცდომა: {e}")
            return []