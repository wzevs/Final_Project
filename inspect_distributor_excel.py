"""
ახალი მომწოდებლის Excel-ის სვეტების სწრაფი შემოწმება.
გაშვება:
    python inspect_distributor_excel.py
    python inspect_distributor_excel.py "data/distributor_files/oasis_stock.xlsx"
"""
import json
import sys

import pandas as pd

DEFAULT_FOLDER = "data/distributor_files/"


def inspect_file(path: str):
    df = pd.read_excel(path, engine="openpyxl", nrows=5)
    df.columns = [str(c).strip() for c in df.columns]
    print(f"\n=== {path} ===")
    print(f"სვეტები ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")
    print("\nპირველი 2 ხაზი:")
    print(df.head(2).to_string(index=False))


def main():
    if len(sys.argv) > 1:
        inspect_file(sys.argv[1])
        return

    import os
    if not os.path.exists(DEFAULT_FOLDER):
        print(f"საქაღალდე არ არსებობს: {DEFAULT_FOLDER}")
        return

    files = [f for f in os.listdir(DEFAULT_FOLDER) if f.endswith((".xlsx", ".xls"))]
    if not files:
        print(f"ფაილები არ მოიძებნა: {DEFAULT_FOLDER}")
        return

    for name in sorted(files):
        inspect_file(os.path.join(DEFAULT_FOLDER, name))

    with open("config/distributors.json", encoding="utf-8") as f:
        configs = json.load(f)
    print("\n=== კონფიგურირებული მომწოდებლები ===")
    for key, cfg in configs.items():
        keywords = cfg.get("file_keywords", [key])
        print(f"  {key}: ფაილის სახელში → {', '.join(keywords)}")


if __name__ == "__main__":
    main()
