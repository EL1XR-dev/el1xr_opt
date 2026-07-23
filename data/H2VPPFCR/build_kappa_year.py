"""Derive per-hour FCR activation coefficients (kappa) from measured Nordic frequency.

Replaces the undocumented Home1-seed activation record (see notes/data_sources.md,
'FCR activation record') with a real, reproducible 2025 series.

Source: Fingrid open data, dataset 177 'Frequency - real time data' (3-minute
resolution, Nordic synchronous area, so valid for SE3). Needs FINGRID_API_KEY in the
environment (~/ai_research/.env).

Derivation (activation DEGREE per product, time-averaged per hour, in [0,1]):
    FCR-N is a proportional response fully activated at +-0.1 Hz:
        kappa_N_up(h) = mean( clip((50.0 - f)/0.1, 0, 1) )   # under-frequency -> deliver
        kappa_N_dn(h) = mean( clip((f - 50.0)/0.1, 0, 1) )   # over-frequency  -> absorb
    FCR-D ramps from 49.9 Hz (0%) to 49.5 Hz (100%) (down: 50.1 -> 50.5):
        kappa_D_up(h) = mean( clip((49.9 - f)/0.4, 0, 1) )
        kappa_D_dn(h) = mean( clip((f - 50.1)/0.4, 0, 1) )
    Caveat: 3-minute sampling under-resolves the seconds-scale FCR-D excursions, so the
    kappa_D estimates are indicative (FCR-D activation energy is negligible either way);
    the 10 Hz Fingrid archives can refine them later.

Timestamps are converted to Europe/Stockholm to align with the other SE3 year series
(spot_se3.csv etc.), and the first 8736 hours of 2025 are written.

Outputs (experiments/h2vpp_fcr/inputs/real_data/year/):
    freq_nordic_2025.csv       raw 3-min frequency (startTime UTC, value Hz)
    fcr_activation_2025.csv    hour, FCRD_Up, FCRD_Down, FCRN_Up, FCRN_Down
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "inputs" / "real_data" / "year"
DATASET = 177
BASE = f"https://data.fingrid.fi/api/datasets/{DATASET}/data"
N_HOURS = 8736  # 52 weeks, matching the case year


def fetch_year(year: int = 2025) -> pd.DataFrame:
    key = os.environ["FINGRID_API_KEY"]
    frames = []
    for m in range(1, 13):
        t0 = f"{year}-{m:02d}-01T00:00:00Z"
        t1 = f"{year + (m == 12)}-{(m % 12) + 1:02d}-01T00:00:00Z"
        rows, page = [], 1
        while True:
            r = requests.get(BASE, headers={"x-api-key": key},
                             params={"startTime": t0, "endTime": t1,
                                     "pageSize": 20000, "page": page, "format": "json"},
                             timeout=120)
            if r.status_code == 429:
                time.sleep(10)
                continue
            r.raise_for_status()
            d = r.json()
            batch = d.get("data", [])
            rows.extend(batch)
            pag = d.get("pagination") or {}
            if not batch or page >= (pag.get("lastPage") or 1):
                break
            page += 1
            time.sleep(1.5)
        print(f"  {year}-{m:02d}: {len(rows)} samples", flush=True)
        frames.append(pd.DataFrame(rows))
        time.sleep(2)
    df = pd.concat(frames, ignore_index=True)
    df = df[["startTime", "value"]].dropna()
    df["startTime"] = pd.to_datetime(df["startTime"])
    df = df.drop_duplicates("startTime").sort_values("startTime").reset_index(drop=True)
    return df


def derive_kappa(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.to_numeric(df["value"], errors="coerce")
    # floor to the hour in UTC (no DST ambiguity), THEN convert the hour label to
    # Europe/Stockholm; tz_convert on aware timestamps is always well defined.
    hour_utc = df["startTime"].dt.floor("h")
    hour_local = hour_utc.dt.tz_convert("Europe/Stockholm").dt.tz_localize(None)
    k = pd.DataFrame({
        "FCRN_Up":   np.clip((50.0 - f) / 0.1, 0.0, 1.0),
        "FCRN_Down": np.clip((f - 50.0) / 0.1, 0.0, 1.0),
        "FCRD_Up":   np.clip((49.9 - f) / 0.4, 0.0, 1.0),
        "FCRD_Down": np.clip((f - 50.1) / 0.4, 0.0, 1.0),
    })
    k["hour"] = hour_local
    hourly = k.groupby("hour").mean().reset_index()
    year = int(hourly["hour"].dt.year.mode()[0])
    hourly = hourly[hourly["hour"].dt.year == year].head(N_HOURS)
    return hourly[["hour", "FCRD_Up", "FCRD_Down", "FCRN_Up", "FCRN_Down"]]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("fetching Fingrid dataset 177 (Nordic frequency, 3-min) for 2025 ...", flush=True)
    raw = fetch_year(2025)
    raw.to_csv(OUT / "freq_nordic_2025.csv", index=False)
    print(f"raw samples: {len(raw)} -> {OUT / 'freq_nordic_2025.csv'}")
    kap = derive_kappa(raw)
    kap.to_csv(OUT / "fcr_activation_2025.csv", index=False)
    print(f"hourly kappa rows: {len(kap)} -> {OUT / 'fcr_activation_2025.csv'}")
    for c in ("FCRN_Up", "FCRN_Down", "FCRD_Up", "FCRD_Down"):
        s = kap[c]
        print(f"  {c}: mean {s.mean():.4f}  p95 {s.quantile(0.95):.4f}  max {s.max():.4f}  zeros {(s == 0).sum()}")
