"""Transformacje RAW -> SILVER -> GOLD.

SILVER:
  items.parquet   - jeden wiersz na przedmiot, nazwa rozbita wg szablonu
                    "<special condition> <weapon> | <skin> (<wear>)"
  prices.parquet  - jeden wiersz na (przedmiot, rynek), ceny w USD (z API) oraz EUR/PLN (przeliczone)
  fx_rate.parquet - kursy średnie NBP (USD, EUR -> PLN) użyte do przeliczenia

GOLD:
  item_summary.parquet - przedmiot + najniższa/najwyższa cena, najtańszy rynek, rozrzut cen
  item_prices.parquet  - ceny przedmiotu na każdym rynku (do widoku szczegółów)
"""
import json
import re
from pathlib import Path

import pandas as pd

from pipeline import config

# Przedmiot traktujemy jako broń (w tym noże i rękawice), gdy ma stan zużycia
# albo jest "gołym" nożem/rękawicami (np. "★ Bayonet"). Reszta to "Inne".
NAME_RE = re.compile(
    r"^(?P<special>(?:★ )?(?:StatTrak™ |Souvenir )?)"
    r"(?P<weapon>[^|]+?)"
    r"(?: \| (?P<skin>.+?))?"
    r"(?: \((?P<wear>" + "|".join(config.WEARS) + r")\))?"
    r"(?: - (?P<phase>.+))?$"
)


def parse_name(name: str) -> dict:
    """Rozbija nazwę przedmiotu na części. Dla kategorii 'Inne' pola broni są puste."""
    empty = {"category": "Inne", "special_condition": None, "weapon": None,
             "skin": None, "wear": None, "phase": None}
    m = NAME_RE.match(name)
    if not m:
        return empty
    is_weapon = m["wear"] is not None or (name.startswith("★") and m["skin"] is None)
    if not is_weapon:
        return empty
    return {
        "category": "Broń",
        "special_condition": m["special"].strip() or None,
        "weapon": m["weapon"].strip(),
        "skin": m["skin"],
        "wear": m["wear"],
        "phase": m["phase"],
    }


def _prices_long(raw: dict, currency: str) -> pd.DataFrame:
    """Spłaszcza {"items": {nazwa: {rynek: {price, listing_count}}}} do tabeli. Cena z API jest w centach."""
    rows = [
        {"item_name": name, "market": market,
         f"price_{currency}": offer["price"] / 100, "listing_count": offer["listing_count"]}
        for name, markets in raw["items"].items()
        for market, offer in markets.items()
    ]
    return pd.DataFrame(rows)


def build_silver(raw_dir: Path) -> dict[str, pd.DataFrame]:
    def read(name):
        return json.loads((raw_dir / name).read_text(encoding="utf-8"))

    usd_raw = read("cs2prices_usd.json")
    fx = pd.DataFrame([
        {"currency": r["code"], "pln_per_unit": r["rates"][0]["mid"],
         "effective_date": r["rates"][0]["effectiveDate"], "table_no": r["rates"][0]["no"]}
        for r in (read("nbp_usd.json"), read("nbp_eur.json"))
    ])
    usd_pln = fx.set_index("currency").at["USD", "pln_per_unit"]
    eur_pln = fx.set_index("currency").at["EUR", "pln_per_unit"]

    prices = _prices_long(usd_raw, "usd")
    prices["price_pln"] = (prices["price_usd"] * usd_pln).round(2)
    prices["price_eur"] = (prices["price_usd"] * usd_pln / eur_pln).round(2)

    items = pd.DataFrame([{"item_name": n, **parse_name(n)} for n in usd_raw["items"]])

    return {"items": items, "prices": prices, "fx_rate": fx}


def build_gold(silver: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    prices, items = silver["prices"], silver["items"]

    cheapest = prices.loc[prices.groupby("item_name")["price_usd"].idxmin(), ["item_name", "market"]]
    agg = prices.groupby("item_name").agg(
        min_price_usd=("price_usd", "min"),
        max_price_usd=("price_usd", "max"),
        markets_count=("market", "nunique"),
        total_listings=("listing_count", "sum"),
    ).reset_index()
    agg["spread_pct"] = ((agg["max_price_usd"] / agg["min_price_usd"] - 1) * 100).round(1)

    summary = (items.merge(agg, on="item_name", how="inner")
                    .merge(cheapest.rename(columns={"market": "best_market"}), on="item_name"))

    return {"item_summary": summary, "item_prices": prices}


def save(tables: dict[str, pd.DataFrame], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(target / f"{name}.parquet", index=False)


def load(source: Path, names: list[str]) -> dict[str, pd.DataFrame]:
    return {n: pd.read_parquet(source / f"{n}.parquet") for n in names}
