import sqlite3
import pandas as pd
from utils.logger import logger


class DatabaseManager:
    def __init__(self, db_path: str = "inventory.db"):
        self.db_path = db_path
        # აპლიკაციის ინიციალიზაციისთანავე ავტომატურად ვქმნით პროდუქტების ცხრილს
        self.create_products_table()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def create_user_table(self):
        """ქმნის მომხმარებლების ცხრილს ავტორიზაციის სისტემისთვის"""
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS users
                           (
                               username TEXT PRIMARY KEY,
                               password TEXT NOT NULL,
                               email    TEXT,
                               name     TEXT
                           )
                           """)
            connection.commit()
        except Exception as e:
            logger.error(f"users ცხრილის შექმნის შეცდომა: {e}")
        finally:
            connection.close()

    def create_products_table(self):
        """ქმნის პროდუქტების ცხრილს და უნიკალურ ინდექსს დუბლიკატების დასაზღვევად"""
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS products
                           (
                               id          INTEGER PRIMARY KEY AUTOINCREMENT,
                               brand       TEXT,
                               name        TEXT,
                               quantity    INTEGER,
                               price       REAL,
                               rrp_price   REAL,
                               category    TEXT,
                               distributor TEXT
                           )
                           """)

            # 🚀 ქმნის უნიკალურ ინდექსს სახელსა და დისტრიბუტორზე.
            # ეს აუცილებელია, რათა INSERT OR REPLACE-მა ზუსტად იცოდეს, რომელი პროდუქტი განაახლოს
            cursor.execute("""
                           CREATE UNIQUE INDEX IF NOT EXISTS idx_products_name_distributor
                               ON products (name, distributor)
                           """)
            self._ensure_sku_column(cursor)
            self._ensure_distributor_code_column(cursor)
            connection.commit()
        except Exception as e:
            logger.error(f"products ცხრილის შექმნის შეცდომა: {e}")
        finally:
            connection.close()

    def _ensure_sku_column(self, cursor):
        cursor.execute("PRAGMA table_info(products)")
        columns = {row[1] for row in cursor.fetchall()}
        if "sku" not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN sku TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products (sku)")

    def _ensure_distributor_code_column(self, cursor):
        cursor.execute("PRAGMA table_info(products)")
        columns = {row[1] for row in cursor.fetchall()}
        if "distributor_code" not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN distributor_code TEXT")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_distributor_code "
                "ON products (distributor_code)"
            )

    def delete_products_by_distributor(self, distributor: str):
        """შლის მომწოდებლის ყველა პროდუქტს — ძველი/ამოღებული ნივთების გასასუფთავებლად."""
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM products WHERE distributor = ?", (distributor,))
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"პროდუქტების წაშლის შეცდომა ({distributor}): {e}")
            raise e
        finally:
            connection.close()

    def save_products(self, products, distributor):
        """ინახავს ან ანახლებს პროდუქტებს ბაზაში (დუბლიკატების დაზღვევით)"""
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            query = """
                INSERT OR REPLACE INTO products (
                    brand, name, quantity, price, rrp_price, category, distributor, sku, distributor_code
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            data = []
            for p in products:
                p.validate()
                data.append(
                    (
                        p.brand, p.name, p.quantity, p.price, p.rrp_price,
                        p.category, distributor, p.sku or "",
                        getattr(p, "distributor_code", "") or "",
                    )
                )

            cursor.executemany(query, data)
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"პროდუქტების ბაზაში შეცხადების/შენახვის შეცდომა: {e}")
            raise e
        finally:
            connection.close()

    def fetch_products_dataframe(self) -> pd.DataFrame:
        """მოაქვს ყველა პროდუქტი გლობალურად, რაც აუცილებელია უნივერსალური სახელით ძებნისთვის"""
        connection = self._get_connection()
        try:
            query = (
                "SELECT brand, name, quantity, price, rrp_price, category, distributor, sku, "
                "distributor_code FROM products"
            )
            df = pd.read_sql_query(query, connection)

            df.columns = [
                "ბრენდი", "დასახელება", "რაოდენობა", "ფასი (₾)",
                "RRP ფასი", "კატეგორია", "მომწოდებელი", "SKU", "მომწოდებლის კოდი",
            ]

            # მომწოდებლის სახელების დიდ ასოებში გადაყვანა
            df["მომწოდებელი"] = df["მომწოდებელი"].str.upper()
            return df
        except Exception as e:
            logger.error(f"ბაზიდან პროდუქტების წაკითხვის შეცდომა: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    # =================================================================
    # 🔒 მომხმარებლების მართვის ბლოკი (Streamlit Authenticator)
    # =================================================================
    def get_all_users(self) -> dict:
        """აბრუნებს ყველა მომხმარებელს ავტორიზაციის მოდულისთვის საჭირო სტრუქტურით"""
        connection = self._get_connection()
        cursor = connection.cursor()
        credentials = {"usernames": {}}
        try:
            cursor.execute("SELECT username, password, email, name FROM users")
            rows = cursor.fetchall()
            for row in rows:
                credentials["usernames"][row[0]] = {
                    "password": row[1],
                    "email": row[2],
                    "name": row[3]
                }
        except Exception as e:
            logger.error(f"იუზერების წაკითხვის შეცდომა: {e}")
        finally:
            connection.close()
        return credentials

    def get_all_usernames(self) -> list:
        """აბრუნებს ყველა არსებულ მომხმარებლის სახელს სიის სახით"""
        connection = self._get_connection()
        cursor = connection.cursor()
        usernames = []
        try:
            cursor.execute("SELECT username FROM users")
            usernames = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"იუზერნეიმების წაკითხვის შეცდომა: {e}")
        finally:
            connection.close()
        return usernames

    def add_user(self, username, password, email, name):
        """ამატებს ახალ მომხმარებელს მონაცემთა ბაზაში"""
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                           INSERT INTO users (username, password, email, name)
                           VALUES (?, ?, ?, ?)
                           """, (username, password, email, name))
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"ახალი იუზერის ჩაწერის შეცდომა: {e}")
            raise e
        finally:
            connection.close()