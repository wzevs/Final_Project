from config.settings import settings
# ... სხვა იმპორტები

class DatabaseManager:
    def __init__(self, db_path: str = None):
        # თუ db_path არ მოგვაწოდეს, ვიყენებთ settings-იდან
        self.db_path = db_path or settings.DB_NAME
        self._create_table()