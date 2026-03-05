"""Execute generated EEM26 cases and keep a resilient execution log."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import sys
import traceback
from itertools import product
from pathlib import Path

import pandas as pd

DEFAULT_BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SRC_DIR = Path(__file__).resolve().parents[2] / "src"

LOG_COLUMNS = ["UC", "Charger", "Mode", "DoD", "Month", "Case", "Status", "Timestamp", "Objective", "Error"]

# === Factors definition ===
BASE_CASES = ["Home1"]
FACTOR0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
# FACTOR1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
FACTOR1 = ["H1"]
# FACTOR2 = ["T0", "T1", "T2", "T3", "T4"]
FACTOR2 = ["T0"]
FACTOR3 = ["wDoD"]
FACTOR4 = [
    # "Month1",
    # "Month2",
    "Month3",
    # "Month4",
    # "Month5",
    # "Month6",
    # "Month7",
    # "Month8",
    # "Month9",
    # "Month10",
    # "Month11",
    # "Month12",
]

ABBREV = {"woDoD": "woD", "wDoD": "wD"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute EEM26 case runs.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR, help="Directory containing Cases folder and execution log.")
    parser.add_argument("--cases-dir", type=Path, default=None, help="Case directory (defaults to <base-dir>/Cases).")
    parser.add_argument("--log-file", type=Path, default=None, help="Execution log CSV file.")
    parser.add_argument("--src-dir", type=Path, default=DEFAULT_SRC_DIR, help="Project src directory to import el1xr_opt modules.")
    parser.add_argument("--solver", default="highs", help="Solver name passed to routine().")
    parser.add_argument("--plots", default="True", help="plots flag passed to routine().")
    parser.add_argument("--rawresults", default="False", help="rawresults flag passed to routine().")
    parser.add_argument("--indlog", default="False", help="indlog flag passed to routine().")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes used to run cases in parallel.")
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


def _run_case_worker(*, src_dir: Path, run_data: dict, f0: str, f1: str, f2: str, f3: str, f4: str, case_name: str) -> dict:
    if str(src_dir) not in sys.path:
        sys.path.append(str(src_dir))

    from el1xr_opt.Modules.oM_Sequence import routine

    try:
        model = routine(**run_data)
        termination = getattr(model.SolverResults1.solver, "termination_condition", None)
        objective = _safe_objective(model)

        if str(termination) != "optimal":
            return {
                "f0": f0,
                "f1": f1,
                "f2": f2,
                "f3": f3,
                "f4": f4,
                "case_name": case_name,
                "status": "FAILED",
                "objective": objective,
                "error": f"Termination condition: {termination}",
            }

        return {
            "f0": f0,
            "f1": f1,
            "f2": f2,
            "f3": f3,
            "f4": f4,
            "case_name": case_name,
            "status": "SUCCESS",
            "objective": objective,
            "error": "",
        }

    except Exception:
        return {
            "f0": f0,
            "f1": f1,
            "f2": f2,
            "f3": f3,
            "f4": f4,
            "case_name": case_name,
            "status": "FAILED",
            "objective": "",
            "error": traceback.format_exc(),
        }


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    cases_dir = (args.cases_dir or (base_dir / "Cases")).resolve()
    log_file = (args.log_file or (base_dir / "execution_log.csv")).resolve()

    if not cases_dir.exists():
        raise FileNotFoundError(f"Cases directory not found: {cases_dir}")

    src_dir = args.src_dir.resolve()

    if args.workers < 1:
        raise ValueError("--workers must be >= 1")

    df_log = initialize_log(log_file)
    completed_cases = set(df_log.loc[df_log["Status"] == "SUCCESS", "Case"].astype(str).values)
    pending_cases: list[tuple[str, str, str, str, str, str, dict]] = []
    for base_case, f0, f1, f2, f3, f4 in product(BASE_CASES, FACTOR0, FACTOR1, FACTOR2, FACTOR3, FACTOR4):
        case_name = f"{base_case}_{f2}_{f1}_{f0}_{f3}_{f4}"

        if (not args.force_rerun) and case_name in completed_cases:
            print(f"⏭️ Skipping {case_name} — already successful")
            continue

        run_data = {
            "dir": cases_dir,
            "case": case_name,
            "solver": args.solver,
            "date": datetime.datetime(2025, 1, 1, 1, 0),
            "rawresults": args.rawresults,
            "plots": args.plots,
            "indlog": args.indlog,
        }
        pending_cases.append((f0, f1, f2, f3, f4, case_name, run_data))

    if not pending_cases:
        print("🏁 No pending cases to run.")
        return

    if args.workers == 1:
        print(f"ℹ️ Running {len(pending_cases)} case(s) sequentially")
        for f0, f1, f2, f3, f4, case_name, run_data in pending_cases:
            print(f"▶️ Running: {case_name}")
            df_log = write_log(df_log, log_file, f0=f0, f1=f1, f2=f2, f3=f3, f4=f4, case=case_name, status="RUNNING")
            result = _run_case_worker(src_dir=src_dir, run_data=run_data, f0=f0, f1=f1, f2=f2, f3=f3, f4=f4, case_name=case_name)

            if result["status"] == "SUCCESS":
                print(f"✅ SUCCESS: {case_name}")
                completed_cases.add(case_name)
            else:
                print(f"❌ FAILED: {case_name}\n{result['error']}")
                completed_cases.discard(case_name)

            df_log = write_log(
                df_log,
                log_file,
                f0=f0,
                f1=f1,
                f2=f2,
                f3=f3,
                f4=f4,
                case=case_name,
                status=result["status"],
                objective=result["objective"],
                error=result["error"],
            )
    else:
        print(f"ℹ️ Running {len(pending_cases)} case(s) with {args.workers} worker process(es)")
        future_to_case = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            for f0, f1, f2, f3, f4, case_name, run_data in pending_cases:
                print(f"▶️ Queued: {case_name}")
                df_log = write_log(df_log, log_file, f0=f0, f1=f1, f2=f2, f3=f3, f4=f4, case=case_name, status="RUNNING")
                future = executor.submit(
                    _run_case_worker,
                    src_dir=src_dir,
                    run_data=run_data,
                    f0=f0,
                    f1=f1,
                    f2=f2,
                    f3=f3,
                    f4=f4,
                    case_name=case_name,
                )
                future_to_case[future] = case_name

            for future in concurrent.futures.as_completed(future_to_case):
                case_name = future_to_case[future]
                result = future.result()

                if result["status"] == "SUCCESS":
                    print(f"✅ SUCCESS: {case_name}")
                    completed_cases.add(case_name)
                else:
                    print(f"❌ FAILED: {case_name}\n{result['error']}")
                    completed_cases.discard(case_name)

                df_log = write_log(
                    df_log,
                    log_file,
                    f0=result["f0"],
                    f1=result["f1"],
                    f2=result["f2"],
                    f3=result["f3"],
                    f4=result["f4"],
                    case=case_name,
                    status=result["status"],
                    objective=result["objective"],
                    error=result["error"],
                )

    print(f"🏁 Process finished. Check log at: {log_file}")


if __name__ == "__main__":
    main()
