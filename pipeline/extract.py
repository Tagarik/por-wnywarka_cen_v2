"""Warstwa RAW: pobranie danych z API i zapis bez zmian do data/raw/<znacznik_czasu>/."""
import json
from datetime import datetime
from pathlib import Path

import requests

from pipeline import config


def _get_json(url: str, **kwargs) -> dict:
    resp = requests.get(url, timeout=config.REQUEST_TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


def fetch_cs2prices(currency: str) -> dict:
    if not config.CS2PRICES_API_KEY:
        raise RuntimeError("Brak CS2PRICES_API_KEY - skopiuj .env.example do .env i uzupełnij klucz.")
    return _get_json(
        config.CS2PRICES_URL,
        params={"currency": currency},
        headers={"x-api-key": config.CS2PRICES_API_KEY},
    )


def fetch_nbp_rate(code: str) -> dict:
    return _get_json(config.NBP_RATE_URL.format(code=code))


def run() -> Path:
    """Pobiera wszystkie źródła i zapisuje je do nowego katalogu raw. Zwraca ścieżkę katalogu."""
    run_dir = config.RAW_DIR / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Ceny pobieramy tylko w USD (jeden spójny zrzut rynku); EUR i PLN liczymy z kursów NBP.
    sources = {
        "cs2prices_usd.json": lambda: fetch_cs2prices("usd"),
        "nbp_usd.json": lambda: fetch_nbp_rate("usd"),
        "nbp_eur.json": lambda: fetch_nbp_rate("eur"),
    }
    for filename, fetch in sources.items():
        print(f"  pobieram {filename} ...")
        data = fetch()
        (run_dir / filename).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    return run_dir


def latest_run_dir() -> Path:
    runs = sorted(p for p in config.RAW_DIR.glob("*") if p.is_dir())
    if not runs:
        raise RuntimeError("Brak danych w data/raw - uruchom najpierw pobieranie.")
    return runs[-1]
