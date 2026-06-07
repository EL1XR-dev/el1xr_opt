"""Build a small two-scenario LP case from H2VPP, for the Benders wiring test.

Two scenarios (sc01, sc02), each probability 0.5; the second is a duplicate of the
first (so the stochastic optimum equals the single-scenario one), which keeps the
data generation trivially correct while still giving Benders two blocks coupled by
the common investment decision. Unit commitment is relaxed (LP) so the operating
subproblems are LPs with valid duals for the cuts. Investment candidates from
H2VPP (BESS_01, Solar_01) are kept so the master has first-stage decisions.
"""
import os
import shutil

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(REPO, "data", "H2VPP", "Home1")
CASE = "Home1"
TRUNC = 24
RELAX = ["IndBinGenOperat", "IndBinGenRamps", "IndBinGenMinTime"]


def build(work):
    """Create the 2-scenario case under ``work/<CASE>`` and return the parent dir."""
    dst = os.path.join(work, CASE)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(BASE, dst)

    def path(stem):
        return os.path.join(dst, f"oM_Data_{stem}_{CASE}.csv")

    # relax UC -> LP
    op = pd.read_csv(path("Option"))
    for f in RELAX:
        if f in op.columns:
            op[f] = 0
    op.to_csv(path("Option"), index=False)

    # zero the FCR operating-reserve requirement so the operating model has complete
    # recourse w.r.t. investment (demand is always coverable by buy/ENS). Hard
    # reserve requirements would make low-investment subproblems infeasible, which
    # the optimality-cut-only Benders does not handle (feasibility cuts are a
    # follow-on). With this, every subproblem is feasible for any investment.
    rr = path("OperatingReserveRequire")
    if os.path.exists(rr):
        df = pd.read_csv(rr)
        for c in df.columns:
            if df[c].dtype.kind in "fi":
                df[c] = 0.0
        df.to_csv(rr, index=False)

    # make the case complete-recourse so any investment in [0,1] is feasible (the
    # candidates only reduce cost, never required to be feasible): a large grid-buy
    # limit (grid can always meet electricity demand), no hydrogen demand, and no
    # green-hydrogen matching. This lets the optimality-cut-only Benders validate.
    par = pd.read_csv(path("Parameter"))
    if "GreenH2Matching" in par.columns:
        par["GreenH2Matching"] = 0
    par.to_csv(path("Parameter"), index=False)
    # zero hydrogen demand (HydD1 column in the var demand files)
    for stem in ("VarMaxDemand", "VarMinDemand"):
        f = path(stem)
        df = pd.read_csv(f)
        if "HydD1" in df.columns:
            df["HydD1"] = 0.0
            df.to_csv(f, index=False)

    # add sc02 to the scenario dimension dict (the scenario SET is built from this)
    dscen = os.path.join(dst, f"oM_Dict_Scenario_{CASE}.csv")
    dd = pd.read_csv(dscen)
    if "sc02" not in dd.iloc[:, 0].values:
        dd = pd.concat([dd, pd.DataFrame({dd.columns[0]: ["sc02"]})], ignore_index=True)
        dd.to_csv(dscen, index=False)

    # scenario probabilities: sc01=0.5, sc02=0.5
    sc = pd.read_csv(path("Scenario"))
    i1 = sc.columns[1]                               # scenario index column
    sc["Probability"] = sc["Probability"].astype(float)
    row = sc[sc[i1] == "sc01"].iloc[0].copy()
    sc.loc[sc[i1] == "sc01", "Probability"] = 0.5
    row["Probability"] = 0.5
    row[i1] = "sc02"
    sc = pd.concat([sc, pd.DataFrame([row])], ignore_index=True)
    sc.to_csv(path("Scenario"), index=False)

    # every data file indexed by (period, scenario, loadlevel): duplicate the full
    # sc01 rows as sc02 (same load levels, so all files stay consistent). Detect by
    # 3 leading unnamed index columns.
    for fname in os.listdir(dst):
        if not (fname.startswith("oM_Data_") and fname.endswith(f"_{CASE}.csv")):
            continue
        fpath = os.path.join(dst, fname)
        head = pd.read_csv(fpath, nrows=1)
        if len([c for c in head.columns if "Unnamed" in str(c)]) != 3:
            continue                                  # not a (p,sc,n) time-series file
        df = pd.read_csv(fpath, header=0)
        c1 = df.columns[1]
        sc01 = df[df[c1] == "sc01"].copy()
        if sc01.empty:
            continue
        dup = sc01.copy()
        dup[c1] = "sc02"
        pd.concat([df, dup], ignore_index=True).to_csv(fpath, index=False)

    # truncate the horizon to TRUNC load levels via the Duration column (the proven
    # method: blank durations past TRUNC for each scenario), so the model uses a
    # short horizon while every file keeps all load levels.
    dpath = path("Duration")
    dur = pd.read_csv(dpath)
    c1, ccol = dur.columns[1], "Duration"
    for s in ("sc01", "sc02"):
        idx = dur.index[dur[c1] == s].tolist()
        for j in idx[TRUNC:]:
            dur.at[j, ccol] = np.nan
    dur.to_csv(dpath, index=False)
    return work
