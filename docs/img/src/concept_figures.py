"""Draw the illustrations of the Concepts pages as SVG files in docs/img.

The numbers are made up to show how a rule works; they are not results of a case.
Run from the repository root:  python docs/img/src/concept_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1]
BLUE, GREEN, ORANGE, RED, GREY = "#1565c0", "#2e7d32", "#ef6c00", "#c62828", "#757575"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "el1xr",
                     "axes.spines.top": False, "axes.spines.right": False})


def fcr_headroom():
    """A battery's FCR bids next to its operating point, and the energy that backs them."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(9.6, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})

    # (a) power: discharging at 3 kW out of 5 kW; charging leg at 0
    pmax, p = 5.0, 3.0
    ax.barh(1, pmax, color="#eeeeee", edgecolor=GREY, height=0.5)
    ax.barh(1, p, color=BLUE, height=0.5)
    ax.annotate("", xy=(pmax, 1.42), xytext=(p, 1.42), arrowprops=dict(arrowstyle="<->", color=GREEN))
    ax.text((p + pmax) / 2, 1.55, "up reserve\n≤ max. discharge − discharge", ha="center", va="bottom", color=GREEN, fontsize=9)
    ax.annotate("", xy=(0, 0.58), xytext=(p, 0.58), arrowprops=dict(arrowstyle="<->", color=ORANGE))
    ax.text(p / 2, 0.47, "down reserve ≤ discharge", ha="center", va="top", color=ORANGE, fontsize=9)
    ax.plot([p, p], [0.7, 1.3], color="black", lw=1.5)
    ax.text(p, 0.1, "operating point", ha="center", va="bottom", fontsize=8)
    ax.set_xlim(-0.2, pmax + 0.3); ax.set_ylim(-0.1, 2.3)
    ax.set_yticks([1]); ax.set_yticklabels(["discharge\nleg"])
    ax.set_xlabel("power (kW)")
    ax.set_title("(a) Headroom: reserve fits around the schedule", loc="left", fontsize=10)

    # (b) energy: inventory must back the up bid, free room the down bid, for the endurance time
    cap, inv = 10.0, 6.0
    bx.bar(0, cap, color="#eeeeee", edgecolor=GREY, width=0.5)
    bx.bar(0, inv, color=BLUE, width=0.5)
    up_need, down_need = 2.5, 2.0
    bx.bar(0.62, up_need, bottom=0, color=GREEN, width=0.18)
    bx.bar(0.62, down_need, bottom=cap - down_need, color=ORANGE, width=0.18)
    bx.text(0.78, up_need / 2, "stored energy ≥\nup bid × endurance ÷ η",
            va="center", fontsize=8.5, color=GREEN)
    bx.text(0.78, cap - down_need / 2, "free room ≥\nη × down bid × endurance",
            va="center", fontsize=8.5, color=ORANGE)
    bx.text(0, inv / 2, "stored\nenergy", ha="center", va="center", color="white", fontsize=9)
    bx.set_xlim(-0.4, 2.3); bx.set_ylim(0, cap * 1.05)
    bx.set_xticks([]); bx.set_ylabel("energy (kWh)")
    bx.spines["bottom"].set_visible(False)
    bx.set_title("(b) Endurance", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "concept_fcr_headroom.svg")
    plt.close(fig)


