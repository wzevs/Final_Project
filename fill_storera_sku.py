"""
ერთჯერადი სკრიპტი: ცარიელ შიდა კოდს ავსებს SKU-ით აღწერიდან/სახელიდან.
გაშვება:
    python fill_storera_sku.py
    python fill_storera_sku.py "C:\\path\\to\\storera.xlsx"
"""
import sys

import pandas as pd

from utils.sku_utils import STORERA_CODE_COLUMN, extract_sku_from_text, is_empty_code

DEFAULT_INPUT = r"c:\Users\User1\Desktop\storera_geekspot.ge_products.xlsx"


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = input_path.replace(".xlsx", "_sku_filled.xlsx")

    df = pd.read_excel(input_path)
    if STORERA_CODE_COLUMN not in df.columns:
        df[STORERA_CODE_COLUMN] = ""

    filled = 0
    for index, row in df.iterrows():
        if not is_empty_code(row.get(STORERA_CODE_COLUMN)):
            continue
        sku = extract_sku_from_text(row.get("სახელი", ""), row.get("აღწერა", ""))
        if sku:
            df.at[index, STORERA_CODE_COLUMN] = sku
            filled += 1

    df.to_excel(output_path, index=False, sheet_name="პროდუქციის ჩამონათვალი")
    print(f"Done: {filled} rows filled -> {output_path}")


if __name__ == "__main__":
    main()
