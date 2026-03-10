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
                    "H":           int(hh),
                    "HType":       "Apt" if int(hh) <= 5 else "SF",
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
    per_home = (df.groupby(["Home", "Scenario", "Cluster", "HType"])
                  .agg(BESS_kWh    = ("BESS_kWh",    "sum"),
                       V2G_hours   = ("V2G_hours",   "sum"),
                       total_hours = ("total_hours", "sum"))
                  .reset_index())
    per_home["V2G_rate"] = per_home["V2G_hours"] / per_home["total_hours"] * 100
    agg = (per_home.groupby(["Scenario", "Cluster", "HType"])
                   .agg(BESS_kWh = ("BESS_kWh", "mean"),
                        V2G_rate = ("V2G_rate",  "mean"))
                   .reset_index())
    return agg


# -- Plot ----------------------------------------------------------------------
def pct_label(val, ref):
    if ref == 0:
        return ""
    p = (val - ref) / ref * 100
    sign = "+" if p >= 0 else "−"
    return f"{sign}{abs(p):.1f}%"


def plot(agg, out_stem="fig_bess_v2g_t0t3t4"):
    SCENARIOS = ["T0", "T3", "T4"]

    def get(sc, cl, ht, col):
        row = agg[(agg.Scenario==sc) & (agg.Cluster==cl) & (agg.HType==ht)]
        return float(row[col].iloc[0]) if len(row) else 0.0

    bess_B_apt = np.array([get(s,"ClusterB","Apt","BESS_kWh") for s in SCENARIOS])
    bess_B_sf  = np.array([get(s,"ClusterB","SF", "BESS_kWh") for s in SCENARIOS])
    bess_D_apt = np.array([get(s,"ClusterD","Apt","BESS_kWh") for s in SCENARIOS])
    bess_D_sf  = np.array([get(s,"ClusterD","SF", "BESS_kWh") for s in SCENARIOS])
    v2g_D_apt  = np.array([get(s,"ClusterD","Apt","V2G_rate")  for s in SCENARIOS])
    v2g_D_sf   = np.array([get(s,"ClusterD","SF", "V2G_rate")  for s in SCENARIOS])

    # T0 baselines
    ref_B_apt, ref_B_sf   = bess_B_apt[0], bess_B_sf[0]
    ref_D_apt, ref_D_sf   = bess_D_apt[0], bess_D_sf[0]
    ref_v_apt, ref_v_sf   = v2g_D_apt[0],  v2g_D_sf[0]

    fig, ax1 = plt.subplots(layout="constrained", figsize=(7.16, 2.5))
    ax2 = ax1.twinx()

    n   = len(SCENARIOS)
    x   = np.arange(n, dtype=float)
    w   = 0.17
    grp = 0.06
    xB_apt = x - grp/2 - w*1.5
    xB_sf  = x - grp/2 - w*0.5
    xD_apt = x + grp/2 + w*0.5
    xD_sf  = x + grp/2 + w*1.5

    C_B,  C_D  = "#0072B2", "#009E73"
    C_BA, C_DA = "#7BBDE0", "#5EC4A4"
    C_V2G      = "#CC6677"
    kw = dict(width=w, zorder=3, linewidth=0.45, edgecolor="#333333")

    ax1.bar(xB_apt, bess_B_apt, color=C_BA, **kw)
    ax1.bar(xB_sf,  bess_B_sf,  color=C_B,  **kw)
    ax1.bar(xD_apt, bess_D_apt, color=C_DA, **kw)
    ax1.bar(xD_sf,  bess_D_sf,  color=C_D,  **kw)

    line_kw = dict(linewidth=1.3, linestyle="--", markersize=4.0,
                   markeredgewidth=0.4, markeredgecolor="white", zorder=5)
    ax2.plot(x, v2g_D_apt, color=C_DA,  marker="o", markerfacecolor=C_DA,  **line_kw)
    ax2.plot(x, v2g_D_sf,  color=C_V2G, marker="o", markerfacecolor=C_V2G, **line_kw)

    ax1.yaxis.grid(True, linestyle=":", linewidth=0.4, color="0.72", zorder=0)
    ax1.set_axisbelow(True)
    ax2.yaxis.grid(False)

    bess_max = max(bess_B_apt.max(), bess_B_sf.max(),
                   bess_D_apt.max(), bess_D_sf.max())
    v2g_max  = max(v2g_D_apt.max(), v2g_D_sf.max())
    ax1.set_ylim(0, bess_max * 1.60)   # extra headroom for annotations
    ax2.set_ylim(0, max(v2g_max * 2.40, 1))

    # ── % change annotations (T3, T4 only) ────────────────────────────────────
    ann_kw = dict(ha="center", va="bottom", fontsize=7.5, zorder=5, clip_on=False)

    for i, sc in enumerate(SCENARIOS):
        if sc == "T0":
            continue
        for xi, val, ref, base_col in [
            (xB_apt[i], bess_B_apt[i], ref_B_apt, C_BA),
            (xB_sf[i],  bess_B_sf[i],  ref_B_sf,  C_B),
            (xD_apt[i], bess_D_apt[i], ref_D_apt, C_DA),
            (xD_sf[i],  bess_D_sf[i],  ref_D_sf,  C_D),
        ]:
            lbl = pct_label(val, ref)
            col = base_col
            ax1.text(xi, val + bess_max * 0.025, lbl,
                     color=col, fontweight="bold", **ann_kw)

        for xi, val, ref, base_col in [
            (x[i] - 0.07, v2g_D_apt[i], ref_v_apt, C_DA),
            (x[i] + 0.07, v2g_D_sf[i],  ref_v_sf,  C_V2G),
        ]:
            lbl = pct_label(val, ref)
            col = base_col
            ax2.text(xi, val + v2g_max * 0.10, lbl,
                     color=col, fontweight="bold", **ann_kw)

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
        mpatches.Patch(facecolor=C_BA, edgecolor="#333", linewidth=0.45,
                       label="BESS Cl.\u2009B, Apt."),
        mpatches.Patch(facecolor=C_B,  edgecolor="#333", linewidth=0.45,
                       label="BESS Cl.\u2009B, S.F."),
        mpatches.Patch(facecolor=C_DA, edgecolor="#333", linewidth=0.45,
                       label="BESS Cl.\u2009D, Apt."),
        mpatches.Patch(facecolor=C_D,  edgecolor="#333", linewidth=0.45,
                       label="BESS Cl.\u2009D, S.F."),
        Line2D([0],[0], color=C_DA,  linewidth=1.3, linestyle="--",
               marker="o", markersize=4.0, markeredgewidth=0.4,
               markeredgecolor="white", markerfacecolor=C_DA,
               label="V2G Cl.\u2009D, Apt."),
        Line2D([0],[0], color=C_V2G, linewidth=1.3, linestyle="--",
               marker="o", markersize=4.0, markeredgewidth=0.4,
               markeredgecolor="white", markerfacecolor=C_V2G,
               label="V2G Cl.\u2009D, S.F."),
    ]
    ax1.legend(
        handles=handles, fontsize=7.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=len(handles),
        framealpha=1.0, facecolor="white", edgecolor="0.75",
        handlelength=1.1, handletextpad=0.35,
        borderpad=0.45, columnspacing=0.55,
    )

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