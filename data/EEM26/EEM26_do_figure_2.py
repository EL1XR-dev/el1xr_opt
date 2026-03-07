"""
plot_t0t3t4.py  -  IEEE-EEM figure: BESS throughput & V2G utilisation rate
                   for scenarios T0, T3, T4 only, with % change vs T0 annotated.

Run: python plot_t0t3t4.py --root "C:/Users/erikal/EEM26/Results"
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
            if scenario not in ("T0", "T3", "T4"):
                continue
            csv_path = os.path.join(home_path, run_dir,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if not os.path.isfile(csv_path):
                continue
            try:
                df   = pd.read_csv(csv_path, header=[0, 1])
                bess = pd.to_numeric(df[BESS_COL], errors="coerce").fillna(0)
                ev   = pd.to_numeric(df[EV_COL],   errors="coerce").fillna(0)
                bess_throughput = (bess[bess > 0].sum() + bess[bess < 0].abs().sum()) / 2.0
                records.append({
                    "Home":        int(home_id),
                    "Scenario":    scenario,
                    "Cluster":     cluster,
                    "Month":       int(month),
                    "BESS_kWh":    bess_throughput,
                    "V2G_hours":   (ev > 0).sum(),
                    "total_hours": len(ev),
                })
            except Exception as e:
                print(f"  skip {csv_path}: {e}")
    return pd.DataFrame(records)


def aggregate(df):
    per_home = (df.groupby(["Home", "Scenario", "Cluster"])
                  .agg(BESS_kWh    = ("BESS_kWh",    "sum"),
                       V2G_hours   = ("V2G_hours",   "sum"),
                       total_hours = ("total_hours", "sum"))
                  .reset_index())
    per_home["V2G_rate"] = per_home["V2G_hours"] / per_home["total_hours"] * 100
    agg = (per_home.groupby(["Scenario", "Cluster"])
                   .agg(BESS_kWh = ("BESS_kWh", "mean"),
                        V2G_rate = ("V2G_rate",  "mean"))
                   .reset_index())
    return agg


# -- Plot ----------------------------------------------------------------------
def pct_label(val, ref):
    """Return a formatted +X.X% / -X.X% string relative to ref."""
    if ref == 0:
        return ""
    p = (val - ref) / ref * 100
    sign = "+" if p >= 0 else "\u2212"   # unicode minus for cleaner look
    return f"{sign}{abs(p):.1f}%"


def plot(agg, out_stem="fig_bess_v2g_t0t3t4"):
    SCENARIOS = ["T0", "T3", "T4"]

    def get(sc, cl, col):
        row = agg[(agg.Scenario == sc) & (agg.Cluster == cl)]
        return float(row[col].iloc[0]) if len(row) else 0.0

    bess_B = np.array([get(s, "ClusterB", "BESS_kWh") for s in SCENARIOS])
    bess_D = np.array([get(s, "ClusterD", "BESS_kWh") for s in SCENARIOS])
    v2g_D  = np.array([get(s, "ClusterD", "V2G_rate")  for s in SCENARIOS])

    # Baseline (T0) for % change annotations
    ref_B   = bess_B[0]
    ref_D   = bess_D[0]
    ref_v2g = v2g_D[0]

    # ── Layout ────────────────────────────────────────────────────────────────
    fig, ax1 = plt.subplots(layout="constrained", figsize=(7.16, 2.3))
    ax2 = ax1.twinx()

    n = len(SCENARIOS)
    x = np.arange(n, dtype=float)
    w, gap = 0.20, 0.07

    xB = x - w/2 - gap/2
    xD = x + w/2 - gap/2
    xV = x + w   + gap

    C_B, C_D, C_V2G = "#0072B2", "#009E73", "#CC6677"
    kw = dict(width=w, zorder=3, linewidth=0.45, edgecolor="#333333")

    rects_B   = ax1.bar(xB, bess_B, color=C_B,   **kw)
    rects_D   = ax1.bar(xD, bess_D, color=C_D,   **kw)
    ax2.plot(x, v2g_D, color=C_V2G, linewidth=1.4, linestyle="--",
             marker="o", markersize=4.5, markeredgewidth=0.4,
             markeredgecolor="white", markerfacecolor=C_V2G, zorder=5)

    # ── Grid ──────────────────────────────────────────────────────────────────
    ax1.yaxis.grid(True, linestyle=":", linewidth=0.4, color="0.72", zorder=0)
    ax1.set_axisbelow(True)
    ax2.yaxis.grid(False)

    # ── Limits (extra headroom at top for annotations) ────────────────────────
    bess_max = max(bess_B.max(), bess_D.max())
    ax1.set_ylim(0, bess_max * 1.52)
    ax2.set_ylim(0, max(v2g_D.max() * 2.10, 1))

    # ── % change annotations ──────────────────────────────────────────────────
    # Annotate T3 and T4 bars only (index 1 and 2); T0 gets no label
    ann_kw = dict(ha="center", va="bottom", fontsize=8, zorder=5,
                  clip_on=False)

    for i, sc in enumerate(SCENARIOS):
        if sc == "T0":
            continue   # baseline: no annotation

        # BESS Cluster B
        lbl = pct_label(bess_B[i], ref_B)
        col = "#0072B2" if bess_B[i] >= ref_B else "#AA3333"
        ax1.text(xB[i], bess_B[i] + bess_max * 0.012, lbl,
                 color=col, fontweight="bold", **ann_kw)

        # BESS Cluster D
        lbl = pct_label(bess_D[i], ref_D)
        col = "#006644" if bess_D[i] >= ref_D else "#AA3333"
        ax1.text(xD[i], bess_D[i] + bess_max * 0.012, lbl,
                 color=col, fontweight="bold", **ann_kw)

        # V2G rate  (use ax2 data coordinates)
        v2g_max = v2g_D.max()
        lbl = pct_label(v2g_D[i], ref_v2g)
        col = "#993333" if v2g_D[i] >= ref_v2g else "#AA3333"
        ax2.text(x[i],  v2g_D[i] + v2g_max * 0.02 - 3.5, lbl,
                 color=col, fontweight="bold", **ann_kw)

    # ── Axes labels & ticks ───────────────────────────────────────────────────
    ax1.set_ylabel("BESS throughput [kWh/year]", fontsize=10, labelpad=4)
    ax2.set_ylabel("V2G utilisation rate [%]",   fontsize=10, labelpad=6,
                   rotation=270, va="center")

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"$T_{{{s[1]}}}$" for s in SCENARIOS], fontsize=11)
    ax1.tick_params(axis="both", labelsize=9)
    ax2.tick_params(axis="y",    labelsize=9)

    ax1.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # ── Spines ────────────────────────────────────────────────────────────────
    for sp in ("left", "bottom"):
        ax1.spines[sp].set_linewidth(0.55)
    ax2.spines["right"].set_linewidth(0.55)
    ax2.spines["top"].set_visible(False)

    # ── Legend ────────────────────────────────────────────────────────────────
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
    ap.add_argument("--out",  default="fig_bess_v2g_t0t3t4")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    raw = extract(args.root)
    print(f"  Records found: {len(raw)}")

    agg = aggregate(raw)
    agg.to_csv(args.out + "_data.csv", index=False)
    print("\n=== Aggregated values ===")
    print(agg.to_string(index=False))

    plot(agg, out_stem=args.out)