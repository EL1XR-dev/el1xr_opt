"""
plot_final.py  -  IEEE-EEM figure: BESS throughput & V2G utilisation rate
Run: python plot_final.py --root "C:/Users/erikal/EEM26/Results"

Metric definitions (v4)
-----------------------
BESS throughput [kWh/year]:
    (sum of BESS discharge + sum of |BESS charge|) / 2
    i.e. standard roundtrip cycling throughput, averaged over Homes in Cluster,
    summed over 12 months.

V2G utilisation rate [%]:
    (hours where EV > 0) / total_hours * 100
    Total hours = all calendar hours in the year (8760).
    Same denominator as BESS makes metrics directly comparable.
"""

import argparse, os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.ticker as mticker

# -- RC / fonts ----------------------------------------------------------------
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

# -- Data extraction -----------------------------------------------------------
BESS_COL  = ("Production/Discharge [kWh]", "BESS")
EV_COL    = ("Production/Discharge [kWh]", "EV")
FILE_PATT = re.compile(r"Home(\d+)_(T\d+)_H(\d+)_(Cluster[A-Z])_wDoD_Month(\d+)")

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
            csv_path = os.path.join(home_path, run_dir,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if not os.path.isfile(csv_path):
                continue
            try:
                df   = pd.read_csv(csv_path, header=[0, 1])
                bess = pd.to_numeric(df[BESS_COL], errors="coerce").fillna(0)
                ev   = pd.to_numeric(df[EV_COL],   errors="coerce").fillna(0)

                # BESS throughput: (discharge + |charge|) / 2
                bess_discharge = bess[bess > 0].sum()
                bess_charge    = bess[bess < 0].abs().sum()
                bess_throughput = (bess_discharge + bess_charge) / 2.0

                # V2G utilisation: V2G hours / total calendar hours
                v2g_hours  = (ev > 0).sum()
                total_hours = len(ev)

                records.append({
                    "Home":          int(home_id),
                    "Scenario":      scenario,
                    "H":             int(hh),
                    "Cluster":       cluster,
                    "Month":         int(month),
                    "BESS_kWh":      bess_throughput,
                    "V2G_hours":     v2g_hours,
                    "total_hours":   total_hours,
                })
            except Exception as e:
                print(f"  skip {csv_path}: {e}")
    return pd.DataFrame(records)


def aggregate(df):
    # Sum months per Home×Scenario×Cluster (V2G: sum hours, then compute rate)
    per_home = (df.groupby(["Home", "Scenario", "Cluster"])
                  .agg(
                      BESS_kWh    = ("BESS_kWh",    "sum"),
                      V2G_hours   = ("V2G_hours",   "sum"),
                      total_hours = ("total_hours", "sum"),
                  )
                  .reset_index())

    # V2G rate from summed hours (correct: annual V2G h / annual total h)
    per_home["V2G_rate"] = per_home["V2G_hours"] / per_home["total_hours"] * 100

    # Average across Homes within each Scenario×Cluster
    agg = (per_home.groupby(["Scenario", "Cluster"])
                   .agg(
                       BESS_kWh  = ("BESS_kWh",  "mean"),
                       V2G_rate  = ("V2G_rate",  "mean"),
                   )
                   .reset_index())
    return agg, per_home


# -- Plot ----------------------------------------------------------------------
def plot(agg, out_stem="fig_bess_v2g"):
    SCENARIOS = ["T0", "T1", "T2", "T3", "T4"]

    def get(sc, cl, col):
        row = agg[(agg.Scenario == sc) & (agg.Cluster == cl)]
        return float(row[col].iloc[0]) if len(row) else 0.0

    bess_B = np.array([get(s, "ClusterB", "BESS_kWh") for s in SCENARIOS])
    bess_D = np.array([get(s, "ClusterD", "BESS_kWh") for s in SCENARIOS])
    v2g_D  = np.array([get(s, "ClusterD", "V2G_rate")  for s in SCENARIOS])

    fig, ax1 = plt.subplots(layout="constrained", figsize=(7.16, 2.2))
    ax2 = ax1.twinx()

    n = len(SCENARIOS)
    x = np.arange(n, dtype=float)
    w, gap = 0.20, 0.07

    xB = x - w/2 - gap/2
    xD = x + w/2 - gap/2
    xV = x + w   + gap

    C_B, C_D, C_V2G = "#0072B2", "#009E73", "#CC6677"
    kw = dict(width=w, zorder=3, linewidth=0.45, edgecolor="#333333")

    ax1.bar(xB, bess_B, color=C_B,   **kw)
    ax1.bar(xD, bess_D, color=C_D,   **kw)
    ax2.plot(x, v2g_D, color=C_V2G, linewidth=1.4, linestyle="--",
             marker="o", markersize=4.5, markeredgewidth=0.4,
             markeredgecolor="white", markerfacecolor=C_V2G, zorder=5)

    # Grid: left-axis only
    ax1.yaxis.grid(True, linestyle=":", linewidth=0.4, color="0.72", zorder=0)
    ax1.set_axisbelow(True)
    ax2.yaxis.grid(False)

    ax1.set_ylim(0, max(bess_B.max(), bess_D.max()) * 1.38)
    ax2.set_ylim(0, max(v2g_D.max() * 1.90, 1))

    ax1.set_ylabel("BESS throughput [kWh/year]", fontsize=10, labelpad=4)
    ax2.set_ylabel("V2G utilisation rate [%]",   fontsize=10, labelpad=6,
                   rotation=270, va="center")

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"$T_{{{s[1]}}}$" for s in SCENARIOS], fontsize=11)
    ax1.tick_params(axis="both", labelsize=9)
    ax2.tick_params(axis="y",    labelsize=9)

    ax1.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    for sp in ("left", "bottom"):
        ax1.spines[sp].set_linewidth(0.55)
    ax2.spines["right"].set_linewidth(0.55)
    ax2.spines["top"].set_visible(False)

    handles = [
        mpatches.Patch(facecolor=C_B,   edgecolor="#333", linewidth=0.45,
                       label="BESS, Cl.\u2009B"),
        mpatches.Patch(facecolor=C_D,   edgecolor="#333", linewidth=0.45,
                       label="BESS, Cl.\u2009D"),
        Line2D([0],[0], color=C_V2G, linewidth=1.4, linestyle="--",
               marker="o", markersize=4.5, markeredgewidth=0.4,
               markeredgecolor="white", markerfacecolor=C_V2G,
               label="V2G util., Cl.\u2009D"),
    ]
    ax1.legend(
        handles=handles, fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=len(handles),
        framealpha=1.0, facecolor="white", edgecolor="0.75",
        handlelength=1.1, handletextpad=0.4,
        borderpad=0.45, columnspacing=0.7,
    )

    # constrained_layout handles spacing

    for ext in ("pdf", "png"):
        p = f"{out_stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Saved: {p}")
    plt.close(fig)


# -- Entry point ---------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Results")
    ap.add_argument("--out",  default="fig_bess_v2g")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    raw = extract(args.root)
    print(f"  Records found: {len(raw)}")

    agg, per_home = aggregate(raw)

    # Save intermediates for audit
    raw.to_csv(args.out + "_raw.csv",      index=False)
    per_home.to_csv(args.out + "_per_home.csv", index=False)
    agg.to_csv(args.out + "_data.csv",     index=False)

    print("\n=== Per-home annual summary (ClusterB & D) ===")
    mask = per_home.Cluster.isin(["ClusterB","ClusterD"])
    print(per_home[mask].sort_values(["Cluster","Scenario","Home"])
                        .to_string(index=False))

    print("\n=== Aggregated (mean over Homes) ===")
    print(agg.to_string(index=False))

    plot(agg, out_stem=args.out)