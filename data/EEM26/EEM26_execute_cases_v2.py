import datetime
import pandas as pd
import traceback
from pathlib import Path
from itertools import product
import sys

sys.path.append(r"C:\Users\ealvarezq\Documents\GitHub\Comillas\Models\el1xr_opt\src")
from el1xr_opt.Modules.oM_Sequence import routine

# === Base directories ===
BASE_DIR = Path(r"C:\Users\ealvarezq\Documents\GitHub\Comillas\Models\el1xr_opt\data\EEM26")
CASES_DIR = BASE_DIR / "Cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

# === Log file (reduced columns) ===
LOG_FILE = BASE_DIR / "execution_log.csv"
LOG_COLUMNS = ["UC", "Charger", "Mode", "DoD", "Case", "Status", "Timestamp", "Objective", "Error"]

if not LOG_FILE.exists():
    pd.DataFrame(columns=LOG_COLUMNS).to_csv(LOG_FILE, index=False)

df_log = pd.read_csv(LOG_FILE)
completed_cases = set(df_log.loc[df_log["Status"] == "SUCCESS", "Case"].astype(str).values)

def _now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_objective(model):
    try:
        if hasattr(model, "eTotalSCost"):
            val = model.eTotalSCost.expr()
            try:
                return round(float(val), 2)
            except Exception:
                return str(val)
        return ""
    except Exception:
        return ""

def write_log(f0, f1, f2, f3, case, status, fobj="", error=""):
    global df_log, completed_cases
    case = str(case)

    df_log = df_log[df_log["Case"].astype(str) != case]

    new_row = pd.DataFrame([{
        "UC": f0, "Charger": f1, "Mode": f2, "DoD": f3,
        "Case": case, "Status": status, "Timestamp": _now_ts(),
        "Objective": fobj, "Error": error
    }])

    df_log = pd.concat([df_log, new_row], ignore_index=True)
    df_log.to_csv(LOG_FILE, index=False)

    if status == "SUCCESS":
        completed_cases.add(case)
    else:
        completed_cases.discard(case)

# === Factors (ONLY f0..f3) ===
base_cases = ["Home1"]
# factor0 = ["ClusterA"]
factor0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
factor1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
# factor1 = ["H1", "H6"]
factor2 = ["T0", "T1", "T2", "T3", "T4"]
factor3 = ["woDoD"]

abbrev = {"woDoD": "woD", "wDoD": "wD"}
short_f2 = {f: abbrev.get(f, f) for f in factor2}
short_f3 = {f: abbrev.get(f, f) for f in factor3}

# === Main loop (reduced) ===
for base, f0, f1, f2, f3 in product(base_cases, factor0, factor1, factor2, factor3):
    case_name = f"{base}_{short_f2[f2]}_{f1}_{f0}_{f3}"

    if case_name in completed_cases:
        print(f"⏭️ Skipping {case_name} — already successful.\n")
        continue

    print(f"\n▶️ Running: {case_name}")

    data = dict(
        dir=CASES_DIR,
        case=case_name,
        solver="gurobi",
        date=datetime.datetime(2025, 1, 1, 1, 0),  # keep if your pipeline expects it
        rawresults="False",
        plots="True",
        indlog="False",
    )

    write_log(f0, f1, f2, f3, case_name, "RUNNING", "")

    try:
        model = routine(**data)
        tc1 = getattr(model.SolverResults1.solver, "termination_condition", None)
        obj_val = _safe_objective(model)

        if str(tc1) != "optimal":
            err = f"Termination condition: {tc1}"
            print(f"❌ FAILED: {case_name} - {err}")
            write_log(f0, f1, f2, f3, case_name, "FAILED", obj_val, error=err)
        else:
            print(f"✔ SUCCESS: {case_name}")
            write_log(f0, f1, f2, f3, case_name, "SUCCESS", obj_val)

    except Exception:
        err_msg = traceback.format_exc()
        print(f"❌ FAILED: {case_name}\n{err_msg}")
        write_log(f0, f1, f2, f3, case_name, "FAILED", "", error=err_msg)

print("\n🏁 Process finished. Check execution_log.csv for results.")