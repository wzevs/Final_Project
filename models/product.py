from dataclasses import dataclass


@dataclass
class Product:
    brand: str
    name: str
    quantity: int
    price: float
    rrp_price: float
    category: str
    distributor: str = "Unknown"

    def validate(self):
        # სახელის ვალიდაცია
        if not self.name or str(self.name).lower() == "nan":
            raise ValueError("პროდუქტის სახელი ცარიელია ან არასწორია")

        # ბრენდის გასუფთავება
        if not self.brand or str(self.brand).lower() == "nan":
            self.brand = "Unknown"

        # ფასის ვალიდაცია
        if self.price < 0:
            raise ValueError(f"უარყოფითი ფასი: {self.name}")

        # რაოდენობის ვალიდაცია (რომ შემთხვევით უარყოფითი არ ჩავწეროთ)
        if self.quantity < 0:
            self.quantity = 0