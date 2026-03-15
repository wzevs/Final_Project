import argparse
import os
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Inventory Import Tool")
    # შევცვალოთ "file" უფრო ზოგადი "path"-ით
    parser.add_argument("path", help="Path to the Excel file or folder containing files")
    args = parser.parse_args()

    try:
        # 1. ინიციალიზაცია
        db = DatabaseManager()
        service = ProductService(db)

        # 2. იმპორტის ლოგიკა
        if os.path.isdir(args.path):
            print(f"📂 აღმოჩენილია საქაღალდე. ვიწყებ სკანირებას: {args.path}")
            service.import_all_from_folder(args.path)
        elif os.path.isfile(args.path):
            # თუ ერთი ფაილია, სერვისი თავად ამოიცნობს დისტრიბუტორს სახელის მიხედვით
            service.import_from_excel(args.path)
        else:
            print(f"❌ შეცდომა: მითითებული გზა '{args.path}' არასწორია.")
            return

        # 3. შედეგების გამოტანა
        print("\n💰 ტოპ 10 ყველაზე ძვირიანი კომპონენტი ბაზიდან:")
        top_products = db.get_top_expensive_products(10)

        if not top_products:
            print("⚠️ ბაზაში მონაცემები ვერ მოიძებნა.")
        else:
            # სათაურში ვამატებთ "მომწოდ."-ს
            header = f"{'კატეგორია':<20} | {'დასახელება':<45} | {'ფასი':<10} | {'რაოდენობა':<6} | {'მომწოდებელი':<10}"
            print(header)
            print("-" * len(header))

            for row in top_products:
                category = row['category'][:18] if row['category'] else "N/A"

                # სახელის შემოკლება
                raw_name = row['name']
                name = (raw_name[:42] + "...") if len(raw_name) > 42 else raw_name

                price = row['price']
                quantity = row['quantity']
                # ვიღებთ მომწოდებლის სახელს ბაზიდან
                distributor = row['distributor'].upper() if row['distributor'] else "N/A"

                # ვბეჭდავთ გაერთიანებულ ხაზს
                print(f"{category:<20} | {name:<45} | {price:>8.2f} | {quantity:^6} | {distributor:<10}")

        print("\n✅ პროცესი დასრულდა.")

    except Exception as e:
        logger.error(f"კრიტიკული შეცდომა main-ში: {e}")
        print(f"❌ მოხდა შეცდომა. დეტალები იხილეთ ლოგებში.")


if __name__ == "__main__":
    main()