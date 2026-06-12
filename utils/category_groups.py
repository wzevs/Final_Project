"""კატეგორიების ზედა დონის ჯგუფები — config/category_groups.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "category_groups.json"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_group_definitions() -> list[dict]:
    """ჯგუფების სია order-ის მიხედვით."""
    cfg = _load_config()
    return sorted(cfg["groups"], key=lambda g: g.get("order", 50))


def get_fallback_group() -> str:
    return _load_config().get("fallback", "სხვა")


@lru_cache(maxsize=1)
def _build_exact_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group in get_group_definitions():
        label = group["label"]
        for cat in group.get("categories", []):
            mapping[str(cat).strip()] = label
    return mapping


@lru_cache(maxsize=1)
def _build_keyword_rules() -> list[tuple[str, tuple[str, ...]]]:
    rules: list[tuple[str, tuple[str, ...]]] = []
    for group in get_group_definitions():
        keywords = tuple(k.lower() for k in group.get("keywords", []) if k)
        if keywords:
            rules.append((group["label"], keywords))
    return rules


def resolve_category_group(
    category: str,
    distributor: str | None = None,
) -> str:
    """მშობელი ჯგუფი კონკრეტული კატეგორიისთვის."""
    if distributor and str(distributor).strip().upper() == "YVERSY":
        return "Yversy"

    raw = str(category or "").strip()
    if not raw:
        return get_fallback_group()

    exact = _build_exact_map()
    if raw in exact:
        return exact[raw]

    lower = raw.lower()
    for label, keywords in _build_keyword_rules():
        if any(kw in lower for kw in keywords):
            return label

    return get_fallback_group()


def add_group_column(
    df: pd.DataFrame,
    category_col: str = "კატეგორია",
    distributor_col: str = "მომწოდებელი",
) -> pd.DataFrame:
    """DataFrame-ს უმატებს 'ჯგუფი' სვეტს."""
    if df.empty or category_col not in df.columns:
        return df
    out = df.copy()
    if distributor_col in out.columns:
        out["ჯგუფი"] = out.apply(
            lambda row: resolve_category_group(
                row.get(category_col, ""),
                row.get(distributor_col, ""),
            ),
            axis=1,
        )
    else:
        out["ჯგუფი"] = out[category_col].map(resolve_category_group)
    return out


def groups_for_categories(categories: list[str]) -> dict[str, list[str]]:
    """ჯგუფი → კატეგორიების სია (მხოლოდ მოცემული კატეგორიებიდან)."""
    result: dict[str, list[str]] = {}
    for cat in categories:
        group = resolve_category_group(cat)
        result.setdefault(group, []).append(cat)
    for group in result:
        result[group] = sorted(result[group])
    return result


def expand_enabled_groups(
    enabled_groups: list[str],
    available_categories: list[str],
) -> list[str]:
    """ჩართული ჯგუფები → ფილტრისთვის ბაზის კატეგორიების სია."""
    if not enabled_groups:
        return []

    grouped = groups_for_categories(available_categories)
    enabled: list[str] = []
    for group in enabled_groups:
        enabled.extend(grouped.get(group, []))
    return sorted(set(enabled))
