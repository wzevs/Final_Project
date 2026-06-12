"""საიტის (Storera) მონიტორები vs მომწოდებლების ბაზა — SKU მეჩინგი."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from database.database_manager import DatabaseManager
from utils.category_groups import add_group_column
from utils.sku_utils import STORERA_CODE_COLUMN, extract_sku_from_text, is_empty_code, normalize_sku

STORERA_CANDIDATES = [
    Path(r"C:\Users\User1\Desktop\storera_geekspot.ge_products.xlsx"),
    Path(r"C:\Users\User1\Desktop\New folder (2)\storera_geekspot.ge_products.xlsx"),
    Path(r"C:\Users\User1\Desktop\Final Project - test\storera_geekspot.ge_products.xlsx"),
]

EXCLUDE_NAME = re.compile(
    r"desk|chair|headset|headphone|keyboard|mouse|pad|scope|impact|h3 wireless|"
    r"go core|arm|mount|stand|სკამ|მაგიდ",
    re.I,
)
MONITOR_NAME = re.compile(
    r"monitor|მონიტორი|odyssey|rog strix xg|tuf gaming vg|zowie|gaming monitor|"
    r"gs25f2|gs27qxa|kg320|kg325|thinkvision",
    re.I,
)


def find_storera_file() -> Path:
    best: Path | None = None
    best_monitors = -1
    for path in STORERA_CANDIDATES:
        if not path.exists():
            continue
        df = pd.read_excel(path)
        n = len(filter_site_monitors(df))
        if n > best_monitors:
            best_monitors = n
            best = path
    if best is None:
        raise FileNotFoundError("Storera Excel ვერ მოიძებნა")
    return best


def filter_site_monitors(df: pd.DataFrame) -> pd.DataFrame:
    names = df["სახელი"].astype(str)
    mask = names.str.contains(MONITOR_NAME) & ~names.str.contains(EXCLUDE_NAME)
    return df[mask].copy()


def resolve_site_sku(row: pd.Series) -> str:
    code = row.get(STORERA_CODE_COLUMN, "")
    if not is_empty_code(code):
        return str(code).strip()
    name = str(row.get("სახელი", ""))
    desc = str(row.get("აღწერა", ""))
    sku = extract_sku_from_text(desc, name)
    if sku:
        return sku
    # მოდელი ფრჩხილებში: (LS34J550WQIXCI)
    paren = re.search(r"\(([A-Z0-9][A-Z0-9\-]{4,})\)", name, re.I)
    if paren:
        return paren.group(1)
    # Gigabyte GS25F2 სტილი
    words = name.split()
    for token in reversed(words):
        if re.match(r"^[A-Z]{1,3}\d{2}[A-Z0-9\+]*$", token, re.I):
            return token
    return ""


def main():
    storera_path = find_storera_file()
    recent_path = Path(r"C:\Users\User1\Desktop\storera_geekspot.ge_products.xlsx")
    print(f"Storera ფაილი: {storera_path}")
    if recent_path.exists():
        print(f"ბოლო ექსპორტი (SKU-ებით): {recent_path}")
    storera = pd.read_excel(storera_path)
    if recent_path.exists() and recent_path != storera_path:
        recent = pd.read_excel(recent_path)
        storera = pd.concat([storera, recent], ignore_index=True).drop_duplicates(
            subset=["სახელი"], keep="last"
        )
    site_monitors = filter_site_monitors(storera)
    site_monitors["resolved_sku"] = site_monitors.apply(resolve_site_sku, axis=1)

    print(f"სულ პროდუქტი საიტზე: {len(storera)}")
    print(f"მონიტორები საიტზე: {len(site_monitors)}")
    print("კატეგორიები:", site_monitors["კატეგორია"].value_counts().to_dict())
    print()

    db = add_group_column(DatabaseManager().fetch_products_dataframe())
    db_monitors = db[db["ჯგუფი"] == "მონიტორები"].copy()
    print(f"მონიტორები ბაზაში: {len(db_monitors)}")
    print(db_monitors.groupby("მომწოდებელი").size().to_dict())
    print()

    sku_index: dict[str, list] = {}
    for _, row in db_monitors.iterrows():
        key = normalize_sku(row.get("SKU", ""))
        if key:
            sku_index.setdefault(key, []).append(row)

    matched = []
    unmatched = []
    no_sku = []

    for _, row in site_monitors.iterrows():
        sku = row["resolved_sku"]
        entry = {
            "სახელი": row.get("სახელი", ""),
            "შიდა კოდი (საიტი)": str(row.get(STORERA_CODE_COLUMN, "")).strip()
            if not is_empty_code(row.get(STORERA_CODE_COLUMN))
            else "",
            "გამოყენებული SKU": sku,
            "კატეგორია": row.get("კატეგორია", ""),
            "რაოდენობა": row.get("რაოდენობა", 0),
            "აქტიური": row.get("აქტიური", 0),
        }

        if not sku:
            no_sku.append(entry)
            continue

        hits = sku_index.get(normalize_sku(sku))
        if hits:
            best = sorted(hits, key=lambda r: (-int(r["რაოდენობა"]), r["ფასი (₾)"]))[0]
            matched.append({
                **entry,
                "მომწოდებელი": best["მომწოდებელი"],
                "მარაგი მომწოდებელთან": int(best["რაოდენობა"]),
                "ფასი მომწოდებელთან": best["ფასი (₾)"],
            })
        else:
            unmatched.append(entry)

    print(f"=== ნაპოვნია მომწოდებელთან: {len(matched)}")
    print(f"=== არ იძებნება: {len(unmatched)}")
    print(f"=== SKU ვერ გამოიცნო: {len(no_sku)}")
    print()

    if matched:
        print("--- ნაპოვნი (სინქრონიზაცია შესაძლებელია) ---")
        for m in matched:
            print(
                f"  [{m['გამოყენებული SKU']}] {str(m['სახელი'])[:55]}"
                f" -> {m['მომწოდებელი']} | მარაგი={m['მარაგი მომწოდებელთან']}"
            )
        print()

    if unmatched:
        print("--- არ იძებნება მომწოდებლების ბაზაში ---")
        for u in unmatched:
            print(
                f"  [{u['გამოყენებული SKU']}] {str(u['სახელი'])[:60]}"
                f" | საიტზე მარაგი={u['რაოდენობა']} | აქტიური={u['აქტიური']}"
            )
        print()

    if no_sku:
        print("--- SKU ვერ გამოიცნო (შიდა კოდი ცარიელი + აღწერიდან ვერ ამოვიღეთ) ---")
        for u in no_sku:
            print(f"  {str(u['სახელი'])[:65]} | მარაგი={u['რაოდენობა']}")
        print()

    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    pd.DataFrame(unmatched).to_csv(
        out_dir / "site_monitors_unmatched.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(matched).to_csv(
        out_dir / "site_monitors_matched.csv", index=False, encoding="utf-8-sig"
    )
    print(f"CSV: {out_dir / 'site_monitors_unmatched.csv'}")


if __name__ == "__main__":
    main()
