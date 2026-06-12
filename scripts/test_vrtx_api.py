"""VRTX API ტესტი — python scripts/test_vrtx_api.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from api_clients.vrtx_client import VrtxClient


def main():
    if not os.getenv("VRTX_API_TOKEN") and not os.getenv("VRTX_API_URL"):
        print("VRTX_API_TOKEN საჭიროა .env-ში.")
        sys.exit(1)

    client = VrtxClient()
    info = client.test_connection()
    print(f"API total: {info['total']}")

    products = client.fetch_products()
    print(f"PC filtered: {len(products)}")
    with_sku = sum(1 for p in products if p.sku)
    print(f"with SKU: {with_sku}")

    if products:
        sample = products[:5]
        print(json.dumps(
            [{"sku": p.sku, "name": p.name[:50], "cat": p.category, "price": p.price, "qty": p.quantity}
             for p in sample],
            ensure_ascii=False,
            indent=2,
        ))


if __name__ == "__main__":
    main()
