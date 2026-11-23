"""Testy jednostkowe parsowania nazw przedmiotów."""
import pytest

from pipeline.transform import parse_name


@pytest.mark.parametrize("name, expected", [
    ("AK-47 | Redline (Field-Tested)",
     ("Broń", None, "AK-47", "Redline", "Field-Tested", None)),
    ("StatTrak™ AK-47 | Redline (Minimal Wear)",
     ("Broń", "StatTrak™", "AK-47", "Redline", "Minimal Wear", None)),
    ("Souvenir AWP | Dragon Lore (Factory New)",
     ("Broń", "Souvenir", "AWP", "Dragon Lore", "Factory New", None)),
    ("★ StatTrak™ Survival Knife | Doppler (Factory New) - Sapphire",
     ("Broń", "★ StatTrak™", "Survival Knife", "Doppler", "Factory New", "Sapphire")),
    ("★ Bayonet",
     ("Broń", "★", "Bayonet", None, None, None)),
    ("Sticker | 9INE (Holo) | Paris 2023",
     ("Inne", None, None, None, None, None)),
    ("Souvenir Charm | Austin 2025 Highlight | The Chase",
     ("Inne", None, None, None, None, None)),
    ("2020 RMR Legends",
     ("Inne", None, None, None, None, None)),
])
def test_parse_name(name, expected):
    r = parse_name(name)
    assert (r["category"], r["special_condition"], r["weapon"], r["skin"], r["wear"], r["phase"]) == expected
