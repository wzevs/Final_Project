import pandas as pd

from database.database_manager import DatabaseManager
from utils.sku_utils import (
    STORERA_ALT_CODE_COLUMN,
    STORERA_CODE_COLUMN,
    is_empty_code,
    normalize_distributor_code,
    normalize_sku,
)

ACTIVE_COLUMN = "აქტიური"
PC_BUILD_CATEGORIES = frozenset({"სათამაშო/სარენდერო", "პრემიალური", "საოფისე"})
VRTX_DISTRIBUTOR = "VRTX"


def _parse_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _active_from_quantity(qty: int) -> int:
    """Storera: მარაგი 0 → საიტზე არ ჩანს (აქტიური=0), ადმინში რჩება."""
    return 1 if qty > 0 else 0


class StoreraService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _build_sku_index(self, supplier_df: pd.DataFrame) -> dict[str, list]:
        """SKU → მომწოდებლის ჩანაწერების სია."""
        index: dict[str, list] = {}
        for _, row in supplier_df.iterrows():
            key = normalize_sku(row.get("SKU", ""))
            if not key:
                continue
            index.setdefault(key, []).append(row)
        for key in index:
            index[key].sort(key=lambda r: (r["ფასი (₾)"], -int(r["რაოდენობა"])))
        return index

    def _build_vrtx_code_index(self, supplier_df: pd.DataFrame) -> dict[str, list]:
        """VRTX vrtx_code → ჩანაწერები."""
        index: dict[str, list] = {}
        vrtx_rows = supplier_df[supplier_df["მომწოდებელი"] == VRTX_DISTRIBUTOR]
        for _, row in vrtx_rows.iterrows():
            key = normalize_distributor_code(row.get("მომწოდებლის კოდი", ""))
            if not key:
                continue
            index.setdefault(key, []).append(row)
        for key in index:
            index[key].sort(key=lambda r: (r["ფასი (₾)"], -int(r["რაოდენობა"])))
        return index

    def _pick_best_supplier_row(self, rows: list) -> pd.Series:
        in_stock = [r for r in rows if int(r["რაოდენობა"]) > 0]
        return in_stock[0] if in_stock else rows[0]

    def find_by_sku(self, storera_sku: str, sku_index: dict[str, list]) -> pd.Series | None:
        key = normalize_sku(storera_sku)
        if not key or key not in sku_index:
            return None
        return self._pick_best_supplier_row(sku_index[key])

    def find_by_vrtx_code(
        self, alt_code: str, vrtx_code_index: dict[str, list]
    ) -> pd.Series | None:
        key = normalize_distributor_code(alt_code)
        if not key or key not in vrtx_code_index:
            return None
        return self._pick_best_supplier_row(vrtx_code_index[key])

    def _find_supplier_match(
        self,
        storera_sku,
        alt_code,
        sku_index: dict[str, list],
        vrtx_code_index: dict[str, list],
    ) -> tuple[pd.Series | None, str | None]:
        """1C/FINA/FMG ↔ VRTX (თუ ემთხვევა), შემდეგ შიდა კოდი ↔ SKU."""
        if not is_empty_code(alt_code):
            vrtx_match = self.find_by_vrtx_code(alt_code, vrtx_code_index)
            if vrtx_match is not None:
                return vrtx_match, "VRTX კოდი"

        if not is_empty_code(storera_sku):
            match = self.find_by_sku(storera_sku, sku_index)
            if match is not None:
                return match, "SKU"

        return None, None

    def _prepare_storera_df(self, storera_df: pd.DataFrame) -> pd.DataFrame:
        df = storera_df.copy()
        if ACTIVE_COLUMN not in df.columns:
            df[ACTIVE_COLUMN] = 1
        df[ACTIVE_COLUMN] = df[ACTIVE_COLUMN].map(lambda v: _parse_int(v, 1))
        return df

    def _sync_active_with_quantity(self, df: pd.DataFrame) -> pd.DataFrame:
        """მარაგი ↔ აქტიური: 0 → გამორთული, >0 → ჩართული (PC build-ის გარდა)."""
        for index, row in df.iterrows():
            category = str(row.get("კატეგორია", "")).strip()
            if category in PC_BUILD_CATEGORIES:
                continue
            qty = _parse_int(row.get("რაოდენობა"), 0)
            df.at[index, ACTIVE_COLUMN] = _active_from_quantity(qty)
        return df

    @staticmethod
    def _change_status(orig_qty: int, new_qty: int, orig_active: int, new_active: int) -> str:
        if new_qty == 0 and (orig_qty > 0 or orig_active == 1):
            return "❌ გათიშა (მარაგი 0)"
        if new_qty > 0 and orig_qty == 0:
            return "✅ ჩაირთო (მარაგი დაემატა)"
        if orig_active != new_active:
            return "🔄 აქტიურობა შეიცვალა"
        return "🔄 განახლდა"

    def process_storera_feed(
        self, storera_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """მარაგის განახლება: SKU → შემდეგ 1C/FINA/FMG ↔ VRTX კოდი."""
        db_df = self.db_manager.fetch_products_dataframe()
        if db_df.empty:
            return self._sync_active_with_quantity(self._prepare_storera_df(storera_df)), pd.DataFrame(), pd.DataFrame()

        sku_index = self._build_sku_index(db_df)
        vrtx_code_index = self._build_vrtx_code_index(db_df)
        updated_storera = self._prepare_storera_df(storera_df)
        change_logs = []
        unmatched_logs = []

        for index, row in updated_storera.iterrows():
            current_category = str(row.get("კატეგორია", "")).strip()
            if current_category in PC_BUILD_CATEGORIES:
                continue

            product_name = row.get("სახელი", "")
            storera_sku = row.get(STORERA_CODE_COLUMN, "")
            alt_code = row.get(STORERA_ALT_CODE_COLUMN, "")
            orig_qty = _parse_int(row.get("რაოდენობა"), 0)
            orig_active = _parse_int(row.get(ACTIVE_COLUMN), 1)

            if is_empty_code(storera_sku) and is_empty_code(alt_code):
                unmatched_logs.append({
                    "პროდუქტი": product_name,
                    "კატეგორია": current_category,
                    "შიდა კოდი": "",
                    "1C / FINA / FMG": "",
                    "მიზეზი": "შიდა კოდი და 1C ველი ცარიელია",
                })
                continue

            match, match_method = self._find_supplier_match(
                storera_sku, alt_code, sku_index, vrtx_code_index
            )
            if match is None:
                unmatched_logs.append({
                    "პროდუქტი": product_name,
                    "კატეგორია": current_category,
                    "შიდა კოდი": str(storera_sku).strip() if not is_empty_code(storera_sku) else "",
                    "1C / FINA / FMG": str(alt_code).strip() if not is_empty_code(alt_code) else "",
                    "მიზეზი": "მომწოდებლებში ვერ მოიძებნა (არც SKU, არც VRTX კოდი)",
                })
                continue

            new_qty = _parse_int(match["რაოდენობა"], 0)
            new_active = _active_from_quantity(new_qty)

            updated_storera.at[index, "რაოდენობა"] = new_qty
            updated_storera.at[index, ACTIVE_COLUMN] = new_active

            if orig_qty != new_qty or orig_active != new_active:
                change_logs.append({
                    "პროდუქტი": product_name,
                    "შიდა კოდი": str(storera_sku).strip() if not is_empty_code(storera_sku) else "",
                    "1C / FINA / FMG": str(alt_code).strip() if not is_empty_code(alt_code) else "",
                    "მეჩინგი": match_method,
                    "კატეგორია": current_category,
                    "მომწოდებელი": match["მომწოდებელი"],
                    "ძველი მარაგი": orig_qty,
                    "ახალი მარაგი": new_qty,
                    "ძველი აქტიური": orig_active,
                    "ახალი აქტიური": new_active,
                    "სტატუსი": self._change_status(orig_qty, new_qty, orig_active, new_active),
                })

        updated_storera = self._sync_active_with_quantity(updated_storera)
        return updated_storera, pd.DataFrame(change_logs), pd.DataFrame(unmatched_logs)
