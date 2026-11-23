"""Wspólna konfiguracja potoku: ścieżki warstw i parametry źródeł."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"        # surowe odpowiedzi API (JSON), jeden katalog na uruchomienie
SILVER_DIR = DATA_DIR / "silver"  # dane oczyszczone, znormalizowane
GOLD_DIR = DATA_DIR / "gold"      # tabele gotowe dla aplikacji

CS2PRICES_URL = "https://api.cs2prices.net/v1/market/prices"
CS2PRICES_API_KEY = os.getenv("CS2PRICES_API_KEY", "")
# Kurs średni NBP (tabela A) - ostatni opublikowany
NBP_RATE_URL = "https://api.nbp.pl/api/exchangerates/rates/a/{code}/?format=json"

REQUEST_TIMEOUT = 60

MARKETS = {"buff163", "youpin", "csfloat", "marketcsgo", "csgoroll"}
WEARS = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
CATEGORIES = {"Broń", "Inne"}
