import os
from parsers.excel_parser import ExcelParser
from database.database_manager import DatabaseManager
from utils.logger import logger


class ProductService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

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

        # თუ დისტრიბუტორი ხელით არ არის მითითებული, ამოვიცნოთ სახელით
        if not distributor:
            distributor = self._detect_distributor(file_name)

        logger.info(f"პროცესი დაიწყო: {file_name} | დისტრიბუტორი: {distributor}")

        # პარსერს გადავცემთ ფაილის გზას და დისტრიბუტორის სახელს (erc/oasis)
        parser = ExcelParser(file_path, distributor)
        products = parser.parse()

        if products:
            # მნიშვნელოვანი ცვლილება: ბაზაში ვინახავთ დისტრიბუტორის მითითებით
            self.db_manager.save_products(products, distributor)
            logger.info(f"წარმატებით აისახა {len(products)} პროდუქტი ({distributor}).")
        else:
            logger.warning(f"ვალიდური მონაცემები ფაილიდან {file_name} ვერ წამოვიდა.")

    def import_all_from_folder(self, folder_path: str):
        """სკანირებას უკეთებს საქაღალდეს და ავტომატურად ანაწილებს ფაილებს"""
        if not os.path.exists(folder_path):
            logger.error(f"საქაღალდე ვერ მოიძებნა: {folder_path}")
            return

        files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx')]

        if not files:
            logger.warning(f"საქაღალდეში {folder_path} ექსელის ფაილები არ მოიძებნა.")
            return

        for file_name in files:
            full_path = os.path.join(folder_path, file_name)
            # თითოეული ფაილისთვის ინდივიდუალურად მოხდება იმპორტი და დეტექცია
            self.import_from_excel(full_path)