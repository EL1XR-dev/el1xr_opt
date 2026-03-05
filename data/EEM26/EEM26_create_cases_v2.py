"""Create EEM26 case folders and generate case-specific CSV inputs.

Improvements over the previous version:
- Path handling is portable via CLI arguments.
- Source files are read once per base case and reused from memory.
- CSV mutations are centralized in small helper functions.
- Missing rows/columns are handled defensively to avoid hard crashes.
- Script can optionally clean old case folders before generation.
"""

from __future__ import annotations

import argparse
import os
import shutil
from io import BytesIO
from itertools import product
from pathlib import Path
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Iterable

import pandas as pd

# === Defaults ===
DEFAULT_BASE_DIR = Path(__file__).resolve().parent
COPY_KEYWORDS = ("oM_Data", "oM_Dict")

# === Factors definition ===
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

DICT_RETAILER = {
    "H1": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H2": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H3": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H4": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H5": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H6": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H7": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H8": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H9": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H10": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
}

DICT_DOD = {
    "wDoD": {"DoDS1": 0.25, "DoDS2": 0.5, "DoDS3": 0.25, "DoDC1": 0.2, "DoDC2": 0.4, "DoDC3": 0.8},
    "woDoD": {"DoDS1": 0, "DoDS2": 0, "DoDS3": 0, "DoDC1": 0, "DoDC2": 0, "DoDC3": 0},
}

DICT_V2G = {
    "V2G": {"MaximumPower": 11, "MinimumPower": 0},
    "V1G": {"MaximumPower": 1e-5, "MinimumPower": 0},
}

DICT_POWER_PEAKS = {"T0": 3, "T1": 3, "T2": 3, "T3": 1, "T4": 1}
DICT_TARIFF_TYPE = {"T0": "Daily", "T1": "Daily", "T2": "Daily", "T3": "Hourly", "T4": "Daily"}

DICT_CLUSTER = {
    "ClusterA": {"Load": 1.0, "PV": 1.0, "BESS": 0.0, "EV": 0.0},
    "ClusterB": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": 0.0},
    "ClusterC": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": "V1G"},
    "ClusterD": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": "V2G"},
    "ClusterE": {"Load": 1.0, "PV": 0.0, "BESS": 0.0, "EV": 0.0},
}

DICT_MONTH_HOURS = {
    "Month1": (1, 744),
    "Month2": (745, 1416),
    "Month3": (1417, 2160),
    "Month4": (2161, 2880),
    "Month5": (2881, 3624),
    "Month6": (3625, 4344),
    "Month7": (4345, 5088),
    "Month8": (5089, 5832),
    "Month9": (5833, 6552),
    "Month10": (6553, 7296),
    "Month11": (7297, 8016),
    "Month12": (8017, 8736),
}

ABBREV = {"ClusterA": "ClA", "ClusterB": "ClB", "ClusterC": "ClC", "ClusterD": "ClD", "ClusterE": "ClE"}


def short(factor: str) -> str:
    return ABBREV.get(factor, factor)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create EEM26 case folders and CSV files.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR, help="Directory containing base-case folders.")
    parser.add_argument("--cases-dir", type=Path, default=None, help="Output cases directory (defaults to <base-dir>/Cases).")
    parser.add_argument("--clean", action="store_true", help="Remove existing case folders before writing new data.")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 1)),
        help="Number of parallel workers used to generate cases.",
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    return args


def preload_source_csvs(base_dir: Path, base_case: str) -> dict[str, bytes]:
    src_folder = base_dir / base_case
    if not src_folder.exists():
        return {}

    csv_files = [file for file in src_folder.glob("*.csv") if any(key in file.name for key in COPY_KEYWORDS)]
    return {file.name: file.read_bytes() for file in csv_files}


def read_and_set_index(csv_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(csv_bytes))
    unnamed_cols = [col for col in df.columns if "Unnamed" in col]
    if unnamed_cols:
        df.set_index(unnamed_cols, inplace=True)
        df.index.names = [None] * len(unnamed_cols)
    return df


def _safe_loc_set(df: pd.DataFrame, row: str, col: str, value: object) -> None:
    if row in df.index and col in df.columns:
        df.loc[row, col] = value


