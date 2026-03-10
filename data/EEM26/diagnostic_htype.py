"""
diagnostic_htype.py
===================
Splits results by house type:
  Apartments    : H1–H5  (hh_id 1–5)
  Single-family : H6–H10 (hh_id 6–10)

Prints a comparison table for BESS throughput, V2G rate, and net cost
change vs T0, broken down by house type × scenario.
No figures — just numbers to decide if the split is worth plotting.

Run:
    python diagnostic_htype.py --root "C:/Users/erikal/EEM26/Results"
"""

import argparse, os, re
import numpy as np
import pandas as pd

DIR_PATT  = re.compile(
    r"Home(\d+)_(T\d+)_H(\d+)_(Cluster[A-Z])_wDoD_Month(\d+)")
BESS_COL  = ("Production/Discharge [kWh]", "BESS")
EV_COL    = ("Production/Discharge [kWh]", "EV")
BUY_COL   = ("Electricity Buy [kWh]", "Node1")
EXCL_COST = {"Depth of Discharge Cost", "Network Fixed Cost"}
SCENARIOS = ["T0", "T1", "T2", "T3", "T4"]


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
            home_id, scenario, hh_id, cluster, month = m.groups()
            run_path = os.path.join(home_path, run_dir)
            row = {"Home": int(home_id), "Scenario": scenario,
                   "Cluster": cluster, "Month": int(month),
                   "HH": int(hh_id),
                   # H1-5 = apartment, H6-10 = single-family
                   "HType": "Apartment" if int(hh_id) <= 5 else "SingleFamily"}

            f01 = os.path.join(run_path,
                f"oM_Result_01_rObjFunComponents_{run_dir}.csv")
            if os.path.isfile(f01):
                try:
                    df = pd.read_csv(f01)
                    df["SEK"] = pd.to_numeric(df["SEK"], errors="coerce").fillna(0)
                    row["NetCost"] = df.loc[
                        ~df["Component"].isin(EXCL_COST), "SEK"].sum()
                except Exception as e:
                    print(f"  skip {f01}: {e}")

            f07 = os.path.join(run_path,
                f"oM_Result_07_rEleOutputSummary_{run_dir}.csv")
            if os.path.isfile(f07):
                try:
                    df   = pd.read_csv(f07, header=[0, 1])
                    bess = pd.to_numeric(df[BESS_COL], errors="coerce").fillna(0)
                    ev   = pd.to_numeric(df[EV_COL],   errors="coerce").fillna(0)
                    row["BESS_kWh"]    = (bess[bess>0].sum() +
                                          bess[bess<0].abs().sum()) / 2
                    row["V2G_hours"]   = int((ev > 0).sum())
                    row["total_hours"] = len(ev)
                except Exception as e:
                    print(f"  skip {f07}: {e}")

            rows.append(row)
    return pd.DataFrame(rows)


def report(df):
    SEP  = "─" * 78
    THIN = "·" * 78

    # Annual per Home × Cluster × Scenario × HType
    ann = (df.groupby(["Home","Cluster","Scenario","HType"])
             .agg(BESS_kWh    = ("BESS_kWh",    "sum"),
                  V2G_hours   = ("V2G_hours",   "sum"),
                  total_hours = ("total_hours", "sum"),
                  NetCost     = ("NetCost",     "sum"))
             .reset_index())
    ann["V2G_rate"] = ann["V2G_hours"] / ann["total_hours"] * 100

    # Mean over Home×Cluster pairs per Scenario × HType
    mean = (ann.groupby(["Scenario","HType"])
               .agg(BESS_kWh = ("BESS_kWh","mean"),
                    V2G_rate = ("V2G_rate","mean"),
                    NetCost  = ("NetCost", "mean"))
               .reset_index())

    # Cost change vs T0 per HType
    for ht in mean["HType"].unique():
        t0 = mean.loc[(mean.Scenario=="T0") & (mean.HType==ht), "NetCost"].values[0]
        mask = mean["HType"] == ht
        mean.loc[mask, "CostChange"] = mean.loc[mask, "NetCost"] - t0

    print(SEP)
    print("BESS throughput [kWh/year]  —  Apartment (H1–H5) vs Single-family (H6–H10)")
    print(THIN)
    piv = mean.pivot(index="Scenario", columns="HType", values="BESS_kWh").loc[SCENARIOS]
    piv["Diff %"] = (piv["SingleFamily"] - piv["Apartment"]) / piv["Apartment"] * 100
    print(piv.to_string(float_format=lambda x: f"{x:,.0f}"))

    print()
    print(SEP)
    print("V2G utilisation rate [%]")
    print(THIN)
    piv2 = mean.pivot(index="Scenario", columns="HType", values="V2G_rate").loc[SCENARIOS]
    piv2["Diff pp"] = piv2["SingleFamily"] - piv2["Apartment"]
    print(piv2.to_string(float_format=lambda x: f"{x:.2f}"))

    print()
    print(SEP)
    print("Net cost change vs T0 [SEK/year]")
    print(THIN)
    piv3 = mean.pivot(index="Scenario", columns="HType", values="CostChange").loc[SCENARIOS]
    piv3["Diff SEK"] = piv3["SingleFamily"] - piv3["Apartment"]
    print(piv3.to_string(float_format=lambda x: f"{x:+,.0f}"))

    print()
    print(SEP)
    print("VERDICT GUIDANCE")
    print(THIN)
    # Compute max relative BESS difference across non-T0 scenarios
    diffs = piv["Diff %"].drop("T0").abs()
    max_bess_diff = diffs.max()
    print(f"  Max |BESS diff| across T1–T4 : {max_bess_diff:.1f} %")
    if max_bess_diff >= 20:
        print("  → Consistent gap ≥20% : WORTH PLOTTING as a separate figure")
    elif max_bess_diff >= 10:
        print("  → Moderate gap 10–20% : worth a sentence in the text, borderline for a figure")
    else:
        print("  → Small gap <10%      : mention as a limitation only, skip figure")
    print(SEP)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Results")
    args = ap.parse_args()

    print(f"Scanning: {args.root}")
    df = extract(args.root)
    print(f"  Records: {len(df)}\n")
    report(df)