def storage_balance():
    """Inventory balance: the level follows the charge and discharge of each load level."""
    hours = np.arange(24)
    charge = np.where((hours >= 1) & (hours <= 6), 1.6, 0.0) + np.where((hours >= 11) & (hours <= 13), 1.5, 0.0)
    discharge = np.where((hours >= 17) & (hours <= 21), 2.4, 0.0) + np.where((hours >= 7) & (hours <= 8), 1.0, 0.0)
    eta_c, eta_d, start = 0.95, 0.95, 3.0
    level = start + np.cumsum(eta_c * charge - discharge / eta_d)
    assert 0.5 <= level.min() and level.max() <= 14.5, "the illustrated schedule must respect the limits"
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    ax.bar(hours, charge, color=GREEN, width=0.8, label="charge")
    ax.bar(hours, -discharge, color=ORANGE, width=0.8, label="discharge")
    ax.set_ylabel("power (kW)")
    ax.axhline(0, color=GREY, lw=0.8)
    bx = ax.twinx(); bx.spines["right"].set_visible(True)
    bx.step(np.r_[-0.5, hours + 0.5], np.r_[start, level], where="post", color=BLUE, lw=2, label="stored energy")
    bx.axhline(0.5, color=RED, ls="--", lw=1); bx.text(23.4, 0.55, "minimum", color=RED, ha="right", va="bottom", fontsize=8)
    bx.axhline(14.5, color=RED, ls="--", lw=1); bx.text(23.4, 14.45, "maximum", color=RED, ha="right", va="top", fontsize=8)
    bx.set_ylim(0, 15.5); bx.set_ylabel("stored energy (kWh)", color=BLUE)
    ax.set_xlim(-0.6, 23.6); ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("load level (hour)")
    lines = [h for h in ax.get_legend_handles_labels()[0]] + bx.get_legend_handles_labels()[0]
    ax.legend(lines, ["charge", "discharge", "stored energy"], loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, ncol=3)
    ax.set_ylim(-3.2, 3.8)
    fig.tight_layout()
    fig.savefig(OUT / "concept_storage_balance.svg")
    plt.close(fig)


def peak_tariff():
    """Monthly power tariff: the N largest hourly imports of the month set the charge."""
    rng = np.random.default_rng(7)
    days, n_peaks = 30, 3
    h = np.arange(24 * days)
    base = 2.0 + 1.2 * np.sin((h % 24 - 7) / 24 * 2 * np.pi) ** 2 + 0.25 * rng.standard_normal(h.size)
    base[(h % 24 >= 17) & (h % 24 <= 20)] += 1.2
    base[rng.choice(h.size, 6, replace=False)] += rng.uniform(1.0, 2.0, 6)
    imp = np.clip(base, 0.2, None)
    top = np.argsort(imp)[-n_peaks:]
    mean_top = imp[top].mean()
    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    ax.plot(h / 24, imp, color=BLUE, lw=0.7)
    ax.scatter(h[top] / 24, imp[top], color=RED, zorder=3, s=28, label=f"the {n_peaks} largest hourly imports")
    ax.axhline(mean_top, color=RED, ls="--", lw=1)
    ax.text(days, mean_top, " their mean × tariff\n = the month's peak charge", color=RED, va="center", fontsize=9)
    ax.set_xlim(0, days); ax.set_xlabel("day of the month"); ax.set_ylabel("grid import (kW)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "concept_peak_tariff.svg")
    plt.close(fig)


def green_h2_matching():
    """Green-hydrogen matching: each hour, the productive electrolyser draw is covered by renewables."""
    hours = np.arange(24)
    wind = 4.0 + 2.5 * np.sin((hours - 4) / 24 * 2 * np.pi) + np.where(hours > 18, -2.2, 0.0)
    wind = np.clip(wind, 0.3, None)
    draw = np.minimum(wind, 4.5) * 0.9
    standby = np.zeros(24)
    off = (hours >= 20) & (hours <= 22)
    draw[off] = 0.0
    standby[off] = 0.25
    assert np.all(draw <= wind + 1e-9), "the productive draw must stay within the renewable output"
    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    ax.fill_between(hours, wind, step="mid", color=GREEN, alpha=0.18, label="PPA renewable output: the most that can be allocated")
    ax.step(hours, wind, where="mid", color=GREEN, lw=1.5)
    ax.bar(hours, draw, color=BLUE, width=0.7, label="productive draw: must be matched")
    ax.bar(hours, standby, bottom=draw, color=ORANGE, width=0.7, label="standby draw: not matched")
    ax.set_xlim(-0.6, 23.6); ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("hour")
    ax.set_ylabel("power (MW)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "concept_green_h2_matching.svg")
    plt.close(fig)


if __name__ == "__main__":
    fcr_headroom()
    storage_balance()
    peak_tariff()
    green_h2_matching()
    print("written to", OUT)
