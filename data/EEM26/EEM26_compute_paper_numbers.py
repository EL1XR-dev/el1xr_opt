"""
compute_paper_numbers.py  v2
============================
Computes every in-text placeholder in the Results section (26 values),
plus the three claim metrics for T2/T3/T4, and prints a ready-to-paste
LaTeX snippet for each.

Run:
    python compute_paper_numbers.py --root "C:/Users/erikal/EEM26/Results" --bess_cap 10.0
"""

import argparse, os, re
import numpy as np
import pandas as pd

EXCLUDE_COST = {"Depth of Discharge Cost", "Network Fixed Cost"}
BESS_COL     = ("Production/Discharge [kWh]", "BESS")
EV_COL       = ("Production/Discharge [kWh]", "EV")
BUY_COL      = ("Electricity Buy [kWh]", "Node1")
DT_COL       = ("Unnamed: 3_level_0", "Unnamed: 3_level_1")
DIR_PATT     = re.compile(
    r"Home(\d+)_(T\d+)_H(\d+)_(Cluster[A-Z])_wDoD_Month(\d+)")
SCENARIOS    = ["T0", "T1", "T2", "T3", "T4"]


# ── Extraction ────────────────────────────────────────────────────────────────
def extract(root):
    rows = []
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
            row = {"Home": int(home_id), "Scenario": scenario,
                   "Cluster": cluster, "Month": int(month)}

            # ── File 01: cost components ──────────────────────────────────────
            f01 = os.path.join(run_path,
                f"oM_Result_01_rObjFunComponents_{run_dir}.csv")
            if os.path.isfile(f01):
                try:
                    df = pd.read_csv(f01)
                    df["SEK"] = pd.to_numeric(
                        df["SEK"], errors="coerce").fillna(0)
                    row["NetCost"] = df.loc[
                        ~df["Component"].isin(EXCLUDE_COST), "SEK"].sum()
                    row["DoD"] = df.loc[
                        df["Component"] == "Depth of Discharge Cost",
                        "SEK"].sum()
                except Exception as e:
                    print(f"  skip {f01}: {e}")

            # ── File 07: hourly dispatch ──────────────────────────────────────
            f07 = os.path.join(run_path,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if os.path.isfile(f07):
                try:
                    df  = pd.read_csv(f07, header=[0, 1])
                    bess = pd.to_numeric(df[BESS_COL], errors="coerce").fillna(0)
                    ev   = pd.to_numeric(df[EV_COL],   errors="coerce").fillna(0)
                    buy  = pd.to_numeric(df[BUY_COL],  errors="coerce").fillna(0)

                    # BESS roundtrip throughput
                    row["BESS_kWh"] = (
                        bess[bess > 0].sum() + bess[bess < 0].abs().sum()
                    ) / 2.0

                    # V2G utilisation
                    row["V2G_hours"]   = int((ev > 0).sum())
                    row["total_hours"] = len(ev)

                    # Monthly grid-import peak
                    row["MonthlyPeak_kW"] = buy.max()

                    # T3 metric: BESS discharge fraction on non-top-3 days
                    top3_idx  = buy.nlargest(3).index
                    try:
                        dates     = pd.to_datetime(df[DT_COL].values).date
                        peak_days = set(pd.to_datetime(
                            df[DT_COL].iloc[top3_idx].values).date)
                        nonpeak   = pd.Series(
                            [d not in peak_days for d in dates])
                        disch     = bess[bess > 0]
                        total_d   = disch.sum()
                        row["BESS_disch_nonpeak_frac"] = (
                            bess[(bess > 0) & nonpeak].sum() / total_d
                            if total_d > 0 else np.nan)
                    except Exception:
                        row["BESS_disch_nonpeak_frac"] = np.nan

                    # T4 metric: peak concentration (max / mean-of-top-3)
                    top3_vals = buy.nlargest(3).values
                    row["PeakConc"] = (
                        top3_vals[0] / top3_vals.mean()
                        if top3_vals.mean() > 0 else np.nan)

                except Exception as e:
                    print(f"  skip {f07}: {e}")

            rows.append(row)
    return pd.DataFrame(rows)


# ── Aggregation ───────────────────────────────────────────────────────────────
def compute_all(df, bess_cap=10.0):
    R = {}   # results dict

    # Annual sums per Home × Scenario × Cluster
    ann = (df.groupby(["Home", "Scenario", "Cluster"])
             .agg(
                 BESS_kWh              = ("BESS_kWh",             "sum"),
                 V2G_hours             = ("V2G_hours",            "sum"),
                 total_hours           = ("total_hours",          "sum"),
                 NetCost               = ("NetCost",              "sum"),
                 DoD                   = ("DoD",                  "sum"),
                 BESS_disch_nonpeak_frac = ("BESS_disch_nonpeak_frac", "mean"),
                 PeakConc              = ("PeakConc",             "mean"),
             ).reset_index())
    ann["V2G_rate"] = ann["V2G_hours"] / ann["total_hours"] * 100

    def mn(sc, cl, col):
        """Mean over Homes for given Scenario × Cluster."""
        sub = ann[(ann.Scenario == sc) & (ann.Cluster == cl)]
        return sub[col].mean() if len(sub) else np.nan

    def mn_all(sc, col):
        """Mean over ALL Homes for a Scenario (all clusters)."""
        sub = ann[ann.Scenario == sc]
        return sub[col].mean() if len(sub) else np.nan

    # ── §A / §B: BESS and V2G per Scenario × Cluster ─────────────────────────
    for sc in SCENARIOS:
        for cl in ["B", "D"]:
            clk = f"Cluster{cl}"
            R[f"BESS_kWh_{sc}_Cl{cl}"] = mn(sc, clk, "BESS_kWh")
            R[f"V2G_rate_{sc}_Cl{cl}"] = mn(sc, clk, "V2G_rate")

    # % of theoretical maximum (T0, Cl-B)
    R["T0_ClB_pct_of_max"] = (
        R["BESS_kWh_T0_ClB"] / (bess_cap * 365) * 100)

    # % changes vs T0
    for sc in ["T1", "T2", "T3", "T4"]:
        for cl in ["B", "D"]:
            t0 = R[f"BESS_kWh_T0_Cl{cl}"]
            tx = R[f"BESS_kWh_{sc}_Cl{cl}"]
            R[f"{sc}_change_BESS_Cl{cl}_pct"] = (tx - t0) / t0 * 100

    # T2 recovery of suppressed flexibility
    for cl in ["B", "D"]:
        t0, t1, t2 = (R[f"BESS_kWh_T0_Cl{cl}"],
                      R[f"BESS_kWh_T1_Cl{cl}"],
                      R[f"BESS_kWh_T2_Cl{cl}"])
        R[f"T2_recovery_BESS_Cl{cl}_pct"] = (t2 - t0) / (t1 - t0) * 100

    v0, v1, v2 = (R["V2G_rate_T0_ClD"],
                  R["V2G_rate_T1_ClD"],
                  R["V2G_rate_T2_ClD"])
    R["T2_recovery_V2G_ClD_pct"] = (v2 - v0) / (v1 - v0) * 100

    # T3 non-peak day cycling fraction
    for sc in SCENARIOS:
        sub = ann[ann.Scenario == sc]
        R[f"NonPeakDayDischarge_{sc}_pct"] = (
            sub["BESS_disch_nonpeak_frac"].mean() * 100)

    # T4 peak concentration vs T0
    for sc in SCENARIOS:
        R[f"PeakConc_{sc}"] = ann[ann.Scenario == sc]["PeakConc"].mean()
    R["T4_conc_vs_T0"] = R["PeakConc_T4"] / R["PeakConc_T0"]

    # ── §C: costs ─────────────────────────────────────────────────────────────
    # Annual net cost per Home×Scenario (all clusters)
    ann_cost = (df.groupby(["Home", "Scenario"])["NetCost"]
                  .sum().reset_index())
    mean_c   = ann_cost.groupby("Scenario")["NetCost"].mean()
    t0c      = mean_c["T0"]
    for sc in SCENARIOS:
        R[f"MeanCost_{sc}"]         = mean_c[sc]
        R[f"CostChange_{sc}_SEK"]   = mean_c[sc] - t0c
        R[f"CostChange_{sc}_pct"]   = (mean_c[sc] - t0c) / abs(t0c) * 100
    R["T2_pct_of_T1_ceiling"] = (
        R["CostChange_T2_SEK"] / R["CostChange_T1_SEK"] * 100)

    # P95 peak per scenario
    p95 = df.groupby("Scenario")["MonthlyPeak_kW"].quantile(0.95)
    for sc in SCENARIOS:
        R[f"P95_kW_{sc}"] = p95[sc]

    # ── §C heterogeneity: Cluster D share of total savings under T2 ───────────
    # Savings = T0_cost - T2_cost per Home; sum for ClD vs sum for all
    ann_cost2 = (df.groupby(["Home", "Scenario", "Cluster"])["NetCost"]
                   .sum().reset_index())
    t0_by_home  = ann_cost2[ann_cost2.Scenario == "T0"][
        ["Home","Cluster","NetCost"]].rename(columns={"NetCost":"Cost_T0"})
    t2_by_home  = ann_cost2[ann_cost2.Scenario == "T2"][
        ["Home","Cluster","NetCost"]].rename(columns={"NetCost":"Cost_T2"})
    savings     = t0_by_home.merge(t2_by_home, on=["Home","Cluster"])
    savings["Saving"] = savings["Cost_T0"] - savings["Cost_T2"]
    # Only count positive savings (households that benefit)
    savings["Saving"] = savings["Saving"].clip(lower=0)
    total_saving  = savings["Saving"].sum()
    clD_saving    = savings[savings.Cluster == "ClusterD"]["Saving"].sum()
    R["ClD_savings_share_T2_pct"] = (
        clD_saving / total_saving * 100 if total_saving > 0 else np.nan)

    return R


# ── Report ────────────────────────────────────────────────────────────────────
def report(R):
    SEP  = "─" * 72
    THIN = "·" * 72
    out  = []

    def row(label, key, fmt=".1f", unit="", latex=""):
        v = R.get(key, float("nan"))
        s = (f"{v:{fmt}}" if not np.isnan(v) else "n/a") if isinstance(v, float) else str(v)
        tag = f"  ← \\textit{{{latex}}}" if latex else ""
        out.append(f"  {label:<52} {s:>9} {unit}{tag}")

    out.append(SEP)
    out.append("§A  BESS throughput and V2G suppression")
    out.append(THIN)
    for sc in SCENARIOS:
        row(f"BESS Cl-B {sc}",  f"BESS_kWh_{sc}_ClB", ",.0f", "kWh/yr",
            f"[{R.get(f'BESS_kWh_{sc}_ClB', 0):,.0f}\\,kWh]" if sc in ["T0","T1","T2"] else "")
        row(f"BESS Cl-D {sc}",  f"BESS_kWh_{sc}_ClD", ",.0f", "kWh/yr")
        row(f"V2G Cl-D  {sc}",  f"V2G_rate_{sc}_ClD",  ".2f", "%",
            f"[{R.get(f'V2G_rate_{sc}_ClD', 0):.1f}\\,\\%]" if sc in ["T0","T1","T2"] else "")
        out.append("")
    row("T0 Cl-B % of theoretical max",
        "T0_ClB_pct_of_max", ".1f", "%",
        f"[{R.get('T0_ClB_pct_of_max',0):.0f}]")

    out.append(SEP)
    out.append("§A  T2/T3/T4 % changes vs T0")
    out.append(THIN)
    for sc in ["T2","T3","T4"]:
        for cl in ["B","D"]:
            row(f"  {sc} Cl-{cl} change vs T0",
                f"{sc}_change_BESS_Cl{cl}_pct", "+.1f", "%",
                f"[{'+' if R.get(f'{sc}_change_BESS_Cl{cl}_pct',0)>=0 else ''}"
                f"{R.get(f'{sc}_change_BESS_Cl{cl}_pct',0):.0f}\\,\\%]")

    out.append(SEP)
    out.append("Claim 1 — T2 recovery of suppressed flexibility")
    out.append(THIN)
    row("T2 recovery BESS Cl-B (of T0→T1 gap)",
        "T2_recovery_BESS_ClB_pct", ".1f", "%")
    row("T2 recovery BESS Cl-D (of T0→T1 gap)",
        "T2_recovery_BESS_ClD_pct", ".1f", "%")
    row("T2 recovery V2G  Cl-D (of T0→T1 gap)",
        "T2_recovery_V2G_ClD_pct",  ".1f", "%")

    out.append(SEP)
    out.append("Claim 2 — T3 non-peak-day cycling (episodic flexibility)")
    out.append(THIN)
    for sc in SCENARIOS:
        row(f"  Non-peak-day discharge fraction {sc}",
            f"NonPeakDayDischarge_{sc}_pct", ".1f", "%")

    out.append(SEP)
    out.append("Claim 3 — T4 peak concentration vs T0  (>1 = sharper incentive)")
    out.append(THIN)
    for sc in SCENARIOS:
        row(f"  Peak concentration ratio {sc}",
            f"PeakConc_{sc}", ".3f", "")
    row("T4 / T0 concentration ratio",
        "T4_conc_vs_T0", ".3f", "×")

    out.append(SEP)
    out.append("§C  Annual cost changes")
    out.append(THIN)
    for sc in SCENARIOS:
        row(f"Mean annual cost {sc}",
            f"MeanCost_{sc}", ",.0f", "SEK/yr")
        row(f"  Δ vs T0",
            f"CostChange_{sc}_SEK", "+,.0f", "SEK/yr",
            f"[{R.get(f'CostChange_{sc}_SEK',0):+,.0f}\\,SEK]")
        row(f"  Δ vs T0 [%]",
            f"CostChange_{sc}_pct", "+.1f", "%",
            f"[{R.get(f'CostChange_{sc}_pct',0):+.1f}\\,\\%]")
        out.append("")
    row("T2 % of T1 ceiling recovered",
        "T2_pct_of_T1_ceiling", ".1f", "%",
        f"[{R.get('T2_pct_of_T1_ceiling',0):.0f}]")

    out.append(SEP)
    out.append("§C  P95 monthly peak")
    out.append(THIN)
    for sc in SCENARIOS:
        row(f"P95 peak {sc}",
            f"P95_kW_{sc}", ".2f", "kW",
            f"[{R.get(f'P95_kW_{sc}',0):.1f}\\,kW]")

    out.append(SEP)
    out.append("§C  Cluster D savings share under T2")
    out.append(THIN)
    row("Cl-D share of total positive savings T2",
        "ClD_savings_share_T2_pct", ".1f", "%",
        f"[{R.get('ClD_savings_share_T2_pct',0):.0f}]")

    out.append(SEP)
    out.append("")
    out.append("LaTeX snippets (copy directly into .tex):")
    out.append(THIN)

    snippets = [
        ("T0 Cl-B throughput",
         f"\\SI{{{R.get('BESS_kWh_T0_ClB',0):,.0f}}}{{\\kWh}}"),
        ("T0 Cl-B pct of max",
         f"{R.get('T0_ClB_pct_of_max',0):.0f}\\,\\%"),
        ("T0 V2G rate Cl-D",
         f"{R.get('V2G_rate_T0_ClD',0):.1f}\\,\\%"),
        ("T1 Cl-B throughput",
         f"\\SI{{{R.get('BESS_kWh_T1_ClB',0):,.0f}}}{{\\kWh}}"),
        ("T1 V2G Cl-D",
         f"{R.get('V2G_rate_T1_ClD',0):.1f}\\,\\%"),
        ("T2 Cl-B throughput",
         f"\\SI{{{R.get('BESS_kWh_T2_ClB',0):,.0f}}}{{\\kWh}}"),
        ("T2 change Cl-B vs T0",
         f"{R.get('T2_change_BESS_ClB_pct',0):+.0f}\\,\\%"),
        ("T2 V2G Cl-D",
         f"{R.get('V2G_rate_T2_ClD',0):.1f}\\,\\%"),
        ("T3 Cl-B throughput",
         f"\\SI{{{R.get('BESS_kWh_T3_ClB',0):,.0f}}}{{\\kWh}}"),
        ("T3 change Cl-B vs T0",
         f"{R.get('T3_change_BESS_ClB_pct',0):+.0f}\\,\\%"),
        ("T3 V2G Cl-D",
         f"{R.get('V2G_rate_T3_ClD',0):.1f}\\,\\%"),
        ("T4 Cl-B throughput",
         f"\\SI{{{R.get('BESS_kWh_T4_ClB',0):,.0f}}}{{\\kWh}}"),
        ("T4 change Cl-B vs T0",
         f"{R.get('T4_change_BESS_ClB_pct',0):+.0f}\\,\\%"),
        ("T1 cost change",
         f"\\num{{{R.get('CostChange_T1_SEK',0):+,.0f}}}~SEK/year "
         f"({R.get('CostChange_T1_pct',0):+.1f}\\,\\%)"),
        ("T2 cost change",
         f"\\num{{{R.get('CostChange_T2_SEK',0):+,.0f}}}~SEK/year "
         f"({R.get('CostChange_T2_pct',0):+.1f}\\,\\%)"),
        ("T2 pct of T1 ceiling",
         f"{R.get('T2_pct_of_T1_ceiling',0):.0f}\\,\\%"),
        ("T3 cost change",
         f"\\num{{{R.get('CostChange_T3_SEK',0):+,.0f}}}~SEK/year"),
        ("T4 cost change",
         f"\\num{{{R.get('CostChange_T4_SEK',0):+,.0f}}}~SEK/year"),
        ("P95 peak T0",
         f"{R.get('P95_kW_T0',0):.1f}~kW"),
        ("P95 peak T2",
         f"{R.get('P95_kW_T2',0):.1f}~kW"),
        ("Cl-D savings share T2",
         f"{R.get('ClD_savings_share_T2_pct',0):.0f}\\,\\%"),
        ("T2 BESS recovery (Cl-B)",
         f"{R.get('T2_recovery_BESS_ClB_pct',0):.0f}\\,\\%"),
        ("T3 non-peak discharge frac",
         f"{R.get('NonPeakDayDischarge_T3_pct',0):.0f}\\,\\%"),
        ("T4 conc ratio vs T0",
         f"{R.get('T4_conc_vs_T0',0):.2f}\\times"),
    ]
    for label, snippet in snippets:
        out.append(f"  {label:<38}  {snippet}")

    return "\n".join(out)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root",     default="Results")
    ap.add_argument("--bess_cap", default=10.0, type=float,
                    help="BESS capacity per household [kWh]")
    ap.add_argument("--out",      default="paper_numbers")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    df = extract(args.root)
    print(f"  Records: {len(df)}")

    R = compute_all(df, bess_cap=args.bess_cap)

    pd.DataFrame([{"metric": k, "value": v}
                  for k, v in R.items()]).to_csv(
        args.out + ".csv", index=False)

    report_str = report(R)
    print("\n" + report_str)
    with open(args.out + ".txt", "w", encoding="utf-8") as f:
        f.write(report_str)
    print(f"\nSaved: {args.out}.csv  and  {args.out}.txt")