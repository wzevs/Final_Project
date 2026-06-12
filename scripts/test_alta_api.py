"""Alta SOAP API ტესტი — python scripts/test_alta_api.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from api_clients.alta_client import AltaClient


def main():
    if not os.getenv("ALTA_USERNAME") or not os.getenv("ALTA_PASSWORD"):
        print("ALTA_USERNAME და ALTA_PASSWORD საჭიროა .env-ში.")
        sys.exit(1)

    client = AltaClient()
    print("SOAP GetPriceList ტესტი...")
    result = client.test_connection()
    print(f"მიღებული ჩანაწერები: {result['items_received']}")
    if result.get("sample"):
        print("ნიმუში:", json.dumps(result["sample"], ensure_ascii=False, indent=2))

    print("\nპროდუქტების ფილტრაცია (PC-relevant)...")
    products = client.fetch_products()
    print(f"დამუშავებული: {len(products)}")
    for p in products[:5]:
        print(f"  [{p.sku}] {p.name[:55]} | {p.price}₾ | qty={p.quantity}")


if __name__ == "__main__":
    main()
