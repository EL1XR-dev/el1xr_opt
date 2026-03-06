"""Extract EEM26 simulation result files from case archives.

Improvements over the previous version:
- Path handling is portable via CLI arguments.
- Factors and case-name format match EEM26_create_cases_v2 and EEM26_execute_cases_v2.
- Script is structured with a main() function and __main__ guard.
- Missing files are reported as warnings without aborting the run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import time
import zipfile
from itertools import product
from pathlib import Path

import py7zr
import rarfile

DEFAULT_BASE_DIR = Path(__file__).resolve().parent

# === Factors definition ===
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

RESULT_FILES = [
    "oM_Result_07_rEleOutputSummary",
    "oM_Result_01_rObjFunComponents",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract EEM26 result files from case archives.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR, help="Directory containing case archives.")
    parser.add_argument("--cases-dir", type=Path, default=None, help="Case directory (defaults to <base-dir>/Cases).")
    parser.add_argument("--results-dir", type=Path, default=None, help="Output directory (defaults to <base-dir>/Results).")
    return parser.parse_args()


def detect_parent_prefix(names: list[str]) -> str:
    """Return the common top-level directory prefix (with trailing '/'), or ''."""
    prefixes = {n.split("/")[0] for n in names if "/" in n}
    if len(prefixes) == 1:
        return prefixes.pop() + "/"
    return ""


def find_archive(base_dir: Path, base_case: str) -> Path | None:
    for ext in [".7z", ".zip", ".rar"]:
        path = base_dir / f"{base_case}{ext}"
        if path.exists():
            return path
    return None


def get_archive_names(archive_path: Path) -> list[str]:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            return z.namelist()
    elif archive_path.suffix == ".rar":
        with rarfile.RarFile(archive_path, "r") as z:
            return z.namelist()
    else:
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            return z.getnames()


def extract_files(archive_path: Path, out_dir: Path, targets: list[str]) -> None:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            for t in targets:
                z.extract(t, path=out_dir)
    elif archive_path.suffix == ".rar":
        with rarfile.RarFile(archive_path, "r") as z:
            for t in targets:
                z.extract(t, path=out_dir)
    else:
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            z.extract(path=out_dir, targets=targets)


def build_case_name(base_case: str, f0: str, f1: str, f2: str, f3: str, f4: str) -> str:
    return f"{base_case}_{f2}_{f1}_{f0}_{f3}_{f4}"


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    cases_dir = (args.cases_dir or (base_dir / "Cases")).resolve()
    results_dir = (args.results_dir or (base_dir / "Results")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    t_total_start = time.time()

    for base_case in BASE_CASES:
        print(f"\n{'='*60}")
        print(f"Processing base case: {base_case}")
        print(f"{'='*60}")

        archive_path = find_archive(cases_dir, base_case)
        print(f"  Searching for archive in: {cases_dir}")
        if archive_path is None:
            print(f"  WARNING: No archive found for {base_case}, skipping.")
            continue

        print(f"  Archive : {archive_path.name}")

        out_dir = results_dir / base_case
        out_dir.mkdir(parents=True, exist_ok=True)

        all_combos = list(product(FACTOR0, FACTOR1, FACTOR2, FACTOR3, FACTOR4))
        print(f"  Combinations : {len(all_combos)}")

        archive_names = get_archive_names(archive_path)
        prefix = detect_parent_prefix(archive_names)
        if prefix:
            print(f"  Archive prefix   : {prefix.rstrip('/')}/")

        targets = []
        for f0, f1, f2, f3, f4 in all_combos:
            case_name = build_case_name(base_case, f0, f1, f2, f3, f4)
            for result_file in RESULT_FILES:
                targets.append(f"{prefix}{case_name}/{result_file}_{case_name}.csv")

        print(f"  Files to extract : {len(targets)}")

        t_start = time.time()

        names_set = set(archive_names)
        missing = [t for t in targets if t not in names_set]
        if missing:
            print(f"  WARNING: {len(missing)} files not found in archive:")
            for m in missing:
                print(f"    MISSING: {m}")
            targets = [t for t in targets if t in names_set]

        if not targets:
            print(f"  WARNING: No files to extract for {base_case}.")
            continue

        print(f"  Extracting {len(targets)} files...")
        extract_files(archive_path, out_dir, targets)

        if prefix:
            parent_extracted = out_dir / prefix.rstrip("/")
            for item in parent_extracted.iterdir():
                shutil.move(str(item), str(out_dir / item.name))
            parent_extracted.rmdir()

        elapsed = time.time() - t_start
        print(f"  Done : {base_case} -> {out_dir}")
        print(f"  Time : {elapsed:.1f}s ({elapsed/60:.1f} min)")

    total_elapsed = time.time() - t_total_start
    print(f"\n{'='*60}")
    print("All base cases done!")
    print(f"Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
