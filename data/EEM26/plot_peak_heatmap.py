"""
plot_peak_heatmap.py  -  IEEE-EEM figure: peak import timing heatmap
=====================================================================
Three panels (T0 | T3 | T4), each a 12-month × 24-hour grid.
Cell colour = mean grid import [kW] at that (month, hour) averaged over
all Home × Cluster pairs where that cell is the monthly peak hour.

A cell is "active" if EleBuy_N1 in that (month, hour-of-day) equals the
monthly maximum for that Home×Cluster×Scenario combination.
Colour encodes the average peak magnitude; white = that hour is never peak.

Run:
    python plot_peak_heatmap.py --root "C:/Users/erikal/EEM26/Results"
"""

import argparse, os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap

FILE_PATT = re.compile(
    r"Home(\d+)_(T\d+)_H(\d+)_(Cluster[A-Z])_wDoD_Month(\d+)")
BUY_COL = ("Electricity Buy [kWh]", "Node1")

SCENARIOS = ["T0", "T3", "T4"]

plt.rcParams.update({
    "font.family":          "serif",
    "font.serif":           ["Times New Roman", "DejaVu Serif"],
    "font.size":            10,
    "axes.linewidth":       0.55,
    "xtick.major.width":    0.5,
    "ytick.major.width":    0.5,
    "xtick.major.size":     2.5,
    "ytick.major.size":     2.5,
    "xtick.minor.visible":  False,
    "ytick.minor.visible":  False,
    "axes.spines.top":      False,
    "pdf.fonttype":         42,
    "ps.fonttype":          42,
})


def extract(root):
    records = []
    for home_dir in sorted(os.listdir(root)):
        home_path = os.path.join(root, home_dir)
        if not os.path.isdir(home_path):
            continue
        for run_dir in sorted(os.listdir(home_path)):
            m = FILE_PATT.search(run_dir)
            if not m:
                continue
            home_id, scenario, hh, cluster, month = m.groups()
            if scenario not in SCENARIOS:
                continue
            csv_path = os.path.join(home_path, run_dir,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if not os.path.isfile(csv_path):
                continue
            try:
                df  = pd.read_csv(csv_path, header=[0, 1])
                buy = pd.to_numeric(df[BUY_COL], errors="coerce").fillna(0)

                # Build hour-of-day index (file has 1-hour resolution)
                n = len(buy)
                hours = np.arange(n) % 24

                # Find the peak hour(s) in this month
                peak_val = buy.max()
                if peak_val <= 0:
                    continue
                peak_idx = buy.idxmax()   # first occurrence
                peak_hour = int(hours[peak_idx])

                records.append({
                    "Home":      int(home_id),
                    "Scenario":  scenario,
                    "Cluster":   cluster,
                    "Month":     int(month),
                    "PeakHour":  peak_hour,
                    "PeakVal":   float(peak_val),
                })
            except Exception as e:
                print(f"  skip {csv_path}: {e}")
    return pd.DataFrame(records)


def build_heatmap(df, scenario):
    """
    Returns a (12, 24) array: mean peak magnitude for each (month, hour) cell.
    NaN where that hour is never the peak hour.
    """
    sub = df[df.Scenario == scenario]
    grid = np.full((12, 24), np.nan)
    for month in range(1, 13):
        msub = sub[sub.Month == month]
        if msub.empty:
            continue
        for hour in range(24):
            hsub = msub[msub.PeakHour == hour]
            if not hsub.empty:
                grid[month - 1, hour] = hsub["PeakVal"].mean()
    return grid


def plot(df, out_stem="fig_peak_heatmap"):
    grids = {s: build_heatmap(df, s) for s in SCENARIOS}

    # Shared colour scale across all panels
    vmax = max(np.nanmax(g) for g in grids.values())
    vmin = 0.0

    # Custom colormap: white → amber → dark blue (perceptually ordered)
    cmap = LinearSegmentedColormap.from_list(
        "peak", ["#FFFFFF", "#F0A500", "#0072B2"], N=256)
    cmap.set_bad(color="#F5F5F5")   # NaN cells = light grey

    TITLES = {"T0": "$T_0$ (baseline)", "T3": "$T_3$ (monthly pool)",
               "T4": "$T_4$ (single peak)"}
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]

    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2),
                             layout="constrained",
                             gridspec_kw={"wspace": 0.08})

    ims = []
    for ax, sc in zip(axes, SCENARIOS):
        im = ax.imshow(grids[sc], aspect="auto", origin="upper",
                       vmin=vmin, vmax=vmax, cmap=cmap,
                       interpolation="nearest")
        ims.append(im)

        ax.set_title(TITLES[sc], fontsize=9, pad=3)
        ax.set_xlabel("Hour of day", fontsize=8, labelpad=2)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xticklabels(["0", "6", "12", "18", "23"], fontsize=7.5)
        ax.set_yticks(range(12))
        ax.tick_params(axis="both", length=2)

        if ax is axes[0]:
            ax.set_yticklabels(MONTHS, fontsize=7.5)
            ax.set_ylabel("Month", fontsize=8, labelpad=3)
        else:
            ax.set_yticklabels([])

        # Spine styling
        for sp in ax.spines.values():
            sp.set_linewidth(0.45)

    # Shared colorbar
    cbar = fig.colorbar(ims[0], ax=axes, orientation="vertical",
                        fraction=0.025, pad=0.02, shrink=0.92)
    cbar.set_label("Mean peak import [kW]", fontsize=8, labelpad=4)
    cbar.ax.tick_params(labelsize=7.5, length=2, width=0.45)
    cbar.outline.set_linewidth(0.45)

    for ext in ("pdf", "png"):
        p = f"{out_stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Results")
    ap.add_argument("--out",  default="fig_peak_heatmap")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    df = extract(args.root)
    print(f"  Records: {len(df)}")
    plot(df, out_stem=args.out)
