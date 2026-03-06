"""Extract key result CSVs from EEM26-v2 case folders or archives and aggregate them.

Improvements over the initial version:
- Portable path handling via CLI arguments (no hard-coded Windows paths).
- Factor definitions and case-name format match EEM26_create_cases_v2 /
  EEM26_execute_cases_v2 exactly.
- No undefined variables (use_cases / dict_base_cases removed).
- Reads result files directly from a Cases/ directory by default; also
  supports extraction from .zip / .7z / .rar archives when present.
- Produces aggregated output CSVs with per-case metadata columns.
"""

from __future__ import annotations

import argparse
import time
import zipfile
from itertools import product
from pathlib import Path

import pandas as pd

try:
    import py7zr
except ImportError:
    py7zr = None  # type: ignore[assignment]

try:
    import rarfile
except ImportError:
    rarfile = None  # type: ignore[assignment]

# === Defaults ===
DEFAULT_BASE_DIR = Path(__file__).resolve().parent

# === Factors (must match EEM26_create_cases_v2.py / EEM26_execute_cases_v2.py) ===
BASE_CASES = ["Home1"]
# FACTOR0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
FACTOR0 = ["ClusterC", "ClusterD"]
# FACTOR1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
FACTOR1 = ["H7", "H8"]
FACTOR2 = ["T0", "T1", "T2", "T3", "T4"]
# FACTOR2 = ["T0"]
FACTOR3 = ["wDoD"]
FACTOR4 = [
    # "Month1",
    # "Month2",
    # "Month3",
    # "Month4",
    # "Month5",
    # "Month6",
    # "Month7",
    "Month8",
    # "Month9",
    "Month10",
    # "Month11",
    # "Month12",
]

# Result file prefixes to extract / aggregate per case
EXTRACT_TARGETS = [
    "oM_Result_07_rEleOutputSummary",
    "oM_Result_01_rObjFunComponents",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract and aggregate EEM26-v2 result CSVs from case folders or archives."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help="Directory that contains the Cases folder (and optional archives).",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=None,
        help="Cases directory (defaults to <base-dir>/Cases).",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Output directory for aggregated CSVs (defaults to <base-dir>/Results).",
    )
    return parser.parse_args()


def build_case_name(base: str, f0: str, f1: str, f2: str, f3: str, f4: str) -> str:
    return f"{base}_{f2}_{f1}_{f0}_{f3}_{f4}"


def iter_case_combinations():
    return product(BASE_CASES, FACTOR0, FACTOR1, FACTOR2, FACTOR3, FACTOR4)


# ---------------------------------------------------------------------------
# Archive helpers
# ---------------------------------------------------------------------------

def find_archive(base_dir: Path, name: str) -> Path | None:
    for ext in [".zip", ".7z", ".rar"]:
        p = base_dir / f"{name}{ext}"
        if p.exists():
            return p
    return None


def _archive_names(archive: Path) -> set[str]:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as z:
            return set(z.namelist())
    if archive.suffix == ".7z":
        if py7zr is None:
            raise ImportError("py7zr is required to read .7z archives: pip install py7zr")
        with py7zr.SevenZipFile(archive, mode="r") as z:
            return set(z.getnames())
    if archive.suffix == ".rar":
        if rarfile is None:
            raise ImportError("rarfile is required to read .rar archives: pip install rarfile")
        with rarfile.RarFile(archive, "r") as z:
            return set(z.namelist())
    raise ValueError(f"Unsupported archive format: {archive.suffix}")


def _extract_from_archive(archive: Path, out_dir: Path, targets: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as z:
            for t in targets:
                z.extract(t, path=out_dir)
    elif archive.suffix == ".7z":
        if py7zr is None:
            raise ImportError("py7zr is required to read .7z archives: pip install py7zr")
        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extract(path=out_dir, targets=targets)
    elif archive.suffix == ".rar":
        if rarfile is None:
            raise ImportError("rarfile is required to read .rar archives: pip install rarfile")
        with rarfile.RarFile(archive, "r") as z:
            for t in targets:
                z.extract(t, path=out_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive.suffix}")


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def _read_result_csv(
    path: Path,
    case_name: str,
    f0: str,
    f1: str,
    f2: str,
    f3: str,
    f4: str,
) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path)
        df.insert(0, "Case", case_name)
        df.insert(1, "UC", f0)
        df.insert(2, "Charger", f1)
        df.insert(3, "Mode", f2)
        df.insert(4, "DoD", f3)
        df.insert(5, "Month", f4)
        return df
    except Exception as exc:
        print(f"  WARNING: Could not read {path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    cases_dir = (args.cases_dir or (base_dir / "Cases")).resolve()
    results_dir = (args.results_dir or (base_dir / "Results")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    collected: dict[str, list[pd.DataFrame]] = {t: [] for t in EXTRACT_TARGETS}
    missing: list[str] = []

    for base_case, f0, f1, f2, f3, f4 in iter_case_combinations():
        case = build_case_name(base_case, f0, f1, f2, f3, f4)
        case_folder = cases_dir / case

        for target_prefix in EXTRACT_TARGETS:
            fname = f"{target_prefix}_{case}.csv"
            direct_path = case_folder / fname

            # --- Try direct read from Cases folder first ---
            if direct_path.exists():
                df = _read_result_csv(direct_path, case, f0, f1, f2, f3, f4)
                if df is not None:
                    collected[target_prefix].append(df)
                    print(f"  OK (folder)  : {case}/{fname}")
                continue

            # --- Fall back to extracting from an archive ---
            archive = find_archive(base_dir, base_case)
            if archive is not None:
                archive_member = f"{case}/{fname}"
                try:
                    names = _archive_names(archive)
                    if archive_member in names:
                        _extract_from_archive(archive, cases_dir, [archive_member])
                        if direct_path.exists():
                            df = _read_result_csv(direct_path, case, f0, f1, f2, f3, f4)
                            if df is not None:
                                collected[target_prefix].append(df)
                                print(f"  OK (archive) : {case}/{fname}")
                            continue
                except Exception as exc:
                    print(f"  WARNING: Archive error for {archive.name}: {exc}")

            missing.append(f"{case}/{fname}")

    # --- Save aggregated results ---
    for target_prefix, frames in collected.items():
        if not frames:
            print(f"  WARNING: No data collected for {target_prefix}")
            continue
        combined = pd.concat(frames, ignore_index=True)
        out_file = results_dir / f"{target_prefix}_all_cases.csv"
        combined.to_csv(out_file, index=False)
        print(f"  Saved: {out_file} ({len(frames)} case(s), {len(combined)} rows)")

    if missing:
        print(f"\nMISSING ({len(missing)} file(s)):")
        for m in missing:
            print(f"  MISSING: {m}")

    elapsed = time.time() - t_start
    print(f"\nDone. Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
