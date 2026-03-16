import argparse
import os
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from utils.logger import logger
from api_clients.gitec_client import GitecClient  # შევასწორე სახელი კლასის მიხედვით


def main():
    parser = argparse.ArgumentParser(description="Inventory Import Tool")
    parser.add_argument("path", help="Path to the Excel file or folder containing files")
    args = parser.parse_args()

    try:
        # 1. ინიციალიზაცია
        db = DatabaseManager()
        service = ProductService(db)

        # 2. ექსელების იმპორტის ლოგიკა
        if os.path.isdir(args.path):
            print(f"📂 აღმოჩენილია საქაღალდე. ვიწყებ სკანირებას: {args.path}")
            service.import_all_from_folder(args.path)
        elif os.path.isfile(args.path):
            service.import_from_excel(args.path)
        else:
            print(f"❌ შეცდომა: მითითებული გზა '{args.path}' არასწორია.")
            # აქ არ ვაჩერებთ, რომ API მაინც გაეშვას თუ საჭიროა

        # --- 3. GITEC API ტესტირება და იმპორტი ---
        print("\n🌐 ვუკავშირდები GITEC API-ს...")

        # ⚠️ ჩაწერე შენი ნამდვილი მონაცემები აქ:
        gitec = GitecClient(username="შენი_იუზერი", password="შენი_პაროლი")
        gitec_products = gitec.fetch_products()

        if gitec_products:
            print(f"✅ API ტესტი წარმატებულია! წამოღებულია {len(gitec_products)} პროდუქტი.")
            db.save_products(gitec_products, "gitec")
        else:
            print("❌ API-დან მონაცემები ვერ წამოვიდა (შეამოწმეთ ლოგები ან პაროლები).")

        # 4. შედეგების გამოტანა (უკვე გაერთიანებული ბაზიდან)
        print("\n💰 ტოპ 10 ყველაზე ძვირიანი კომპონენტი ბაზიდან:")
        top_products = db.get_top_expensive_products(10)

        if not top_products:
            print("⚠️ ბაზაში მონაცემები ვერ მოიძებნა.")
        else:
            header = f"{'კატეგორია':<20} | {'დასახელება':<45} | {'ფასი':<10} | {'რაოდენობა':<6} | {'მომწოდებელი':<10}"
            print(header)
            print("-" * len(header))

            for row in top_products:
                category = row['category'][:18] if row['category'] else "N/A"
                raw_name = row['name']
                name = (raw_name[:42] + "...") if len(raw_name) > 42 else raw_name
                price = row['price']
                quantity = row['quantity']
                distributor = row['distributor'].upper() if row['distributor'] else "N/A"

                print(f"{category:<20} | {name:<45} | {price:>8.2f} | {quantity:^6} | {distributor:<10}")

        print("\n✅ პროცესი დასრულდა.")

    except Exception as e:
        logger.error(f"კრიტიკული შეცდომა main-ში: {e}")
        print(f"❌ მოხდა შეცდომა. დეტალები იხილეთ ლოგებში.")


if __name__ == "__main__":
    main()