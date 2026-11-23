"""Uruchomienie całego potoku: pobranie -> silver -> gold -> testy jakości.

Użycie:
    python run_pipeline.py              # pobiera świeże dane z API
    python run_pipeline.py --no-fetch   # przetwarza ostatni zapisany katalog raw
"""
import sys

from pipeline import config, extract, quality, transform


def main() -> int:
    if "--no-fetch" in sys.argv:
        raw_dir = extract.latest_run_dir()
        print(f"1/4 RAW: używam {raw_dir.name}")
    else:
        print("1/4 RAW: pobieranie z API")
        raw_dir = extract.run()

    print("2/4 SILVER: czyszczenie i parsowanie nazw")
    silver = transform.build_silver(raw_dir)

    print("3/4 GOLD: budowa tabel dla aplikacji")
    gold = transform.build_gold(silver)
    tables = {**gold, "fx_rate": silver["fx_rate"]}

    print("4/4 Testy jakości danych")
    if not quality.run_all(tables):
        print("\nTesty jakości NIE przeszły - dane nie zostały opublikowane do data/gold.")
        return 1

    transform.save(silver, config.SILVER_DIR)
    transform.save(tables, config.GOLD_DIR)
    (config.GOLD_DIR / "source_run.txt").write_text(raw_dir.name, encoding="utf-8")
    print(f"\nOK: {len(gold['item_summary'])} przedmiotów, {len(gold['item_prices'])} ofert -> data/gold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
