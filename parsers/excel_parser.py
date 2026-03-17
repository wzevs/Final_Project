import json
import pandas as pd
import re
import os
from models.product import Product
from utils.logger import logger


class ExcelParser:
    def __init__(self, file_path: str, distributor_name: str):
        self.file_path = file_path
        self.distributor_name = distributor_name
        self.config = self._load_config(distributor_name)

    def _load_config(self, name):
        try:
            # ვიყენებთ აბსოლუტურ გზას ან ვამოწმებთ არსებობას
            config_path = "config/distributors.json"
            if not os.path.exists(config_path):
                logger.error(f"კონფიგურაციის ფაილი არ არსებობს გზაზე: {config_path}")
                return None

            with open(config_path, "r", encoding="utf-8") as f:
                configs = json.load(f)
                return configs.get(name)
        except Exception as e:
            logger.error(f"კონფიგურაციის ჩატვირთვის შეცდომა: {e}")
            return None

    def _identify_category(self, row):
        """ადგენს კატეგორიას კონფიგურაციაში არსებული Mapping-ის ან Keywords-ის მიხედვით"""
        if not self.config:
            return None

        cat_col = self.config.get("category_col")
        sub_cat_col = self.config.get("sub_category_col")
        name_col = self.config.get("name_col")

        cat_raw = str(row.get(cat_col, "")).strip() if cat_col in row else ""
        sub_cat_raw = str(row.get(sub_cat_col, "")).strip() if sub_cat_col in row else ""
        name_raw = str(row.get(name_col, "")).strip() if name_col in row else ""

        sub_cat_low = sub_cat_raw.lower()
        combined_text = (cat_raw + " " + sub_cat_raw).lower()

        # 1. ERC-ის შემთხვევა: მთავარი ფილტრი + Sub-category Mapping
        if self.config.get("main_category_filter"):
            if cat_raw == self.config["main_category_filter"]:
                sub_cat_map = self.config.get("sub_category_keywords")
                if sub_cat_map:
                    for formal_cat, kws in sub_cat_map.items():
                        if any(kw.lower() in sub_cat_low for kw in kws):
                            return formal_cat
                # თუ Mapping-ში არ არის, ვაბრუნებთ გასუფთავებულ ორიგინალს
                return sub_cat_raw if sub_cat_raw else "Other"
            return None

        # 2. Oasis, VRTX და სხვა: Keywords ძებნა კატეგორიებსა და სახლებში
        if "keywords" in self.config:
            for formal_cat, kws in self.config["keywords"].items():
                if any(kw.lower() in combined_text for kw in kws):
                    return formal_cat

        # 3. დამატებითი დაზღვევა: ძებნა პროდუქტის სახელით (თუ კატეგორიით ვერ იპოვა)
        name_low = name_raw.lower()
        # შეგვიძლია გამოვიყენოთ VRTX-ის keywords ბაზა სახელებისთვისაც
        all_keywords = self.config.get("keywords") or self.config.get("sub_category_keywords")
        if all_keywords:
            for formal_cat, kws in all_keywords.items():
                if any(kw.lower() in name_low for kw in kws):
                    return formal_cat

        return None

    def _clean_price(self, value):
        if pd.isna(value) or str(value).strip() == "":
            return 0.0
        # ვტოვებთ მხოლოდ ციფრებს, წერტილს და მძიმეს (მძიმეს ვცვლით წერტილით)
        cleaned = str(value).replace(',', '.')
        cleaned = "".join(c for c in cleaned if c.isdigit() or c == '.')
        try:
            return float(cleaned)
        except:
            return 0.0

    def parse(self) -> list[Product]:
        if not self.config:
            logger.error(f"პარსინგი ვერ დაიწყო: კონფიგურაცია {self.distributor_name}-სთვის ვერ მოიძებნა.")
            return []

        try:
            # ვკითხულობთ ექსელს
            df = pd.read_excel(self.file_path, engine="openpyxl")
            # სვეტების გასუფთავება
            df.columns = [str(col).strip() for col in df.columns]

            products = []
            for _, row in df.iterrows():
                category = self._identify_category(row)

                # თუ კატეგორია ვერ დადგინდა, ამ პროდუქტს ვტოვებთ
                if not category:
                    continue

                # --- ფასის ამოღება ---
                price = 0.0
                for col in self.config.get("price_cols", []):
                    if col in row:
                        price = self._clean_price(row.get(col))
                        if price > 0: break

                if price <= 0: continue

                # --- RRP ლოგიკა ---
                rrp = 0.0
                for col in self.config.get("rrp_cols", []):
                    if col in row:
                        rrp = self._clean_price(row.get(col))
                        if rrp > 0: break

                if rrp <= 0:
                    rrp = round(price * 1.10, 2)

                # --- რაოდენობის ლოგიკა ---
                quantity = 0
                q_col = self.config.get("quantity_col")
                if q_col and q_col in row:
                    raw_q = str(row.get(q_col, "0"))
                    cleaned_q = re.sub(r'\D', '', raw_q)
                    quantity = int(cleaned_q) if cleaned_q else 0
                else:
                    # დეფოლტად 1, თუ სვეტი არ არსებობს (მაგ: Oasis)
                    quantity = 1

                # ბრენდის ამოღება
                brand_col = self.config.get("brand_col")
                brand = str(row.get(brand_col, "Unknown")).strip() if brand_col in row else "Unknown"

                # დასახელების ამოღება
                name_col = self.config.get("name_col")
                name = str(row.get(name_col, "No Name")).strip() if name_col in row else "No Name"

                products.append(Product(
                    brand=brand,
                    name=name,
                    quantity=quantity,
                    price=price,
                    rrp_price=rrp,
                    category=category,
                    distributor=self.distributor_name  # ვამატებთ დისტრიბუტორსაც
                ))

            logger.info(f"{self.distributor_name}: წარმატებით დაპარსულია {len(products)} პროდუქტი.")
            return products

        except Exception as e:
            logger.error(f"შეცდომა {self.distributor_name}-ის პარსინგისას: {e}")
            return []