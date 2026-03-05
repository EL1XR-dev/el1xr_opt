"""Execute generated EEM26 cases and keep a resilient execution log."""

from __future__ import annotations

import argparse
import datetime
import sys
import traceback
from itertools import product
from pathlib import Path

import pandas as pd

DEFAULT_BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SRC_DIR = Path(__file__).resolve().parents[2] / "src"

LOG_COLUMNS = ["UC", "Charger", "Mode", "DoD", "Month", "Case", "Status", "Timestamp", "Objective", "Error"]

# === Factors ===
BASE_CASES = ["Home1"]
FACTOR0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
FACTOR1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
FACTOR2 = ["T0", "T1", "T2", "T3", "T4"]
FACTOR3 = ["woDoD"]
FACTOR4 = [
    "Month1",
    "Month2",
    "Month3",
    "Month4",
    "Month5",
    "Month6",
    "Month7",
    "Month8",
    "Month9",
    "Month10",
    "Month11",
    "Month12",
]

ABBREV = {"woDoD": "woD", "wDoD": "wD"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute EEM26 case runs.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR, help="Directory containing Cases folder and execution log.")
    parser.add_argument("--cases-dir", type=Path, default=None, help="Case directory (defaults to <base-dir>/Cases).")
    parser.add_argument("--log-file", type=Path, default=None, help="Execution log CSV file.")
    parser.add_argument("--src-dir", type=Path, default=DEFAULT_SRC_DIR, help="Project src directory to import el1xr_opt modules.")
    parser.add_argument("--solver", default="gurobi", help="Solver name passed to routine().")
    parser.add_argument("--plots", default="True", help="plots flag passed to routine().")
    parser.add_argument("--rawresults", default="False", help="rawresults flag passed to routine().")
    parser.add_argument("--indlog", default="False", help="indlog flag passed to routine().")
    parser.add_argument("--force-rerun", action="store_true", help="Run even if case is already SUCCESS in execution log.")
    return parser.parse_args()


def _now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_objective(model) -> str | float:
    try:
        if hasattr(model, "eTotalSCost"):
            value = model.eTotalSCost.expr()
            try:
                return round(float(value), 2)
            except Exception:
                return str(value)
    except Exception:
        pass
    return ""


def initialize_log(log_file: Path) -> pd.DataFrame:
    if not log_file.exists():
        pd.DataFrame(columns=LOG_COLUMNS).to_csv(log_file, index=False)

    df_log = pd.read_csv(log_file)
    missing_columns = [column for column in LOG_COLUMNS if column not in df_log.columns]
    for column in missing_columns:
        df_log[column] = ""
    return df_log[LOG_COLUMNS]


def write_log(df_log: pd.DataFrame, log_file: Path, *, f0: str, f1: str, f2: str, f3: str, f4: str, case: str, status: str, objective: str | float = "", error: str = "") -> pd.DataFrame:
    case = str(case)
    df_log = df_log[df_log["Case"].astype(str) != case]

    new_row = pd.DataFrame(
        [
            {
                "UC": f0,
                "Charger": f1,
                "Mode": f2,
                "DoD": f3,
                "Month": f4,
                "Case": case,
                "Status": status,
                "Timestamp": _now_ts(),
                "Objective": objective,
                "Error": error,
            }
        ]
    )

    updated = pd.concat([df_log, new_row], ignore_index=True)
    updated.to_csv(log_file, index=False)
    return updated


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    cases_dir = (args.cases_dir or (base_dir / "Cases")).resolve()
    log_file = (args.log_file or (base_dir / "execution_log.csv")).resolve()

    if not cases_dir.exists():
        raise FileNotFoundError(f"Cases directory not found: {cases_dir}")

    src_dir = args.src_dir.resolve()
    if str(src_dir) not in sys.path:
        sys.path.append(str(src_dir))

    from el1xr_opt.Modules.oM_Sequence import routine

    df_log = initialize_log(log_file)
    completed_cases = set(df_log.loc[df_log["Status"] == "SUCCESS", "Case"].astype(str).values)
    for base_case, f0, f1, f2, f3, f4 in product(BASE_CASES, FACTOR0, FACTOR1, FACTOR2, FACTOR3, FACTOR4):
        case_name = f"{base_case}_{f2}_{f1}_{f0}_{f3}_{f4}"

        if (not args.force_rerun) and case_name in completed_cases:
            print(f"⏭️ Skipping {case_name} — already successful")
            continue

        print(f"▶️ Running: {case_name}")
        run_data = {
            "dir": cases_dir,
            "case": case_name,
            "solver": args.solver,
            "date": datetime.datetime(2025, 1, 1, 1, 0),
            "rawresults": args.rawresults,
            "plots": args.plots,
            "indlog": args.indlog,
        }

        df_log = write_log(df_log, log_file, f0=f0, f1=f1, f2=f2, f3=f3, f4=f4, case=case_name, status="RUNNING")

        try:
            model = routine(**run_data)
            termination = getattr(model.SolverResults1.solver, "termination_condition", None)
            objective = _safe_objective(model)

            if str(termination) != "optimal":
                error_msg = f"Termination condition: {termination}"
                print(f"❌ FAILED: {case_name} - {error_msg}")
                df_log = write_log(
                    df_log,
                    log_file,
                    f0=f0,
                    f1=f1,
                    f2=f2,
                    f3=f3,
                    f4=f4,
                    case=case_name,
                    status="FAILED",
                    objective=objective,
                    error=error_msg,
                )
                completed_cases.discard(case_name)
            else:
                print(f"✅ SUCCESS: {case_name}")
                df_log = write_log(
                    df_log,
                    log_file,
                    f0=f0,
                    f1=f1,
                    f2=f2,
                    f3=f3,
                    f4=f4,
                    case=case_name,
                    status="SUCCESS",
                    objective=objective,
                )
                completed_cases.add(case_name)

        except Exception:
            error_msg = traceback.format_exc()
            print(f"❌ FAILED: {case_name}\n{error_msg}")
            df_log = write_log(
                df_log,
                log_file,
                f0=f0,
                f1=f1,
                f2=f2,
                f3=f3,
                f4=f4,
                case=case_name,
                status="FAILED",
                error=error_msg,
            )
            completed_cases.discard(case_name)

    print(f"🏁 Process finished. Check log at: {log_file}")


if __name__ == "__main__":
    main()
