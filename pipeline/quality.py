"""Testy jakości danych. Każdy test zwraca listę błędów (pusta lista = OK).

Rodzaje reguł: unikalność, kompletność, dozwolone wartości, zakresy,
integralność referencyjna, reguły dziedzinowe.
"""
import pandas as pd

from pipeline import config


def check_unique_item_market(t) -> list[str]:
    """Unikalność: para (przedmiot, rynek) występuje raz."""
    dup = t["item_prices"].duplicated(["item_name", "market"]).sum()
    return [f"{dup} zduplikowanych par (item_name, market)"] if dup else []


def check_unique_item(t) -> list[str]:
    """Unikalność: przedmiot występuje raz w podsumowaniu."""
    dup = t["item_summary"]["item_name"].duplicated().sum()
    return [f"{dup} zduplikowanych przedmiotów w item_summary"] if dup else []


def check_completeness(t) -> list[str]:
    """Kompletność: kluczowe kolumny nie mają braków."""
    errors = []
    for col in ["item_name", "market", "price_usd", "price_eur", "price_pln"]:
        n = t["item_prices"][col].isna().sum()
        if n:
            errors.append(f"item_prices.{col}: {n} pustych wartości")
    weapons = t["item_summary"].query("category == 'Broń'")
    n = weapons["weapon"].isna().sum()
    if n:
        errors.append(f"{n} broni bez nazwy broni")
    return errors


def check_allowed_values(t) -> list[str]:
    """Dozwolone wartości: rynek, kategoria, stan zużycia."""
    errors = []
    bad = set(t["item_prices"]["market"]) - config.MARKETS
    if bad:
        errors.append(f"nieznane rynki: {bad}")
    bad = set(t["item_summary"]["category"]) - config.CATEGORIES
    if bad:
        errors.append(f"nieznane kategorie: {bad}")
    bad = set(t["item_summary"]["wear"].dropna()) - set(config.WEARS)
    if bad:
        errors.append(f"nieznane stany zużycia: {bad}")
    return errors


def check_price_range(t) -> list[str]:
    """Zakres: ceny dodatnie, kursy NBP (USD, EUR) w rozsądnym przedziale."""
    errors = []
    p = t["item_prices"]
    for col in ["price_usd", "price_eur", "price_pln"]:
        n = (p[col] <= 0).sum()
        if n:
            errors.append(f"{col}: {n} cen <= 0")
    fx = t["fx_rate"]
    if set(fx["currency"]) != {"USD", "EUR"}:
        errors.append(f"brak kursu NBP, są tylko: {set(fx['currency'])}")
    for _, r in fx.iterrows():
        if not 2 <= r["pln_per_unit"] <= 8:
            errors.append(f"podejrzany kurs {r['currency']}/PLN: {r['pln_per_unit']}")
    return errors


def check_referential_integrity(t) -> list[str]:
    """Integralność referencyjna: każda cena wskazuje na istniejący przedmiot."""
    missing = set(t["item_prices"]["item_name"]) - set(t["item_summary"]["item_name"])
    return [f"{len(missing)} cen bez przedmiotu w item_summary"] if missing else []


def check_domain_rules(t) -> list[str]:
    """Reguły dziedzinowe: min <= max, najtańszy rynek ma cenę minimalną,
    'Souvenir' i 'StatTrak™' nie występują razem."""
    errors = []
    s = t["item_summary"]
    n = (s["min_price_usd"] > s["max_price_usd"]).sum()
    if n:
        errors.append(f"{n} przedmiotów z min > max")
    best = s.merge(t["item_prices"], left_on=["item_name", "best_market"],
                   right_on=["item_name", "market"])
    n = (best["price_usd"] != best["min_price_usd"]).sum()
    if n:
        errors.append(f"{n} przedmiotów, gdzie best_market nie ma najniższej ceny")
    sc = s["special_condition"].fillna("")
    n = (sc.str.contains("Souvenir") & sc.str.contains("StatTrak")).sum()
    if n:
        errors.append(f"{n} przedmiotów jednocześnie Souvenir i StatTrak™")
    return errors


CHECKS = [
    check_unique_item_market,
    check_unique_item,
    check_completeness,
    check_allowed_values,
    check_price_range,
    check_referential_integrity,
    check_domain_rules,
]


def run_all(tables: dict[str, pd.DataFrame]) -> bool:
    """Uruchamia wszystkie testy, wypisuje wynik. Zwraca True, gdy wszystkie przeszły."""
    ok = True
    for check in CHECKS:
        errors = check(tables)
        status = "PASS" if not errors else "FAIL"
        print(f"  [{status}] {check.__name__}: {check.__doc__.splitlines()[0]}")
        for e in errors:
            print(f"         -> {e}")
        ok = ok and not errors
    return ok
