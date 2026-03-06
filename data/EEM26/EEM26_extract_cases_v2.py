import py7zr
import zipfile
import rarfile
import time
from pathlib import Path
from itertools import product

BASE_DIR = Path("C:/Users/erikal/EEM26")

# === Factors definition ===
BASE_CASES = ["Home1"]

abbrev = {
    "woDoD": "woD", "wDoD": "wD",
    "Month1": "M01",  "Month2": "M02",  "Month3": "M03",  "Month4": "M04",
    "Month5": "M05",  "Month6": "M06",  "Month7": "M07",  "Month8": "M08",
    "Month9": "M09",  "Month10": "M10", "Month11": "M11", "Month12": "M12",
    "DayAhead": "DA", "DayAhead&FCR-D": "DAFD", "DayAhead&FCR-N": "DAFN",
}

def short(f):
    return abbrev.get(f, f)

def is_extended(uc):
    return "_" in uc   # "UC1_woD_..." vs plain "UC1"

factor1 = ["EV_01","EV_02","EV_03","EV_04","EV_05",
            "EV_06","EV_07","EV_08","EV_09","EV_10"]
factor2 = ["V1G", "V2G"]
factor3 = ["woDoD"]
factor4 = ["Month1","Month2","Month3","Month4","Month5","Month6",
            "Month7","Month8","Month9","Month10","Month11","Month12"]
factor5 = ["DayAhead", "DayAhead&FCR-D", "DayAhead&FCR-N"]

RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def find_archive(base_dir, use_case):
    for ext in [".7z", ".zip", ".rar"]:
        path = base_dir / f"{use_case}{ext}"
        if path.exists():
            return path
    return None

def get_archive_names(archive_path):
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            return z.namelist()
    elif archive_path.suffix == ".rar":
        with rarfile.RarFile(archive_path, "r") as z:
            return z.namelist()
    else:
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            return z.getnames()

def extract_files(archive_path, out_dir, targets):
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

def build_case_name(base, use_case, f1, f2, f3, f4, f5):
    """
    Simple  (UC1):
        Home2_DayAhead_Month1_UC1_EV_01_V1G_woDoD
    Extended (UC1_woD_P11_S50_SE3_PM):
        Home2_DAFD_M01_UC1_EV_01_V1G_woD_P11_S50_SE3_PM
    """
    if is_extended(use_case):
        uc_root, uc_suffix = use_case.split("_", 1)
        return (f"{base}_{short(f5)}_{short(f4)}_{uc_root}_{f1}_{f2}"
                f"_{short(f3)}_{uc_suffix[4:]}")
    else:
        return f"{base}_{f5}_{f4}_{use_case}_{f1}_{f2}_{f3}"


# ─────────────────────────────────────────────────────────────────────────────
t_total_start = time.time()

for use_case in use_cases:
    print(f"\n{'='*60}")
    print(f"Processing use case: {use_case}")
    print(f"{'='*60}")

    archive_path = find_archive(BASE_DIR, use_case)
    if archive_path is None:
        print(f"  WARNING: No archive found, skipping: {use_case}")
        continue

    print(f"  Archive : {archive_path.name}")

    base_cases = dict_base_cases.get(use_case)
    if base_cases is None:
        print(f"  WARNING: No base_cases defined for {use_case}, skipping.")
        continue

    out_dir = BASE_DIR / use_case
    out_dir.mkdir(parents=True, exist_ok=True)

    all_combos = list(product(base_cases, factor1, factor2, factor3, factor4, factor5))
    print(f"  Combinations : {len(all_combos)}")

    targets = []
    for base, f1, f2, f3, f4, f5 in all_combos:
        case_name = build_case_name(base, use_case, f1, f2, f3, f4, f5)
        # print(f"    Case: {case_name}")
        targets.append(f"{case_name}/oM_Result_07_rEleOutputSummary_{case_name}.csv")
        targets.append(f"{case_name}/oM_Result_01_rObjFunComponents_{case_name}.csv")

    print(f"  Files to extract : {len(targets)}")

    t_start = time.time()

    names_set = set(get_archive_names(archive_path))
    missing   = [t for t in targets if t not in names_set]
    if missing:
        print(f"  WARNING: {len(missing)} files not found:")
        for m in missing:
            print(f"    MISSING: {m}")
        targets = [t for t in targets if t in names_set]

    print(f"  Extracting {len(targets)} files...")
    extract_files(archive_path, out_dir, targets)

    elapsed = time.time() - t_start
    print(f"  Done : {use_case} -> {out_dir}")
    print(f"  Time : {elapsed:.1f}s ({elapsed/60:.1f} min)")

total_elapsed = time.time() - t_total_start
print(f"\n{'='*60}")
print(f"All use cases done!")
print(f"Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")