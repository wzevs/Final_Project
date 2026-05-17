import os
import pandas as pd
from parsers.excel_parser import ExcelParser
from database.database_manager import DatabaseManager
from utils.logger import logger


class ProductService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.blacklist = [
            "backpack", "bag", "ზურგჩანთა", "ჩანთა",
            "notebook case", "laptop case", "sleeve",
            "cleaning kit", "mouse pad", "მაუსის პადი"
        ]

    def is_valid_component(self, product_name: str) -> bool:
        """ამოწმებს, არის თუ არა პროდუქტი ნამდვილად კომპიუტერის ნაწილი"""
        if not product_name:
            return False
        name_low = product_name.lower()
        return not any(bad_word in name_low for bad_word in self.blacklist)

    def _detect_distributor(self, file_name: str) -> str:
        """ამოიცნობს დისტრიბუტორს ფაილის სახელის მიხედვით"""
        name_low = file_name.lower()
        if "erc" in name_low:
            return "erc"
        elif "oasis" in name_low:
            return "oasis"
        elif "vrtx" in name_low:
            return "vrtx"
        return "default_distributor"

    def import_from_excel(self, file_path: str, distributor: str = None):
        """ერთი ექსელის ფაილის იმპორტი ავტომატური დეტექციით"""
        file_name = os.path.basename(file_path)
        if not distributor:
            distributor = self._detect_distributor(file_name)

        logger.info(f"პროცესი დაიწყო: {file_name} | დისტრიბუტორი: {distributor}")

        parser = ExcelParser(file_path, distributor)
        products = parser.parse()

        if products:
            valid_products = [p for p in products if self.is_valid_component(p.name)]
            if valid_products:
                self.db_manager.save_products(valid_products, distributor)
                logger.info(f"წარმატებით აისახა {len(valid_products)} პროდუქტი ({distributor}).")
            else:
                logger.warning(f"ვალიდური მონაცემები ფაილიდან {file_name} ვერ წამოვიდა (ყველა დაიბლოკა).")
        else:
            logger.warning(f"ვალიდური მონაცემები ფაილიდან {file_name} ვერ წამოვიდა.")

    def import_all_from_folder(self, folder_path: str):
        """სკანირებას უკეთებს საქაღალდეს"""
        if not os.path.exists(folder_path):
            logger.error(f"საქაღალდე ვერ მოიძებნა: {folder_path}")
            return

        files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx')]
        if not files:
            logger.warning(f"საქაღალდეში {folder_path} ექსელის ფაილები არ მოიძებნა.")
            return

        for file_name in files:
            full_path = os.path.join(folder_path, file_name)
            self.import_from_excel(full_path)

    def import_gitec_products(self, gitec_products):
        """ფილტრავს და ინახავს GITEC API პროდუქტებს"""
        if not gitec_products:
            return

        valid_products = [p for p in gitec_products if self.is_valid_component(p.name)]
        if valid_products:
            self.db_manager.save_products(valid_products, "gitec")
            logger.info(f"წარმატებით აისახა {len(valid_products)} პროდუქტი GITEC API-დან.")
        else:
            logger.warning("GITEC API-დან წამოღებული ყველა პროდუქტი დაიბლოკა შავი სიით.")

    def get_all_products(self) -> pd.DataFrame:
        """🚀 შესწორება: კითხულობს პროდუქტებს ბაზის ცენტრალიზებული მენეჯერის მეშვეობით"""
        return self.db_manager.fetch_products_dataframe()