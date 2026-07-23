"""Full-year 2025 hourly wind CF profile for an SE3 west-coast onshore site via ERA5/atlite.

Writes inputs/real_data/year/wind_se3.csv on the canonical 8736-hour (52-week) UTC index
2025-01-01..2025-12-30, matching the spot/FCR year files so the model can slice any window.
"""
import sys
import pandas as pd
import atlite

LAT, LON = 57.5, 12.1
TURBINE = "Vestas_V112_3MW"
START, END = "2025-01-01", "2025-12-31"
OUT = "/Users/philias/ai_research/repos/paper_H2_frontiers/experiments/h2vpp_fcr/inputs/real_data/year/wind_se3.csv"
CUTOUT_PATH = "/Users/philias/ai_research/repos/paper_H2_frontiers/experiments/h2vpp_fcr/inputs/real_data/year/se3_era5_year.nc"

cutout = atlite.Cutout(
    path=CUTOUT_PATH,
    module="era5",
    x=slice(11.5, 12.7),
    y=slice(57.0, 58.0),
    time=slice(START, END),
)

try:
    cutout.prepare()
except Exception as e:
    print("PREPARE_FAILED")
    print(repr(e))
    sys.exit(2)

cf = cutout.wind(turbine=TURBINE, capacity_factor_timeseries=True)
site = cf.sel(x=LON, y=LAT, method="nearest")
s = site.to_pandas().sort_index()

idx = pd.date_range("2025-01-01T00:00:00", periods=8736, freq="h", tz="UTC")
vals = pd.Series(s.values[:8736], index=idx)

df = pd.DataFrame({
    "datetime_utc": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in idx],
    "cf": vals.values.clip(0, 1),
})
df.to_csv(OUT, index=False)

print("OK")
print(f"rows={len(df)}")
print(f"cf_min={df.cf.min():.4f} cf_mean={df.cf.mean():.4f} cf_max={df.cf.max():.4f}")
print(f"hours_cf_gt0={(df.cf > 0).sum()}")
print(f"nearest_cell_x={float(site.x):.3f} nearest_cell_y={float(site.y):.3f}")
