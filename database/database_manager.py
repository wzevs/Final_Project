import sqlite3
from models.product import Product
from utils.logger import logger

class DatabaseManager:
    def __init__(self, db_path: str = "inventory.db"):
        self.db_path = db_path
        self._create_table()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            name TEXT, 
            quantity INTEGER,
            price REAL,
            rrp_price REAL,
            category TEXT,
            distributor TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, distributor)
        )
        """
        with self._get_connection() as conn:
            conn.execute(query)

    def save_products(self, products: list[Product], distributor_name: str):
        query = """
        INSERT INTO products (brand, name, quantity, price, rrp_price, category, distributor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, distributor) DO UPDATE SET
            quantity = excluded.quantity,
            price = excluded.price,
            rrp_price = excluded.rrp_price,
            category = excluded.category,
            last_updated = CURRENT_TIMESTAMP
        """
        # ... (დანარჩენი კოდი)
        saved_count = 0
        with self._get_connection() as conn:
            for p in products:
                try:
                    conn.execute(query, (
                        p.brand, p.name, p.quantity, p.price,
                        p.rrp_price, p.category, distributor_name
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"შეცდომა შენახვისას ({p.name}): {e}")
        logger.info(f"ბაზაში აისახა {saved_count} პროდუქტი დისტრიბუტორისგან: {distributor_name}")

    def get_top_expensive_products(self, limit: int = 10):
        query = "SELECT name, price, quantity, category, distributor FROM products ORDER BY price DESC LIMIT ?"
        with self._get_connection() as conn:
            cursor = conn.execute(query, (limit,))
            return cursor.fetchall()