import os
import pandas as pd
from parsers.excel_parser import ExcelParser
from database.database_manager import DatabaseManager
from utils.logger import logger


class ProductService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # 🚀 ძველი ბლექლისტი წაიშალა! ახლა ვტოვებთ მხოლოდ აშკარა არასაჭირო სერვისულ სიტყვებს, თუ ასეთი შემოგვეპარა
        self.garbage_keywords = [
            "მიწოდების სერვისი", "კურიერის მომსახურება", "გარანტიის გაგრძელება"
        ]

    def is_valid_component(self, product_name: str) -> bool:
        """ამოწმებს, არის თუ არა სტრიქონი რეალური პროდუქტი და არა ნაგავი ჩანაწერი"""
        if not product_name or pd.isna(product_name):
            return False

        name_low = str(product_name).lower().strip()

        # თუ სახელი ძალიან მოკლეა (მაგ: ცარიელი ადგილები ან უცნაური სიმბოლოები)
        if len(name_low) < 2:
            return False

        # ბლოკავს მხოლოდ აშკარა სერვისულ ჩანაწერებს
        return not any(garbage in name_low for garbage in self.garbage_keywords)

    def _detect_distributor(self, file_name: str) -> str:
        """ავტომატურად ამოიცნობს დისტრიბუტორს ფაილის სახელის მიხედვით"""
        name_low = file_name.lower()
        if "erc" in name_low:
            return "erc"
        elif "oasis" in name_low:
            return "oasis"
        elif "vrtx" in name_low:
            return "vrtx"
        return "default_distributor"

    def import_from_excel(self, file_path: str, distributor: str = None):
        """ერთი კონკრეტული ექსელის ფაილის იმპორტი და ბაზაში შენახვა"""
        file_name = os.path.basename(file_path)
        if not distributor:
            distributor = self._detect_distributor(file_name)

        logger.info(f"მომწოდებლის ფაილის დამუშავება დაიწყო: {file_name} | დისტრიბუტორი: {distributor}")

        parser = ExcelParser(file_path, distributor)
        products = parser.parse()

        if products:
            # ატარებს ფილტრაციას (ახლა პერიფერიაც სუფთად ძვრება აქ)
            valid_products = [p for p in products if self.is_valid_component(p.name)]
            if valid_products:
                self.db_manager.save_products(valid_products, distributor)
                logger.info(f"წარმატებით აისახა {len(valid_products)} პროდუქტი ბაზაში ({distributor}).")
            else:
                logger.warning(f"ფაილიდან {file_name} ვალიდური მონაცემები ვერ წამოვიდა.")
        else:
            logger.warning(f"ფაილიდან {file_name} მონაცემების წაკითხვა ვერ მოხერხდა (პარსერის შეცდომა).")

    def import_all_from_folder(self, folder_path: str):
        """ავტომატურად ასკანირებს მთელ საქაღალდეს და აიმპორტებს ყველა .xlsx ფაილს"""
        if not os.path.exists(folder_path):
            logger.error(f"საქაღალდე ვერ მოიძებნა: {folder_path}")
            return

        files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx') or f.endswith('.xls')]
        if not files:
            logger.warning(f"საქაღალდეში {folder_path} ექსელის ფაილები არ მოიძებნა.")
            return

        for file_name in files:
            full_path = os.path.join(folder_path, file_name)
            self.import_from_excel(full_path)

    def import_gitec_products(self, gitec_products):
        """ფილტრავს და ინახავს GITEC API-დან წამოღებულ პროდუქტებს"""
        if not gitec_products:
            return

        valid_products = [p for p in gitec_products if self.is_valid_component(p.name)]
        if valid_products:
            self.db_manager.save_products(valid_products, "gitec")
            logger.info(f"წარმატებით აისახა {len(valid_products)} პროდუქტი GITEC API-დან.")
        else:
            logger.warning("GITEC API-დან წამოღებული ყველა პროდუქტი დაიბლოკა.")

    def get_all_products(self) -> pd.DataFrame:
        """კითხულობს ყველა პროდუქტს ბაზის ცენტრალიზებული მენეჯერის მეშვეობით"""
        return self.db_manager.fetch_products_dataframe()