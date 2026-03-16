import requests
import json
import re
from models.product import Product
from utils.logger import logger


class GitecClient:
    def __init__(self, username, password):
        self.base_url = "https://b2b.gitec.ge/restapi/products"
        self.headers = {
            "username": "sales@geekspot.ge",
            "password": "qazaq123"
        }
        # GITEC-ისთვის მორგებული საკვანძო სიტყვები
        self.category_map = {
            "Processors": ["cpu", "processor", "intel core", "amd ryzen", "i3-", "i5-", "i7-", "i9-", "პროცესორი"],
            "Video Cards": ["vga", "gpu", "geforce", "nvidia", "radeon", "rtx", "gtx", "rx ", "ვიდეო ბარათი"],
            "Motherboards": ["motherboard", "mb ", " h610", " b760", " z790", " a620", " b650", "დედა დაფა"],
            "Storage": ["ssd", "hdd", "nvme", "m.2", "sata", "internal drive", "მყარი დისკი"],
            "PSU": ["psu", "power supply", "კვების ბლოკი", " 500w", " 600w", " 750w", " 850w"],
            "RAM": ["ram ", "memory", "ddr4", "ddr5", "dimm", "ოპერატიული"],
            "Cases": ["case", "chassis", "tower", "ქეისი"],
            "Cooling": ["cooler", "fan", "heatsink", "ქულერი", "lga1700", "am4", "am5"]
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
            # ენის პარამეტრი ქართული ინფორმაციისთვის
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

                # 1. ფასის ამოღება (PriceValue ყველაზე ზუსტია)
                price_info = item.get("ProductPrice", {})
                price_value = price_info.get("PriceValue", 0)

                # 2. რაოდენობის ამოღება CustomProperties-დან
                custom_props = item.get("CustomProperties", {})

                # ვამოწმებთ ორივე შესაძლო სპელინგს (ll და l)
                qty_raw = (
                        custom_props.get("Available Quantity") or
                        custom_props.get("Avaliable Quantity") or
                        "0"
                )

                # სტრინგის ("6") გარდაქმნა რიცხვად (int)
                try:
                    # ჯერ float-ად, რადგან შეიძლება ეწეროს "6.0"
                    quantity = int(float(str(qty_raw).replace(',', '.')))
                except (ValueError, TypeError):
                    quantity = 0

                # 3. კატეგორიზაცია
                category = self._identify_category(name)

                # ვამატებთ მხოლოდ იმ პროდუქტებს, რომლებიც ჩვენს კატეგორიებში მოხვდა
                if category != "Other":
                    p = Product(
                        brand="GITEC",
                        name=name,
                        quantity=quantity,
                        price=float(price_value) if price_value else 0.0,
                        rrp_price=0.0,
                        category=category
                    )
                    products.append(p)

            logger.info(f"GITEC API: წარმატებით დამუშავდა {len(products)} კომპონენტი.")
            return products

        except Exception as e:
            logger.error(f"GITEC API შეცდომა: {e}")
            return []