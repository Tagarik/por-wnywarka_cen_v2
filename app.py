"""Porównywarka cen przedmiotów CS2. Uruchom: streamlit run app.py

Aplikacja czyta wyłącznie warstwę GOLD (wynik ostatniego poprawnego uruchomienia potoku).
"""
import html
import math
import re
from urllib.parse import quote

import pandas as pd
import streamlit as st

from pipeline import config, transform

st.set_page_config(page_title="Porównywarka cen CS2", layout="wide")

CURRENCIES = {"USD": "$", "EUR": "€", "PLN": "zł"}
# nazwa wyświetlana, kolor ikony, litera ikony
MARKETS = {
    "csfloat": ("CSFloat", "#27272a", "f"),
    "marketcsgo": ("Market.CSGO", "#1d8fd8", "M"),
    "csgoroll": ("CSGORoll", "#c0392b", "R"),
    "buff163": ("Buff163", "#27272a", "B"),
    "youpin": ("YouPin", "#e0a800", "Y"),
}
WEAR_SHORT = {"Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT",
              "Well-Worn": "WW", "Battle-Scarred": "BS"}
SORTS = {
    "Popularność": ("total_listings", False),
    "Cena: rosnąco": ("min_price_usd", True),
    "Cena: malejąco": ("min_price_usd", False),
    "Różnica cen między rynkami": ("spread_pct", False),
    "Nazwa": ("item_name", True),
}
PAGE_SIZE = 50