def modify_csv(csv_path: Path, df: pd.DataFrame, f0: str, f1: str, f2: str, f3: str, f4: str) -> None:
    fname = csv_path.name
    load = f"EleD_{f1[1:].zfill(2)}"
    pv = f"Solar_{f1[1:].zfill(2)}"
    ev = f"EV_{f1[1:].zfill(2)}"
    bess = "BESS_01"

    if "Option" in fname:
        _safe_loc_set(df, "Options", "IndBinGenOperat", 0)

    if "ElectricityDemand" in fname:
        df["InitialPeriod"] = 2045
        _safe_loc_set(df, load, "InitialPeriod", 2020)

    if "ElectricityGeneration" in fname:
        df["InitialPeriod"] = 2045
        if f0 in {"ClusterA", "ClusterB", "ClusterC", "ClusterD"}:
            _safe_loc_set(df, pv, "InitialPeriod", 2020)
        if f0 in {"ClusterB", "ClusterC", "ClusterD"}:
            _safe_loc_set(df, bess, "InitialPeriod", 2020)
        if f0 in {"ClusterC", "ClusterD"}:
            _safe_loc_set(df, ev, "InitialPeriod", 2020)
            ev_type = str(DICT_CLUSTER[f0]["EV"])
            v2g_settings = DICT_V2G[ev_type]
            for column_name, value in v2g_settings.items():
                _safe_loc_set(df, ev, column_name, value)

        if f3 == "wDoD":
            for column_name, value in DICT_DOD[f3].items():
                _safe_loc_set(df, bess, column_name, value)
                _safe_loc_set(df, ev, column_name, value)

    if "Parameter" in fname:
        _safe_loc_set(df, "Parameters", "NumberPowerPeaks", DICT_POWER_PEAKS[f2])

    if "ElectricityRetail" in fname:
        float_cols = ["Fastavgift", "Overforingsavgift", "EnergyTax", "PowerTariff", "Paslag", "Moms"]
        for column_name in float_cols:
            if column_name in df.columns:
                df[column_name] = pd.to_numeric(df[column_name], errors="coerce").astype(float)

        retailer_name = "EleR_01"
        df["InitialPeriod"] = 2045
        _safe_loc_set(df, retailer_name, "InitialPeriod", 2020)

        retail_values = DICT_RETAILER[f1]
        for column_name, value in retail_values.items():
            _safe_loc_set(df, retailer_name, column_name, value)
        _safe_loc_set(df, retailer_name, "TariffType", DICT_TARIFF_TYPE[f2])

        if f2 == "T1":
            _safe_loc_set(df, retailer_name, "PowerTariff", 0.0)
        elif f2 == "T2":
            _safe_loc_set(df, retailer_name, "PowerTariff", 32.5)
        elif f2 in {"T3", "T4"}:
            _safe_loc_set(df, retailer_name, "PowerTariff", 65.0)

    if "Duration" in fname and "Duration" in df.columns:
        start_hr, end_hr = DICT_MONTH_HOURS[f4]
        start_row = start_hr - 1
        num_rows = end_hr - start_row
        df["Duration"] = 0.0
        duration_col = df.columns.get_loc("Duration")
        df.iloc[start_row : start_row + num_rows, duration_col] = 1

    df.to_csv(csv_path, index=True)


def generate_case(
    base_case: str,
    f2: str,
    f1: str,
    f0: str,
    f3: str,
    f4: str,
    cases_dir: Path,
    clean: bool,
    cache: dict[str, bytes],
) -> tuple[str, str]:
    case_name = f"{base_case}_{short(f2)}_{f1}_{f0}_{f3}_{f4}"
    case_folder = cases_dir / case_name

    if clean and case_folder.exists():
        shutil.rmtree(case_folder)
    case_folder.mkdir(parents=True, exist_ok=True)

    for src_name, src_bytes in cache.items():
        new_name = src_name.replace(base_case, case_name)
        dest_file = case_folder / new_name
        if "oM_Data" in src_name:
            df = read_and_set_index(src_bytes)
            modify_csv(dest_file, df, f0, f1, f2, f3, f4)
        else:
            dest_file.write_bytes(src_bytes)

    return case_name, str(case_folder)


def iter_case_combinations() -> Iterable[tuple[str, str, str, str, str, str]]:
    return product(BASE_CASES, FACTOR2, FACTOR1, FACTOR0, FACTOR3, FACTOR4)


def run_parallel_generation(args: argparse.Namespace, cases_dir: Path, csv_cache: dict[str, dict[str, bytes]]) -> None:
    max_in_flight = max(args.workers * 2, 1)
    in_flight = set()
    combinations = iter_case_combinations()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for base_case, f2, f1, f0, f3, f4 in combinations:
            cache = csv_cache[base_case]
            if not cache:
                continue

            in_flight.add(executor.submit(generate_case, base_case, f2, f1, f0, f3, f4, cases_dir, args.clean, cache))
            if len(in_flight) < max_in_flight:
                continue

            done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                case_name, case_folder = future.result()
                print(f"✅ Case '{case_name}' generated in {case_folder}")

        while in_flight:
            done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                case_name, case_folder = future.result()
                print(f"✅ Case '{case_name}' generated in {case_folder}")


def run_sequential_generation(args: argparse.Namespace, cases_dir: Path, csv_cache: dict[str, dict[str, bytes]]) -> None:
    for base_case, f2, f1, f0, f3, f4 in iter_case_combinations():
        cache = csv_cache[base_case]
        if not cache:
            continue
        case_name, case_folder = generate_case(base_case, f2, f1, f0, f3, f4, cases_dir, args.clean, cache)
        print(f"✅ Case '{case_name}' generated in {case_folder}")


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    cases_dir = (args.cases_dir or (base_dir / "Cases")).resolve()
    cases_dir.mkdir(parents=True, exist_ok=True)

    csv_cache = {base_case: preload_source_csvs(base_dir, base_case) for base_case in BASE_CASES}

    for base_case in BASE_CASES:
        if not csv_cache[base_case]:
            print(f"⚠️ No matching CSV files found for {base_case} in {base_dir}")

    if args.workers == 1:
        run_sequential_generation(args, cases_dir, csv_cache)
    else:
        run_parallel_generation(args, cases_dir, csv_cache)


if __name__ == "__main__":
    main()
