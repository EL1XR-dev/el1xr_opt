"""
plot_combined.py  -  IEEE-EEM figure (two-panel, shared x-axis)
  Top panel   : mean annual net cost change vs T0 [SEK/year]  (bars, colour-coded)
                + monthly P95 grid-import peak [kW]           (line, right axis)
                Excludes: 'Depth of Discharge Cost', 'Network Fixed Cost'
  Bottom panel: mean annual DoD cost [SEK/year] per Cluster   (grouped bars)

Run:
    python plot_combined.py --root "C:/Users/erikal/EEM26/Results"
"""

import argparse, os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

plt.rcParams.update({
    "font.family":          "serif",
    "font.serif":           ["Times New Roman", "DejaVu Serif"],
    "font.size":            8,
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

EXCLUDE_COST  = {"Depth of Discharge Cost", "Network Fixed Cost"}
ELECBUY_COL   = ("Electricity Buy [kWh]", "Node1")
DIR_PATT      = re.compile(
    r"Home(\d+)_(T\d+)_H(\d+)_(Cluster[A-Z])_wDoD_Month(\d+)")
SCENARIOS     = ["T0", "T1", "T2", "T3", "T4"]

CLUSTER_COLORS = {
    "ClusterA": "#E69F00",
    "ClusterB": "#0072B2",
    "ClusterC": "#CC79A7",
    "ClusterD": "#009E73",
}


# ── Extraction ────────────────────────────────────────────────────────────────
def extract(root):
    cost_rec, peak_rec, dod_rec = [], [], []

    for home_dir in sorted(os.listdir(root)):
        home_path = os.path.join(root, home_dir)
        if not os.path.isdir(home_path):
            continue
        for run_dir in sorted(os.listdir(home_path)):
            m = DIR_PATT.search(run_dir)
            if not m:
                continue
            home_id, scenario, hh, cluster, month = m.groups()
            run_path = os.path.join(home_path, run_dir)

            # ── File 01: cost components ──────────────────────────────────────
            f01 = os.path.join(run_path,
                f"oM_Result_01_rObjFunComponents_{run_dir}.csv")
            if os.path.isfile(f01):
                try:
                    df = pd.read_csv(f01)
                    df["SEK"] = pd.to_numeric(
                        df["SEK"], errors="coerce").fillna(0)
                    # Tariff-sensitive net cost
                    net = df.loc[
                        ~df["Component"].isin(EXCLUDE_COST), "SEK"].sum()
                    # Degradation proxy
                    dod = df.loc[
                        df["Component"] == "Depth of Discharge Cost",
                        "SEK"].sum()
                    cost_rec.append({
                        "Home": int(home_id), "Scenario": scenario,
                        "Cluster": cluster,   "Month": int(month),
                        "NetCost": net,
                    })
                    dod_rec.append({
                        "Home": int(home_id), "Scenario": scenario,
                        "Cluster": cluster,   "Month": int(month),
                        "DoD": dod,
                    })
                except Exception as e:
                    print(f"  skip {f01}: {e}")

            # ── File 07: hourly grid import for peak ──────────────────────────
            f07 = os.path.join(run_path,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if os.path.isfile(f07):
                try:
                    df = pd.read_csv(f07, header=[0, 1])
                    buy = pd.to_numeric(
                        df[ELECBUY_COL], errors="coerce").fillna(0)
                    peak_rec.append({
                        "Home": int(home_id), "Scenario": scenario,
                        "Cluster": cluster,   "Month": int(month),
                        "MonthlyPeak_kW": buy.max(),
                    })
                except Exception as e:
                    print(f"  skip {f07}: {e}")

    return (pd.DataFrame(cost_rec),
            pd.DataFrame(peak_rec),
            pd.DataFrame(dod_rec))


# ── Aggregation ───────────────────────────────────────────────────────────────
def aggregate(cost_df, peak_df, dod_df):
    # ── Top panel: cost change + P95 peak ────────────────────────────────────
    annual_cost = (cost_df.groupby(["Home", "Scenario"])["NetCost"]
                          .sum().reset_index())
    mean_cost   = (annual_cost.groupby("Scenario")["NetCost"]
                              .mean().reset_index())
    t0_cost     = mean_cost.loc[
        mean_cost.Scenario == "T0", "NetCost"].values[0]
    mean_cost["CostChange"] = mean_cost["NetCost"] - t0_cost

    p95 = (peak_df.groupby("Scenario")["MonthlyPeak_kW"]
                  .quantile(0.95).reset_index()
                  .rename(columns={"MonthlyPeak_kW": "P95_kW"}))

    top = (mean_cost.merge(p95, on="Scenario")
                    .set_index("Scenario")
                    .loc[SCENARIOS].reset_index())

    # ── Bottom panel: DoD cost per Cluster ────────────────────────────────────
    annual_dod = (dod_df.groupby(["Home", "Scenario", "Cluster"])["DoD"]
                        .sum().reset_index())
    mean_dod   = (annual_dod.groupby(["Scenario", "Cluster"])["DoD"]
                             .mean().reset_index())
    order_map  = {s: i for i, s in enumerate(SCENARIOS)}
    mean_dod["_o"] = mean_dod["Scenario"].map(order_map)
    bot = mean_dod.sort_values("_o").drop(columns="_o").reset_index(drop=True)

    return top, bot


# ── Plot ──────────────────────────────────────────────────────────────────────
def plot(top, bot, out_stem="fig_combined"):
    clusters = sorted(bot["Cluster"].unique())

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1,
        figsize=(4.5, 2.5),
        sharex=True,
        gridspec_kw={"hspace": 0.10, "height_ratios": [1, 1]},
    layout="constrained",
    )

    x = np.arange(len(SCENARIOS), dtype=float)

    # ── Colours ───────────────────────────────────────────────────────────────
    C_NEG  = "#009E73"
    C_POS  = "#4878CF"
    C_BASE = "#AAAAAA"
    C_LINE = "#D65F5F"

    # ============================================================
    # TOP PANEL: cost change bars + P95 peak line
    # ============================================================
    ax_top2 = ax_top.twinx()

    cost_chg   = top["CostChange"].values
    p95        = top["P95_kW"].values
    bar_colors = [C_BASE] + [
        C_NEG if v < 0 else C_POS for v in cost_chg[1:]]

    ax_top.bar(x, cost_chg, width=0.42, color=bar_colors,
               zorder=3, linewidth=0.45, edgecolor="#333333")
    ax_top.axhline(0, color="0.40", linewidth=0.55, zorder=4)

    ax_top2.plot(x, p95, color=C_LINE, linewidth=1.2, zorder=5,
                 marker="o", markersize=3.5,
                 markeredgewidth=0.4, markeredgecolor="#333333",
                 markerfacecolor=C_LINE, solid_capstyle="round")

    # grid
    ax_top.yaxis.grid(True,  linestyle=":", linewidth=0.4,
                      color="0.72", zorder=0)
    ax_top.set_axisbelow(True)
    ax_top2.yaxis.grid(False)

    # limits
    abs_max = max(abs(cost_chg.min()), abs(cost_chg.max()), 1)
    ax_top.set_ylim(-abs_max * 1.55, abs_max * 1.55)
    p95_span = max(p95.max() - p95.min(), 0.1)
    ax_top2.set_ylim(p95.min() - p95_span * 0.9,
                     p95.max() + p95_span * 0.9)

    # labels
    ax_top.set_ylabel(r"$\Delta$ cost vs. $T_0$ [SEK/year]",
                      fontsize=7, labelpad=4)
    ax_top2.set_ylabel("Monthly P95 peak [kW]", fontsize=7, labelpad=6,
                       rotation=270, va="center")
    ax_top.tick_params(axis="y", labelsize=6.5)
    ax_top2.tick_params(axis="y", labelsize=6.5)
    ax_top.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # panel label
    ax_top.text(0.01, 0.97, "(a)", transform=ax_top.transAxes,
                fontsize=7, va="top", fontweight="bold")

    # spines
    ax_top.spines["left"].set_linewidth(0.55)
    ax_top.spines["bottom"].set_visible(False)   # shared axis — hide bottom
    ax_top2.spines["right"].set_linewidth(0.55)
    ax_top2.spines["top"].set_visible(False)

    # legend
    top_handles = [
        mpatches.Patch(facecolor=C_NEG,  edgecolor="#333", linewidth=0.45,
                       label="Cost saving"),
        mpatches.Patch(facecolor=C_POS,  edgecolor="#333", linewidth=0.45,
                       label="Cost increase"),
        Line2D([0], [0], color=C_LINE, linewidth=1.2,
               marker="o", markersize=3.5,
               markeredgewidth=0.4, markeredgecolor="#333",
               label="P95 peak"),
    ]
    ax_top.legend(handles=top_handles, fontsize=5.8, loc="lower left",
                  framealpha=1.0, facecolor="white", edgecolor="0.75",
                  handlelength=1.4, handletextpad=0.45,
                  borderpad=0.55, labelspacing=0.3)

    # ============================================================
    # BOTTOM PANEL: DoD cost grouped bars by Cluster
    # ============================================================
    nc      = len(clusters)
    w_bar   = 0.65 / nc
    offsets = np.linspace(-(nc - 1) / 2, (nc - 1) / 2, nc) * w_bar

    for ci, cl in enumerate(clusters):
        sub  = bot[bot.Cluster == cl].set_index("Scenario")
        vals = np.array([
            sub.loc[s, "DoD"] if s in sub.index else 0.0
            for s in SCENARIOS])
        ax_bot.bar(x + offsets[ci], vals, width=w_bar,
                   color=CLUSTER_COLORS.get(cl, f"C{ci}"),
                   zorder=3, linewidth=0.45, edgecolor="#333333")

    ax_bot.yaxis.grid(True, linestyle=":", linewidth=0.4,
                      color="0.72", zorder=0)
    ax_bot.set_axisbelow(True)

    ax_bot.set_ylabel("DoD cost [SEK/year]", fontsize=7, labelpad=4)
    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels(
        [f"$T_{{{s[1]}}}$" for s in SCENARIOS], fontsize=8)
    ax_bot.tick_params(axis="both", labelsize=6.5)
    ax_bot.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    ax_bot.text(0.01, 0.97, "(b)", transform=ax_bot.transAxes,
                fontsize=7, va="top", fontweight="bold")

    ax_bot.spines["left"].set_linewidth(0.55)
    ax_bot.spines["bottom"].set_linewidth(0.55)

    bot_handles = [
        mpatches.Patch(
            facecolor=CLUSTER_COLORS.get(cl, f"C{i}"),
            edgecolor="#333", linewidth=0.45,
            label=f"Cl.\u2009{cl[-1]}")
        for i, cl in enumerate(clusters)
    ]
    ax_bot.legend(handles=bot_handles, fontsize=5.8, loc="upper right",
                  framealpha=1.0, facecolor="white", edgecolor="0.75",
                  handlelength=1.2, handletextpad=0.45,
                  borderpad=0.55, labelspacing=0.3)

    # ── Save ──────────────────────────────────────────────────────────────────
    # constrained_layout handles spacing
    for ext in ("pdf", "png"):
        fig.savefig(f"{out_stem}.{ext}", dpi=300, bbox_inches="tight")
        print(f"Saved: {out_stem}.{ext}")
    plt.close(fig)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Results")
    ap.add_argument("--out",  default="fig_combined")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    cost_df, peak_df, dod_df = extract(args.root)
    print(f"  Cost records : {len(cost_df)}")
    print(f"  Peak records : {len(peak_df)}")
    print(f"  DoD  records : {len(dod_df)}")

    top, bot = aggregate(cost_df, peak_df, dod_df)

    top.to_csv(args.out + "_top.csv",    index=False)
    bot.to_csv(args.out + "_bottom.csv", index=False)

    print("\n=== Top panel (cost change + P95) ===")
    print(top[["Scenario", "CostChange", "P95_kW"]].to_string(index=False))
    print("\n=== Bottom panel (DoD cost) ===")
    print(bot.pivot(index="Scenario", columns="Cluster",
                    values="DoD").to_string())

    plot(top, bot, out_stem=args.out)
