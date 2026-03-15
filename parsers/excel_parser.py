import json
import pandas as pd
import re
from models.product import Product
from utils.logger import logger


class ExcelParser:
    def __init__(self, file_path: str, distributor_name: str):
        self.file_path = file_path
        self.config = self._load_config(distributor_name)

    def _load_config(self, name):
        try:
            with open("config/distributors.json", "r", encoding="utf-8") as f:
                configs = json.load(f)
                return configs.get(name)
        except Exception as e:
            logger.error(f"კონფიგურაციის ფაილი ვერ მოიძებნა: {e}")
            return None

    def _identify_category(self, row):
        """ადგენს კატეგორიას ფილტრის ან საკვანძო სიტყვების მიხედვით"""
        if not self.config: return None

        # ვიღებთ მნიშვნელობებს კონფიგურაციაში მითითებული სვეტებიდან
        cat_col = self.config.get("category_col")
        sub_cat_col = self.config.get("sub_category_col")

        cat_raw = str(row.get(cat_col, "")).strip() if cat_col in row else ""
        sub_cat_raw = str(row.get(sub_cat_col, "")).strip() if sub_cat_col in row else ""

        # 1. ERC-ის შემთხვევა: თუ გვაქვს მთავარი ფილტრი (მაგ: PC Components)
        if self.config.get("main_category_filter"):
            if cat_raw == self.config["main_category_filter"]:
                return sub_cat_raw
            return None

        # 2. Oasis-ის შემთხვევა: Keywords ძებნა (ვეძებთ ორივე სვეტში)
        combined_text = (cat_raw + " " + sub_cat_raw).lower()
        if "keywords" in self.config:
            for formal_cat, kws in self.config["keywords"].items():
                if any(kw.lower() in combined_text for kw in kws):
                    return formal_cat
        return None

    def _clean_price(self, value):
        if pd.isna(value) or str(value).strip() == "": return 0.0
        # ვტოვებთ მხოლოდ ციფრებს და წერტილს
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == '.')
        try:
            return float(cleaned)
        except:
            return 0.0

    def parse(self) -> list[Product]:
        if not self.config:
            return []

        try:
            df = pd.read_excel(self.file_path, engine="openpyxl")
            # სვეტების სახელების გასუფთავება (Space-ების მოცილება)
            df.columns = [str(col).strip() for col in df.columns]

            products = []
            for index, row in df.iterrows():
                category = self._identify_category(row)
                if not category:
                    continue

                # --- ფასის ამოღება ---
                price = 0.0
                for col in self.config.get("price_cols", []):
                    if col in row:
                        val = row.get(col)
                        price = self._clean_price(val)
                        if price > 0: break

                if price <= 0: continue

                # --- RRP ლოგიკა ---
                rrp = 0.0
                for col in self.config.get("rrp_cols", []):
                    if col in row:
                        val = row.get(col)
                        rrp = self._clean_price(val)
                        if rrp > 0: break

                if rrp <= 0:
                    rrp = round(price * 1.10, 2)

                # --- რაოდენობის ლოგიკა (Oasis-ის გათვალისწინებით) ---
                q_col = self.config.get("quantity_col")
                if q_col and q_col in row:
                    raw_q = str(row.get(q_col, "0"))
                    cleaned_q = re.sub(r'\D', '', raw_q)
                    quantity = int(cleaned_q) if cleaned_q else 0
                else:
                    # თუ რაოდენობის სვეტი არ არსებობს (Oasis), მივანიჭოთ 1
                    quantity = 1

                products.append(Product(
                    brand=str(row.get(self.config["brand_col"], "Unknown")).strip(),
                    name=str(row.get(self.config["name_col"], "No Name")).strip(),
                    quantity=quantity,
                    price=price,
                    rrp_price=rrp,
                    category=category
                ))

            logger.info(f"წარმატებით დაპარსულია {len(products)} პროდუქტი.")
            return products

        except Exception as e:
            logger.error(f"შეცდომა პარსინგისას: {e}")
            return []