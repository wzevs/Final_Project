import re
import pandas as pd
from rapidfuzz import fuzz
from database.database_manager import DatabaseManager


class StoreraService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.clean_regex = re.compile(r'[®™\-\(\)\+\,\.\/]')

    def clean_and_normalize(self, text: str) -> str:
        """ასუფთავებს ტექსტს ბაზის შედარებისთვის"""
        if not text or pd.isna(text):
            return ""
        text = str(text).upper()
        text = self.clean_regex.sub(' ', text)
        return " ".join(text.split())

    def extract_model_code(self, cleaned_text: str) -> str:
        """ტექსტიდან ამოაქვს ტექნიკური მოდელის კოდი"""
        words = cleaned_text.split()
        for word in words:
            if any(char.isdigit() for char in word) and len(word) >= 3:
                return word
        return None

    def find_best_match(self, storera_name: str, supplier_df: pd.DataFrame, threshold=80):
        """ჰიბრიდული ძებნა: Regex + Fuzzy Matching მომწოდებლის ბაზაში"""
        clean_storera = self.clean_and_normalize(storera_name)
        storera_model = self.extract_model_code(clean_storera)

        best_score = 0
        best_match_row = None

        for index, row in supplier_df.iterrows():
            # ვეძებთ ბაზის ქართულ სვეტში: 'დასახელება'
            clean_supplier = self.clean_and_normalize(row['დასახელება'])
            supplier_model = self.extract_model_code(clean_supplier)

            # ეტაპი 1: მოდელის კოდის ზუსტი დამთხვევა
            if storera_model and supplier_model and storera_model == supplier_model:
                return row, 100

            # ეტაპი 2: ბუნდოვანი შედარება
            score = fuzz.token_sort_ratio(clean_storera, clean_supplier)

            if score > best_score:
                best_score = score
                best_match_row = row

        if best_score >= threshold:
            return best_match_row, best_score

        return None, 0

    def process_storera_feed(self, storera_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """ანახლებს მხოლოდ მარაგებს, ფასებს ტოვებს ხელუხლებლად და აგროვებს ცვლილებების ისტორიას"""
        db_df = self.db_manager.fetch_products_dataframe()
        if db_df.empty:
            return storera_df, pd.DataFrame()

        # ვფილტრავთ აქტიურ ნაშთებს და ვახარისხებთ ფასის მიხედვით (ყველაზე იაფის ასარჩევად)
        active_supplier_stock = db_df[db_df["რაოდენობა"] > 0].copy()
        active_supplier_stock = active_supplier_stock.sort_values(by="ფასი (₾)", ascending=True)

        updated_storera = storera_df.copy()

        # აქ შევინახავთ მხოლოდ შეცვლილ სტრიქონებს ვიზუალიზაციისთვის
        change_logs = []

        # 🛡️ უსაფრთხოების ფარი: აწყობილი პერსონალური კომპიუტერების კატეგორიები
        pc_build_categories = ["სათამაშო/სარენდერო", "პრემიალური", "საოფისე"]

        for index, row in updated_storera.iterrows():
            current_category = str(row.get("კატეგორია", "")).strip()

            # 🛡️ თუ აწყობილი კომპიუტერია - საერთოდ არ ვეხებით
            if current_category in pc_build_categories:
                continue

            product_name = row.get("სახელი")
            orig_qty = row.get("რაოდენობა", 0)

            # უსაფრთხო კონვერტაცია ციფრში
            orig_qty = int(orig_qty) if not pd.isna(orig_qty) else 0

            if not pd.isna(product_name):
                best_match, match_score = self.find_best_match(product_name, active_supplier_stock)

                if best_match is not None:
                    new_qty = int(best_match["რაოდენობა"])
                    updated_storera.at[index, "რაოდენობა"] = new_qty
                    updated_storera.at[index, "აქტიური"] = 1

                    # თუ მარაგი რეალურად შეიცვალა, ვიწერთ რეპორტისთვის
                    if orig_qty != new_qty:
                        change_logs.append({
                            "პროდუქტი": product_name,
                            "კატეგორია": current_category,
                            "ძველი მარაგი": orig_qty,
                            "ახალი მარაგი": new_qty,
                            "სტატუსი": "🔄 განახლდა"
                        })
                else:
                    # თუ პროდუქტი მომწოდებლებთან აღარ არის, საიტზე მარაგს ვსვამთ 0-ზე
                    if orig_qty > 0:
                        updated_storera.at[index, "რაოდენობა"] = 0
                        change_logs.append({
                            "პროდუქტი": product_name,
                            "კატეგორია": current_category,
                            "ძველი მარაგი": orig_qty,
                            "ახალი მარაგი": 0,
                            "სტატუსი": "❌ ამოიწურა"
                        })

        return updated_storera, pd.DataFrame(change_logs)