st.markdown("""
<style>
  .block-container {padding-top: 2rem;}
  .section {font-family: ui-monospace, monospace; font-size: .72rem; letter-spacing: .12em;
            color: #8b8b93; text-transform: uppercase; margin: .4rem 0 .2rem;}
  .count {font-size: 1rem; color: #e7e7e7; letter-spacing: 0; text-transform: none; margin-left: .6rem;}
  [class*="st-key-row_"] {border-bottom: 1px solid #222226; padding: .7rem 0; gap: 0;}
  [class*="st-key-row_"] [data-testid="stVerticalBlock"] {gap: .35rem;}
  /* Streamlit daje blokom markdown ujemny margines dolny -> treść wystawała poza wiersz */
  [class*="st-key-row_"] [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
  [class*="st-key-row_"] [data-testid="stMarkdownContainer"] p {margin: 0;}
  [class*="st-key-name_"] button {padding: 0; min-height: 0; justify-content: flex-start;}
  [class*="st-key-name_"] button:focus, [class*="st-key-name_"] button:focus-visible {outline: none; box-shadow: none;}
  [class*="st-key-name_"] button p {font-weight: 600; font-size: 1rem; color: #f4f4f5; text-align: left;}
  [class*="st-key-name_"] button:hover p {text-decoration: underline;}
  .badge {display: inline-block; font-family: ui-monospace, monospace; font-size: .7rem; font-weight: 600;
          padding: 1px 6px; border-radius: 4px; background: #27272a; color: #d4d4d8; margin-right: 4px;}
  .badge.st {color: #f08a24;} .badge.sv {color: #f5c518;} .badge.other {color: #8b8b93;}
  .price {text-align: right; line-height: 1.3;}
  .price b {font-size: 1.05rem;} .price span {color: #71717a; font-size: .85rem;}
  .market {line-height: 1.3;} .market span {color: #71717a; font-size: .85rem; margin-left: 1.6rem;}
  .thumb {width: 64px; height: 48px; object-fit: contain; display: block;}
  .dlg-head {display: flex; align-items: center; gap: .8rem; margin-bottom: .4rem;}
  .dlg-head img {width: 96px; aspect-ratio: 4 / 3; object-fit: contain;}
  [class*="st-key-card_"][class*="_best"] {border-color: #22c55e !important;}
  .card-head {display: flex; justify-content: space-between; align-items: center; font-weight: 600;
              font-size: .9rem;}
  .tag {font-size: .7rem; color: #8b8b93;}
  .tag.best {background: #14532d; color: #4ade80; padding: 1px 6px; border-radius: 4px;}
  .card-price {font-size: 1.5rem; font-weight: 700; margin-top: .5rem;}
  .card-alt {color: #71717a; font-size: .8rem; padding-bottom: .6rem; border-bottom: 1px solid #27272a;}
  .card-row {display: flex; justify-content: space-between; color: #a1a1aa; font-size: .85rem;
             margin: .6rem 0 .3rem;}
  .icon {display: inline-flex; width: 18px; height: 18px; border-radius: 4px; align-items: center;
         justify-content: center; font-size: .7rem; font-weight: 700; color: #fff; margin-right: 6px;}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(version: float):  # version = czas zapisu data/gold; nowy przebieg potoku unieważnia cache
    t = transform.load(config.GOLD_DIR, ["item_summary", "item_prices", "fx_rate"])
    run = (config.GOLD_DIR / "source_run.txt").read_text(encoding="utf-8")
    return t["item_summary"], t["item_prices"], t["fx_rate"], run


@st.cache_data
def summarize(markets: tuple, version: float) -> pd.DataFrame:
    """Najniższa cena i najtańszy rynek liczone tylko z wybranych rynków."""
    p = prices[prices["market"].isin(markets)]
    best = p.loc[p.groupby("item_name")["price_usd"].idxmin(), ["item_name", "market"]]
    agg = p.groupby("item_name").agg(min_price_usd=("price_usd", "min"), max_price_usd=("price_usd", "max"),
                                      markets_count=("market", "nunique"),
                                      total_listings=("listing_count", "sum")).reset_index()
    agg["spread_pct"] = ((agg["max_price_usd"] / agg["min_price_usd"] - 1) * 100).round(1)
    items = summary.drop(columns=["min_price_usd", "max_price_usd", "markets_count",
                                  "total_listings", "spread_pct", "best_market"])
    return items.merge(agg, on="item_name").merge(best.rename(columns={"market": "best_market"}), on="item_name")


def section(title: str) -> None:
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)


def market_icon(market: str) -> str:
    name, color, letter = MARKETS.get(market, (market, "#3f3f46", market[0].upper()))
    return f'<span class="icon" style="background:{color}">{letter}</span>{name}'


def icon_url(item: str) -> str:
    """Ikona z CDN cs2prices: nazwa małymi literami, ciągi znaków spoza [a-z0-9] -> '-'.
    Np. '★ StatTrak™ Karambit | Tiger Tooth (Factory New)' -> 'stattrak-karambit-tiger-tooth-factory-new'."""
    return f"https://cdn.cs2prices.net/icons/{re.sub(r'[^a-z0-9]+', '-', item.lower()).strip('-')}.png"


def fmt(value: float, sym: str) -> str:
    s = f"{value:,.2f}".replace(",", " ")
    return f"{s} zł" if sym == "zł" else f"{sym}{s}"


if not (config.GOLD_DIR / "item_summary.parquet").exists():
    st.error("Brak danych. Uruchom najpierw: `python run_pipeline.py`")
    st.stop()

data_version = (config.GOLD_DIR / "item_summary.parquet").stat().st_mtime
summary, prices, fx, run = load_data(data_version)
usd_pln = fx.set_index("currency").at["USD", "pln_per_unit"]
eur_pln = fx.set_index("currency").at["EUR", "pln_per_unit"]

# --- Filtry -----------------------------------------------------------------
with st.sidebar:
    section("Waluta")
    currency = st.segmented_control("Waluta", list(CURRENCIES), default="USD",
                                    label_visibility="collapsed") or "USD"
    factor = {"USD": 1.0, "PLN": usd_pln, "EUR": usd_pln / eur_pln}[currency]
    sym = CURRENCIES[currency]

    section("Rynki")
    markets = tuple(m for m, (label, _, _) in MARKETS.items() if st.checkbox(label, value=True, key=f"mk_{m}"))

    section("Cena")
    c1, c2 = st.columns(2)
    price_min = c1.number_input("Min", min_value=0.0, value=None, placeholder=f"{sym} Min",
                                label_visibility="collapsed")
    price_max = c2.number_input("Max", min_value=0.0, value=None, placeholder=f"{sym} Max",
                                label_visibility="collapsed")

    section("Stan zużycia")
    wears = st.pills("Stan zużycia", list(WEAR_SHORT.values()), selection_mode="multi",
                     label_visibility="collapsed")

    section("Jakość")
    st.markdown('<span style="color:#f08a24;font-weight:600">StatTrak™</span>', unsafe_allow_html=True)
    stattrak = st.segmented_control("StatTrak", ["Dowolne", "Tylko", "Bez"], default="Dowolne",
                                    key="st", label_visibility="collapsed") or "Dowolne"
    st.markdown('<span style="color:#f5c518;font-weight:600">Souvenir</span>', unsafe_allow_html=True)
    souvenir = st.segmented_control("Souvenir", ["Dowolne", "Tylko", "Bez"], default="Dowolne",
                                    key="sv", label_visibility="collapsed") or "Dowolne"

    section("Kategoria")
    category = st.segmented_control("Kategoria", ["Wszystkie", "Broń", "Inne"], default="Wszystkie",
                                    label_visibility="collapsed") or "Wszystkie"

    st.caption(f"Dane z: {run}  \nKurs NBP ({fx['effective_date'].iloc[0]}): "
               f"1 USD = {usd_pln:.4f} PLN, 1 EUR = {eur_pln:.4f} PLN")

# --- Filtrowanie ---------------------------------------------------------------
query = st.text_input("Szukaj", placeholder="Szukaj po nazwie, np. AK-47 Redline", label_visibility="collapsed")

if not markets:
    st.info("Zaznacz co najmniej jeden rynek.")
    st.stop()

df = summarize(markets, data_version)
for word in query.lower().split():
    df = df[df["item_name"].str.lower().str.contains(word, regex=False)]
if category != "Wszystkie":
    df = df[df["category"] == category]
if wears:
    df = df[df["wear"].map(WEAR_SHORT).isin(wears)]
sc = df["special_condition"].fillna("")
for choice, word in [(stattrak, "StatTrak"), (souvenir, "Souvenir")]:
    if choice == "Tylko":
        df, sc = df[sc.str.contains(word)], sc[sc.str.contains(word)]
    elif choice == "Bez":
        df, sc = df[~sc.str.contains(word)], sc[~sc.str.contains(word)]
if price_min is not None:
    df = df[df["min_price_usd"] * factor >= price_min]
if price_max is not None:
    df = df[df["min_price_usd"] * factor <= price_max]

# --- Nagłówek wyników --------------------------------------------------------
h1, h2 = st.columns([3, 1], vertical_alignment="center")
h1.markdown(f'<div class="section">Wyniki<span class="count">{len(df):,} przedmiotów</span></div>'
            .replace(",", " "), unsafe_allow_html=True)
sort = h2.selectbox("Sortuj", list(SORTS), label_visibility="collapsed")
col, asc = SORTS[sort]
df = df.sort_values(col, ascending=asc)

pages = max(1, math.ceil(len(df) / PAGE_SIZE))
signature = (query, markets, price_min, price_max, tuple(wears), stattrak, souvenir, category, sort)
if st.session_state.get("signature") != signature:  # nowe filtry -> wracamy na 1. stronę
    st.session_state.signature, st.session_state.page = signature, 1
page = st.session_state.page = min(st.session_state.get("page", 1), pages)


# --- Szczegóły przedmiotu ------------------------------------------------------
def market_url(market: str, item: str, wear) -> str | None:
    """Link do ofert przedmiotu na rynku. YouPin wymaga wewnętrznego ID, którego nie mamy -> brak linku."""
    q = quote(item, safe="()")
    if market == "csfloat":
        return f"https://csfloat.com/search?sort_by=lowest_price&type=buy_now&market_hash_name={q}"
    if market == "marketcsgo":
        url = f"https://market.csgo.com/en/?search={q}"
        return url + f"&quality={quote(wear)}" if isinstance(wear, str) else url
    if market == "csgoroll":
        return f"https://www.csgoroll.com/trade/market/?marketName={q}"
    if market == "buff163":  # wyszukiwarka Buff (wymaga zalogowania)
        return f"https://buff.163.com/market/csgo#game=csgo&page_num=1&search={q}"
    return None


@st.dialog("Porównanie rynków", width="large")
def show_details(item: str) -> None:
    pcol = f"price_{currency.lower()}"
    alt_cur = "USD" if currency == "PLN" else "PLN"
    alt_col, alt_sym = f"price_{alt_cur.lower()}", CURRENCIES[alt_cur]
    d = prices[(prices["item_name"] == item) & prices["market"].isin(markets)].sort_values(pcol)
    wear = summary.loc[summary["item_name"] == item, "wear"].iloc[0]
    cheapest = d[pcol].min()

    st.markdown(f'<div class="dlg-head"><img src="{icon_url(item)}" alt="">'
                f'<b>{html.escape(item)}</b></div>', unsafe_allow_html=True)
    for col, r in zip(st.columns(len(d)), d.itertuples()):
        price = getattr(r, pcol)
        is_best = price == cheapest
        tag = ('<span class="tag best">Najniżej</span>' if is_best
               else f'<span class="tag">+{(price / cheapest - 1) * 100:.1f}%</span>')
        with col.container(border=True, key=f"card_{r.market}{'_best' if is_best else ''}"):
            st.markdown(
                f'<div class="card-head">{market_icon(r.market)}{tag}</div>'
                f'<div class="card-price">{fmt(price, sym)}</div>'
                f'<div class="card-alt">{fmt(getattr(r, alt_col), alt_sym)}</div>'
                f'<div class="card-row"><span>Oferty</span><span>{r.listing_count}</span></div>',
                unsafe_allow_html=True)
            url = market_url(r.market, item, wear)
            if url:
                st.link_button("Zobacz oferty ↗", url, use_container_width=True)
            else:
                st.button("Brak linku", key=f"nolink_{r.market}", disabled=True, use_container_width=True,
                          help="Ten rynek identyfikuje przedmioty wewnętrznym ID, którego API nie udostępnia.")


# --- Lista wyników -------------------------------------------------------------
COLS = [0.9, 6, 2, 2]
_, c1, c2, c3 = st.columns(COLS)
for c, label, align in [(c1, "Przedmiot", "left"), (c2, "Najniższa cena", "right"), (c3, "Najtańszy rynek", "left")]:
    c.markdown(f'<div class="section" style="text-align:{align}">{label}</div>', unsafe_allow_html=True)

for i, r in enumerate(df.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE].itertuples()):
    with st.container(key=f"row_{i}"):
        c0, c1, c2, c3 = st.columns(COLS, vertical_alignment="center")
        c0.markdown(f'<img class="thumb" src="{icon_url(r.item_name)}" alt="" loading="lazy">',
                    unsafe_allow_html=True)
        with c1:
            if st.button(r.item_name, key=f"name_{i}", type="tertiary"):
                show_details(r.item_name)
            special = r.special_condition if isinstance(r.special_condition, str) else ""
            badges = ""
            if "StatTrak" in special:
                badges += '<span class="badge st">ST</span>'
            if "Souvenir" in special:
                badges += '<span class="badge sv">SV</span>'
            if isinstance(r.wear, str):
                badges += f'<span class="badge">{WEAR_SHORT[r.wear]}</span>'
            if r.category == "Inne":
                badges += '<span class="badge other">INNE</span>'
            st.markdown(badges, unsafe_allow_html=True)
        spread = (f'<span>do {fmt(r.max_price_usd * factor, sym)}</span>'
                  if r.markets_count > 1 else '<span>jedyna oferta</span>')
        c2.markdown(f'<div class="price"><b>{fmt(r.min_price_usd * factor, sym)}</b><br>{spread}</div>',
                    unsafe_allow_html=True)
        c3.markdown(f'<div class="market">{market_icon(r.best_market)}<br>'
                    f'<span>najtaniej z {r.markets_count}</span></div>', unsafe_allow_html=True)

if pages > 1:
    _, mid, _ = st.columns([2, 1, 2])
    mid.number_input(f"Strona (z {pages})", min_value=1, max_value=pages, key="page")
