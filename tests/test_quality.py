"""Testy jakości danych na ostatnim wyniku potoku (data/gold). Uruchom: pytest"""
import pytest

from pipeline import config, quality, transform


@pytest.fixture(scope="module")
def tables():
    if not (config.GOLD_DIR / "item_summary.parquet").exists():
        pytest.skip("Brak data/gold - uruchom najpierw python run_pipeline.py")
    return transform.load(config.GOLD_DIR, ["item_summary", "item_prices", "fx_rate"])


@pytest.mark.parametrize("check", quality.CHECKS, ids=lambda c: c.__name__)
def test_quality(check, tables):
    errors = check(tables)
    assert not errors, "\n".join(errors)
