import datetime
import pandas as pd
import traceback
from pathlib import Path
from itertools import product

import sys
sys.path.append(r"C:\Users\Erik\Documents\GitHub\el1xr_opt\src")

from el1xr_opt.Modules.oM_Sequence import routine
from el1xr_opt.Modules.oM_LoadCase import load_case

# === Base directories ===
BASE_DIR = Path(r"C:\Users\Erik\Desktop\WS2\MS3_exe\Sensitivity")
CASES_DIR = BASE_DIR / "Cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

# === Log file ===
LOG_FILE = BASE_DIR / "execution_log.csv"

LOG_COLUMNS = [
    "UC", "Charger", "Mode", "DoD", "Month", "Market",
    "Power", "Storage", "BiddingZone", "Price",
    "Case", "Status", "Timestamp", "Objective", "Error"
]

if not LOG_FILE.exists():
    pd.DataFrame(columns=LOG_COLUMNS).to_csv(LOG_FILE, index=False)

df_log = pd.read_csv(LOG_FILE)

# === Pre-compute successful cases as a set for O(1) lookup ===
completed_cases = set(df_log.loc[df_log["Status"] == "SUCCESS", "Case"].values)


def write_log(f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, case, status, fobj, error=""):
    """Delete old rows for this case and write fresh status."""
    global df_log, completed_cases
    df_log = df_log[df_log["Case"] != case]
    new_row = pd.DataFrame([{
        "UC": f0, "Charger": f1, "Mode": f2, "DoD": f3,
        "Month": f4, "Market": f5, "Power": f6, "Storage": f7,
        "BiddingZone": f8, "Price": f9, "Case": case,
        "Status": status, "Timestamp": "2025-01-01 00:00:00",
        "Objective": fobj, "Error": error
    }])
    df_log = pd.concat([df_log, new_row], ignore_index=True)
    df_log.to_csv(LOG_FILE, index=False)
    # Keep the set in sync
    if status == "SUCCESS":
        completed_cases.add(case)
    else:
        completed_cases.discard(case)


# === Factors definition ===
base_cases = ["Home2"]
factor0 = ["UC1"]
factor1 = ["EV_01", "EV_02", "EV_03", "EV_04", "EV_05", "EV_06", "EV_07", "EV_08", "EV_09", "EV_10"]
# factor1 = ["EV_03"]
factor2 = ["V1G", "V2G"]
# factor2 = ["V2G"]
factor3 = ["woDoD"]
factor4 = ["Month1", "Month2", "Month3", "Month4", "Month5", "Month6",
           "Month7", "Month8", "Month9", "Month10", "Month11", "Month12"]
# factor4 = ["Month11"]
factor5 = ["DayAhead", "DayAhead&FCR-D", "DayAhead&FCR-N"]
# factor5 = ["DayAhead&FCR-D"]
factor6 = ["Power-11"]
factor7 = ["Storage-70"]
factor8 = ["BZ-SE3"]
factor9 = ["Price-High"]

# === Abbreviations ===
abbrev = {
    "woDoD": "woD", "wDoD": "wD",
    "Month1": "M01", "Month2": "M02", "Month3": "M03", "Month4": "M04",
    "Month5": "M05", "Month6": "M06", "Month7": "M07", "Month8": "M08",
    "Month9": "M09", "Month10": "M10", "Month11": "M11", "Month12": "M12",
    "DayAhead": "DA", "FCR-D": "FD", "FCR-N": "FN",
    "DayAhead&FCR-D": "DAFD", "DayAhead&FCR-N": "DAFN",
    "Power-11": "P11", "Power-22": "P22",
    "Storage-70": "S70", "Storage-50": "S50", "Storage-100": "S100",
    "BZ-SE1": "SE1", "BZ-SE2": "SE2", "BZ-SE3": "SE3", "BZ-SE4": "SE4",
    "Price-Medium": "PM", "Price-High": "PH",
}

# Pre-compute abbreviated factor values (avoid dict lookup every iteration)
short_f3 = {f: abbrev.get(f, f) for f in factor3}
short_f4 = {f: abbrev.get(f, f) for f in factor4}
short_f5 = {f: abbrev.get(f, f) for f in factor5}
short_f6 = {f: abbrev.get(f, f) for f in factor6}
short_f7 = {f: abbrev.get(f, f) for f in factor7}
short_f8 = {f: abbrev.get(f, f) for f in factor8}
short_f9 = {f: abbrev.get(f, f) for f in factor9}

# Pre-filter invalid combos: V1G + (FCR-D or FCR-N)
SKIP_FCR = {"FCR-D", "FCR-N"}

# === Main loop ===
for base, f0, f1, f2, f3, f4, f5, f6, f7, f8, f9 in product(
    base_cases, factor0, factor1, factor2, factor3, factor4, factor5,
    factor6, factor7, factor8, factor9
):
    if f2 == "V1G" and f5 in SKIP_FCR:
        continue

    case_name = f"{base}_{short_f5[f5]}_{short_f4[f4]}_{f0}_{f1}_{f2}_{short_f3[f3]}_{short_f6[f6]}_{short_f7[f7]}_{short_f8[f8]}_{short_f9[f9]}"

    # O(1) set lookup instead of filtering entire DataFrame
    if case_name in completed_cases:
        print(f"⏭️ Skipping {case_name} — already successful.\n")
        continue

    print(f"\n▶️ Running: {case_name}")

    data = dict(
        dir=CASES_DIR,
        case=case_name,
        solver="gurobi",
        date=datetime.datetime(2025, 1, 1, 0, 0),
        rawresults="False",
        plots="True",
        indlog="False",
    )

    try:
        model = routine(**data)

        tc1 = model.SolverResults1.solver.termination_condition
        tc2 = model.SolverResults2.solver.termination_condition
        print(f"Solver termination condition in the second execution: {tc2}")

        if tc1 != "optimal":
            print(f"❌ INFEASIBLE: {case_name} - Termination condition: {tc1}")
            fobj = round(model.eTotalSCost.expr(), 2) if tc2 == "optimal" else model.eTotalSCost.expr()
            err = f"Termination condition: {tc2 if tc2 == 'optimal' else tc1}"
            write_log(f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, case_name, "FAILED", fobj, error=err)
        else:
            print(f"✔ SUCCESS: {case_name}")
            write_log(f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, case_name, "SUCCESS", round(model.eTotalSCost.expr(), 2))

    except Exception:
        err_msg = traceback.format_exc()
        print(f"❌ FAILED: {case_name}\n{err_msg}")
        write_log(f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, case_name, "FAILED", 0, error=err_msg)

print("\n🏁 Process finished. Check execution_log.csv for results.")