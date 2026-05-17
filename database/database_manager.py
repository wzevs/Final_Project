import sqlite3
import pandas as pd

# თუ პროექტში logger გაქვს, დაიტოვე ეს იმპორტი, თუ არა - შეცდომას არ ამოაგდებს
try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path="inventory.db"):
        self.db_path = db_path

    def create_user_table(self):
        """ქმნის მომხმარებლებისა და პროდუქტების ცხრილებს, თუ არ არსებობს"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS users
                           (
                               username TEXT PRIMARY KEY,
                               password TEXT NOT NULL,
                               email    TEXT NOT NULL,
                               name     TEXT NOT NULL
                           )
                           """)
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS products
                           (
                               id          INTEGER PRIMARY KEY AUTOINCREMENT,
                               category    TEXT,
                               name        TEXT,
                               price       REAL,
                               quantity    INTEGER,
                               distributor TEXT
                           )
                           """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"ცხრილების შექმნის შეცდომა: {e}")

    def add_user(self, username, password, email, name):
        """უსაფრთხოდ ამატებს ან აახლებს მომხმარებელს პარამეტრიზებული ქუერით"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO users (username, password, email, name) VALUES (?, ?, ?, ?)",
                (username, password, email, name)
            )
            conn.commit()
            conn.close()
            logger.info(f"მომხმარებელი {username} წარმატებით შეინახა ბაზაში.")
        except Exception as e:
            logger.error(f"მომხმარებლის ბაზაში ჩაწერის შეცდომა: {e}")

    def save_products(self, products, distributor):
        """აშლის ძველ პროდუქტებს კონკრეტული მომწოდებლისთვის და წერს ახლებს"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE distributor = ?", (distributor,))

            for p in products:
                # მხარს უჭერს როგორც ობიექტს (p.name), ასევე დიქტს (p['name'])
                p_cat = getattr(p, 'category', p.get('category') if isinstance(p, dict) else '')
                p_name = getattr(p, 'name', p.get('name') if isinstance(p, dict) else '')
                p_price = getattr(p, 'price', p.get('price') if isinstance(p, dict) else 0.0)
                p_qty = getattr(p, 'quantity', p.get('quantity') if isinstance(p, dict) else 0)

                cursor.execute(
                    "INSERT INTO products (category, name, price, quantity, distributor) VALUES (?, ?, ?, ?, ?)",
                    (p_cat, p_name, p_price, p_qty, distributor)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"პროდუქტების ბაზაში შენახვის შეცდომა: {e}")

    def get_all_users(self) -> dict:
        """უსაფრთხოდ ამოაქვს ყველა მომხმარებელი ავტორიზაციის მენეჯერისთვის"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            users = conn.execute("SELECT username, password, email, name FROM users").fetchall()
            conn.close()

            user_dict = {'usernames': {}}
            for u in users:
                user_dict['usernames'][u['username']] = {
                    'email': u['email'],
                    'name': u['name'],
                    'password': u['password']
                }
            return user_dict
        except Exception as e:
            logger.error(f"მომხმარებლების წაკითხვის შეცდომა: {e}")
            return {'usernames': {}}

    def get_all_usernames(self) -> list:
        """აბრუნებს ყველა მომხმარებლის სახელების სიას ვალიდაციისთვის"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users")
            usernames = [row[0] for row in cursor.fetchall()]
            conn.close()
            return usernames
        except Exception as e:
            logger.error(f"იუზერნეიმების წაკითხვის შეცდომა: {e}")
            return []

    def fetch_products_dataframe(self) -> pd.DataFrame:
        """ცენტრალიზებულად კითხულობს პროდუქტებს და აბრუნებს Pandas DataFrame-ს"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT category, name, price, quantity, distributor FROM products"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            logger.error(f"პროდუქტების DataFrame-ის შექმნის შეცდომა: {e}")
            return pd.DataFrame()