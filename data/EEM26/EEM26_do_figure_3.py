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
                        "Home": int(home_id), "H": int(hh),
                        "Scenario": scenario,
                        "Cluster": cluster,   "Month": int(month),
                        "NetCost": net,
                    })
                    dod_rec.append({
                        "Home": int(home_id), "H": int(hh),
                        "Scenario": scenario,
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
                        "Home": int(home_id), "H": int(hh),
                        "Scenario": scenario,
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
    # ── Top panel: per-cluster cost change + P95 peak ───────────────────────
    # Annual cost per Home×Cluster×Scenario, then mean over Homes per Cluster.
    annual_cost = (cost_df.groupby(["Home", "H", "Cluster", "Scenario"])["NetCost"]
                          .sum().reset_index())
    # Diagnostic: show record count and sample values to verify no inflation
    _n = annual_cost.groupby(["Cluster","Scenario"]).size()
    print("\n[Diagnostic] Records per Cluster×Scenario (should = n_homes × n_H):")
    print(_n.unstack().to_string())
    print("\n[Diagnostic] Mean annual NetCost per Cluster×Scenario:")
    _sample = annual_cost.groupby(["Cluster","Scenario"])["NetCost"].mean().unstack()
    print(_sample.to_string(float_format=lambda x: f"{x:,.0f}"))
    print()
    mean_cost_cl = (annual_cost.groupby(["Cluster", "Scenario"])["NetCost"]
                               .mean().reset_index())

    # T0 baseline per Cluster (each cluster may have a different absolute cost)
    t0_by_cl = (mean_cost_cl[mean_cost_cl.Scenario == "T0"]
                .set_index("Cluster")["NetCost"])
    mean_cost_cl["CostChange"] = mean_cost_cl.apply(
        lambda r: r["NetCost"] - t0_by_cl[r["Cluster"]], axis=1)

    # Order correctly
    order_map = {s: i for i, s in enumerate(SCENARIOS)}
    mean_cost_cl["_o"] = mean_cost_cl["Scenario"].map(order_map)
    top_cl = (mean_cost_cl.sort_values(["Cluster","_o"])
                          .drop(columns="_o")
                          .reset_index(drop=True))

    # Grand-mean CostChange (for reference / paper_numbers compatibility)
    mean_cost_grand = (annual_cost.groupby("Scenario")["NetCost"]
                                  .mean().reset_index())  # Home×H already annual
    t0_grand = mean_cost_grand.loc[
        mean_cost_grand.Scenario == "T0", "NetCost"].values[0]
    mean_cost_grand["CostChange"] = mean_cost_grand["NetCost"] - t0_grand

    # P95 peak per Cluster×Scenario (consistent with per-cluster bars)
    # P95 over all Home×H×Month observations per Cluster×Scenario
    p95 = (peak_df.groupby(["Cluster", "Scenario"])["MonthlyPeak_kW"]
                  .quantile(0.95).reset_index()
                  .rename(columns={"MonthlyPeak_kW": "P95_kW"}))

    # top: per-cluster df with P95 merged on Cluster+Scenario
    top = top_cl.merge(p95, on=["Cluster", "Scenario"])

    # ── Bottom panel: DoD cost per Cluster ────────────────────────────────────
    annual_dod = (dod_df.groupby(["Home", "H", "Scenario", "Cluster"])["DoD"]
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
    nc       = len(clusters)

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1,
        figsize=(7.16, 3.8),   # IEEE two-column full width
        sharex=True,
        gridspec_kw={"hspace": 0.08, "height_ratios": [1, 1]},
        layout="constrained",
    )

    x       = np.arange(len(SCENARIOS), dtype=float)
    w_bar   = 0.72 / nc                             # group width 0.72, split by cluster
    offsets = np.linspace(-(nc-1)/2, (nc-1)/2, nc) * w_bar

    # ── Aggregate cost change per Cluster×Scenario from top df ───────────────
    # top df has CostChange as grand mean; we need per-cluster values from bot
    # Use the raw per-cluster annual cost stored in top_by_cluster if available,
    # otherwise fall back to the grand-mean CostChange for all clusters equally.
    # The aggregate() function must expose per-cluster cost; see note below.
    p95 = top["P95_kW"].values

    # ============================================================
    # TOP PANEL: grouped cost-change bars per cluster + P95 line
    # ============================================================
    ax_top2 = ax_top.twinx()

    all_vals = []
    for ci, cl in enumerate(clusters):
        sub  = top[top.Cluster == cl].set_index("Scenario")                if "Cluster" in top.columns else None
        vals = np.array([
            sub.loc[s, "CostChange"] if (sub is not None and s in sub.index)
            else top.loc[top.Scenario == s, "CostChange"].values[0]
            for s in SCENARIOS])
        all_vals.append(vals)
        ax_top.bar(x + offsets[ci], vals, width=w_bar,
                   color=CLUSTER_COLORS.get(cl, f"C{ci}"),
                   zorder=3, linewidth=0.45, edgecolor="#333333")

    ax_top.axhline(0, color="0.35", linewidth=0.6, zorder=4)

    # P95 lines — one dashed line per cluster, same colour as bars
    all_p95_vals = []
    for cl in clusters:
        sub_p95 = top[top.Cluster == cl].set_index("Scenario")
        p95_vals = np.array([
            sub_p95.loc[s, "P95_kW"] if s in sub_p95.index else np.nan
            for s in SCENARIOS])
        all_p95_vals.append(p95_vals)
        ax_top2.plot(x, p95_vals,
                     color=CLUSTER_COLORS.get(cl, "grey"),
                     linewidth=1.1, linestyle="--",
                     marker="o", markersize=3.5,
                     markeredgewidth=0.4, markeredgecolor="white",
                     markerfacecolor=CLUSTER_COLORS.get(cl, "grey"),
                     zorder=5, solid_capstyle="round")

    # grid & axes
    ax_top.yaxis.grid(True, linestyle=":", linewidth=0.4, color="0.72", zorder=0)
    ax_top.set_axisbelow(True)
    ax_top2.yaxis.grid(False)

    flat = np.concatenate(all_vals)
    abs_max = max(abs(flat.min()), abs(flat.max()), 1)
    ax_top.set_ylim(-abs_max * 1.45, abs_max * 1.45)
    flat_p95 = np.concatenate(all_p95_vals)
    p95_span = max(float(np.nanmax(flat_p95)) - float(np.nanmin(flat_p95)), 0.1)
    ax_top2.set_ylim(float(np.nanmin(flat_p95)) - p95_span * 0.5,
                     float(np.nanmax(flat_p95)) + p95_span * 0.9)

    ax_top.set_ylabel(r"$\Delta$ cost vs. $T_0$ [SEK/year]",
                      fontsize=10, labelpad=4)
    ax_top2.set_ylabel("Monthly P95 peak [kW]", fontsize=10, labelpad=6,
                       rotation=270, va="center")
    ax_top.tick_params(axis="y", labelsize=9)
    ax_top2.tick_params(axis="y", labelsize=9)
    ax_top.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax_top.text(0.005, 0.97, "(a)", transform=ax_top.transAxes,
                fontsize=9, va="top", fontweight="bold")
    ax_top.spines["left"].set_linewidth(0.55)
    ax_top.spines["bottom"].set_visible(False)
    ax_top2.spines["right"].set_linewidth(0.55)
    ax_top2.spines["top"].set_visible(False)

    # ============================================================
    # BOTTOM PANEL: DoD cost grouped bars by Cluster (unchanged)
    # ============================================================
    for ci, cl in enumerate(clusters):
        sub  = bot[bot.Cluster == cl].set_index("Scenario")
        vals = np.array([
            sub.loc[s, "DoD"] if s in sub.index else 0.0
            for s in SCENARIOS])
        ax_bot.bar(x + offsets[ci], vals, width=w_bar,
                   color=CLUSTER_COLORS.get(cl, f"C{ci}"),
                   zorder=3, linewidth=0.45, edgecolor="#333333")

    ax_bot.yaxis.grid(True, linestyle=":", linewidth=0.4, color="0.72", zorder=0)
    ax_bot.set_axisbelow(True)
    ax_bot.set_ylabel("DoD cost [SEK/year]", fontsize=10, labelpad=4)
    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels([f"$T_{{{s[1]}}}$" for s in SCENARIOS], fontsize=11)
    ax_bot.tick_params(axis="both", labelsize=9)
    ax_bot.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax_bot.text(0.005, 0.97, "(b)", transform=ax_bot.transAxes,
                fontsize=9, va="top", fontweight="bold")
    ax_bot.spines["left"].set_linewidth(0.55)
    ax_bot.spines["bottom"].set_linewidth(0.55)

    # ── Shared legend: one entry per cluster + marker-style guide ───────────
    shared_handles = [
        mpatches.Patch(facecolor=CLUSTER_COLORS.get(cl, f"C{i}"),
                       edgecolor="#333", linewidth=0.45,
                       label=f"Cl.\u2009{cl[-1]}")
        for i, cl in enumerate(clusters)
    ] + [
        Line2D([0], [0], color="0.4", linewidth=1.0, linestyle="-",
               label=r"Bars: $\Delta$ cost"),
        Line2D([0], [0], color="0.4", linewidth=1.0, linestyle="--",
               marker="o", markersize=3.5, markerfacecolor="0.4",
               label="Lines: P95 peak"),
    ]
    ax_bot.legend(handles=shared_handles, fontsize=8,
                  loc="upper center",
                  bbox_to_anchor=(0.5, -0.15),
                  ncol=len(shared_handles),
                  framealpha=1.0, facecolor="white", edgecolor="0.75",
                  handlelength=1.1, handletextpad=0.4,
                  borderpad=0.45, columnspacing=0.7)

    # ── Save ──────────────────────────────────────────────────────────────────
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