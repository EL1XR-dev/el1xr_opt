"""Fetch full-year 2025 SE3 day-ahead spot and Svk FCR capacity prices.

Writes inputs/real_data/year/spot_se3.csv and year/fcr_se.csv, aligned to a clean
8736-hour UTC index (52 weeks from 2025-01-01), so the model can slice a week, a
month, or the whole year from one set of files. DST gaps/duplicates from the source
are reconciled by reindexing onto that clean hourly index.
"""
from pathlib import Path
import pandas as pd
from elptools.power.prices import fetch_day_ahead
from elptools.power.mimer import fetch_fcr_prices

HERE = Path(__file__).resolve().parent
OUT = HERE / "inputs" / "real_data" / "year"
OUT.mkdir(parents=True, exist_ok=True)

# 52 full weeks of 2025 (8736 h), UTC, so weekly/monthly slicing tiles cleanly.
IDX = pd.date_range("2025-01-01T00:00:00Z", periods=8736, freq="h")

def _on_index(df, value_col):
    """Reindex a (datetime_utc, value) frame onto IDX; ffill across DST gaps."""
    s = df.copy()
    s["datetime_utc"] = pd.to_datetime(s["datetime_utc"], utc=True)
    s = s.set_index("datetime_utc")[value_col]
    s = s[~s.index.duplicated(keep="first")].sort_index()
    return s.reindex(IDX).ffill().bfill()

import sys
SKIP_SPOT = "--fcr-only" in sys.argv

# --- spot (ENTSO-E, SE3) ---
if not SKIP_SPOT:
    print("fetching SE3 spot 2025 ...", flush=True)
    spot = fetch_day_ahead("SE3", "2025-01-01", "2025-12-31", resolution="PT60M")
    price_col = "price_eur_mwh" if "price_eur_mwh" in spot.columns else [c for c in spot.columns if "price" in c.lower()][0]
    sp = _on_index(spot.rename(columns={price_col: "price_eur_mwh"}), "price_eur_mwh")
    pd.DataFrame({"datetime_utc": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in IDX],
                 "price_eur_mwh": sp.to_numpy()}).to_csv(OUT / "spot_se3.csv", index=False)
    print(f"  spot: {len(IDX)} h  mean={sp.mean():.1f}  min={sp.min():.1f}  max={sp.max():.1f} EUR/MWh", flush=True)

# --- FCR (Mimer, national clearing; long -> wide) ---
# Mimer's _to_utc cannot disambiguate the autumn DST fall-back (2025-10-26 02:00 is
# ambiguous), so fetch in two ranges split around that day and let the reindex onto
# IDX forward-fill the one skipped day. (Known elptools mimer DST limitation.)
print("fetching FCR 2025 (split around the Oct-26 DST fall-back) ...", flush=True)
fcr = pd.concat([
    fetch_fcr_prices("2025-01-01", "2025-10-25"),
    fetch_fcr_prices("2025-10-27", "2025-12-31"),
], ignore_index=True)
prod_col = "product" if "product" in fcr.columns else [c for c in fcr.columns if "prod" in c.lower()][0]
wide = {}
mapping = {"FCR-N": "fcr_n_eur_mw", "FCR-D-up": "fcr_d_up_eur_mw", "FCR-D-down": "fcr_d_down_eur_mw"}
prods = fcr[prod_col].unique()
print("  FCR products returned:", list(prods), flush=True)
for raw_name, out_col in mapping.items():
    match = [p for p in prods if p.replace(" ", "").lower() == raw_name.replace("-", "").replace(" ", "").lower()
             or p.lower() == raw_name.lower()]
    sub = fcr[fcr[prod_col].isin(match)] if match else fcr.iloc[0:0]
    wide[out_col] = _on_index(sub.rename(columns={"price_eur_mw": "price_eur_mw"}), "price_eur_mw") if len(sub) else pd.Series(0.0, index=IDX)
out = pd.DataFrame({"datetime_utc": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in IDX]})
for c, s in wide.items():
    out[c] = s.to_numpy()
out.to_csv(OUT / "fcr_se.csv", index=False)
print(f"  fcr: {len(IDX)} h  N mean={out['fcr_n_eur_mw'].mean():.1f}  Dup mean={out['fcr_d_up_eur_mw'].mean():.1f}  Ddn mean={out['fcr_d_down_eur_mw'].mean():.1f} EUR/MW", flush=True)
print("done ->", OUT, flush=True)
