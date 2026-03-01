# This copy the case name and creates the cases into the folder case
import shutil
import numpy as np
import pandas as pd

from pathlib import Path
from itertools import product

# === Base directories ===
BASE_DIR = Path(r"C:\Users\Erik\Documents\GitHub\el1xr_opt\data\EEM26")
CASES_DIR = BASE_DIR / "Cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

# === Factors definition ===
base_cases = ["Home1"]
factor0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
factor1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
factor2 = ["T1", "T2", "T3", "T4", "T5"]

# Define columns
columns_retailer = ["Case", "TariffType","Fastavgift", "Overforingsavgift", "EnergyTax", "PowerTariff", "Paslag", "Moms"]
columns_DoD = ["Case", "DoDS1", "DoDS2", "DoDS3", "DoDC1", "DoDC2", "DoDC3"]
columns_parameter = ["Case", "NumberPowerPeaks"]
columns_MinStorage = ["Case", "MinCapacity", "InitialStorage"]

# === Lookup dictionaries (faster than DataFrame filtering) ===
dict_factor0 = {
    "UC1": "HomeCom", "UC2": "HomeNonCom", "UC3": "HomeCom", "UC4": "HomeNonCom",
    "UC5": "HomeCom", "UC6": "HomeNonCom", "UC7": "HomeCom", "UC8": "HomeCom",
    "UC9": "HomeCom", "UC10": "HomeCom",
}

dict_retailer = {
    "UC1":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "UC2":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "UC3":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891.0, "Paslag": 0.05, "Moms": 0.25},
    "UC4":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891.0, "Paslag": 0.05, "Moms": 0.25},
    "UC5":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "UC6":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "UC7":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891, "Paslag": 0.05, "Moms": 0.25},
    "UC8":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891, "Paslag": 0.05, "Moms": 0.25},
    "UC9":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891, "Paslag": 0.05, "Moms": 0.25},
    "UC10": {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 891, "Paslag": 0.05, "Moms": 0.25},
}

dict_DoD = {
    "wDoD":  {"DoDS1": 0.25, "DoDS2": 0.5, "DoDS3": 0.25, "DoDC1": 0.2, "DoDC2": 0.4, "DoDC3": 0.8},
    "woDoD": {"DoDS1": 0, "DoDS2": 0, "DoDS3": 0, "DoDC1": 0, "DoDC2": 0, "DoDC3": 0},
}

dict_V2G = {
    "V2G": {"MaximumPower": None, "MinimumPower": 0},  # MaximumPower set from f6
    "V1G": {"MaximumPower": 1e-5, "MinimumPower": 1e-5},
}

dict_power_peaks = {
    "UC1": 3, "UC2": 3, "UC3": 0, "UC4": 0, "UC5": 3,
    "UC6": 3, "UC7": 0, "UC8": 0, "UC9": 0, "UC10": 0,
}

dict_min_storage = {
    "UC1": (7.0, 70.0), "UC2": (7.0, 70.0), "UC3": (7.0, 70.0), "UC4": (7.0, 70.0),
    "UC5": (35.0, 70.0), "UC6": (35.0, 70.0), "UC7": (7.0, 70.0), "UC8": (7.0, 70.0),
    "UC9": (7.0, 70.0), "UC10": (7.0, 70.0),
}

dict_month_hours = {
    "Month1": (1, 744), "Month2": (745, 1416), "Month3": (1417, 2160), "Month4": (2161, 2880),
    "Month5": (2881, 3624), "Month6": (3625, 4344), "Month7": (4345, 5088), "Month8": (5089, 5832),
    "Month9": (5833, 6552), "Month10": (6553, 7296), "Month11": (7297, 8016), "Month12": (8017, 8736),
}

UC_50_PERCENT = {"UC5", "UC6"}  # set for O(1) lookup

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

def short(factor):
    return abbrev.get(factor, factor)

# === File name filters ===
COPY_KEYWORDS = ["oM_Data", "oM_Dict"]


# === Pre-cache source CSVs per base case ===
# Read each source CSV once and reuse in memory instead of reading from disk every time
def preload_source_csvs(base):
    """Read all matching CSVs from source folder into memory."""
    src_folder = BASE_DIR / base
    csv_files = [f for f in src_folder.glob("*.csv") if any(k in f.name for k in COPY_KEYWORDS)]
    cache = {}
    for f in csv_files:
        cache[f.name] = {"path": f, "bytes": f.read_bytes()}
    return cache


def read_and_set_index(csv_bytes):
    """Read CSV from bytes and set unnamed columns as index."""
    from io import BytesIO
    df = pd.read_csv(BytesIO(csv_bytes))
    unnamed_cols = [col for col in df.columns if "Unnamed" in col]
    if unnamed_cols:
        df.set_index(unnamed_cols, inplace=True)
        df.index.names = [None] * len(unnamed_cols)
    return df


# === Optimized modify function ===
def modify_csv(csv_path: Path, df: pd.DataFrame, f0, f1, f2, f3, f4, f5, f6, f7, f8, f9,
               power_val, storage_val, charger, retailer_name):
    """Modify DataFrame in-place and save. Receives pre-parsed values."""

    fname = csv_path.name

    # --- CHARGER / ElectricityGeneration ---
    if "ElectricityGeneration" in fname:
        df["InitialPeriod"] = 2045
        df.loc[charger, "InitialPeriod"] = 2020
        df.loc[charger, "V2G"] = "Yes" if f2 == "V2G" else "No"

        # V2G adjustment
        v2g = dict_V2G[f2]
        df["MaximumPower"] = power_val if v2g["MaximumPower"] is None else v2g["MaximumPower"]
        df["MinimumPower"] = v2g["MinimumPower"]

        # Power (MaximumCharge)
        if "MaximumCharge" in df.columns:
            df["MaximumCharge"] = power_val

        # MinStorage from UC
        min_cap, init_stor = dict_min_storage[f0]
        df.loc[charger, "MinimumStorage"] = int(min_cap)
        df.loc[charger, "InitialStorage"] = int(init_stor)

        # Storage factor
        if "MaximumStorage" in df.columns:
            df["MaximumStorage"] = storage_val
        if "MinimumStorage" in df.columns:
            ratio = 50 / 100 if f0 in UC_50_PERCENT else 10 / 100
            df["MinimumStorage"] = storage_val * ratio
        if "InitialStorage" in df.columns:
            df["InitialStorage"] = storage_val

        # Market settings
        if f5 == "DayAhead":
            df.loc[charger, ["NoDayAhead", "NoFCRD", "NoFCRN"]] = ["No", "Yes", "Yes"]
        elif f5 == "FCR-D":
            df.loc[charger, ["NoFCRD", "NoFCRN", "EnduranceFCRD"]] = ["No", "Yes", 20]
            if f2 == "V2G":
                df.loc[charger, ["NoDayAhead", "MaximumPower"]] = ["No", 1e-5]
            else:
                df.loc[charger, "NoDayAhead"] = "Yes"
        elif f5 == "FCR-N":
            df.loc[charger, ["NoFCRD", "NoFCRN", "EnduranceFCRN"]] = ["Yes", "No", 60]
            if f2 == "V2G":
                df.loc[charger, ["NoDayAhead", "MaximumPower"]] = ["No", 1e-5]
            else:
                df.loc[charger, "NoDayAhead"] = "Yes"
        elif f5 == "DayAhead&FCR-D":
            df.loc[charger, ["NoDayAhead", "NoFCRD", "NoFCRN", "EnduranceFCRD"]] = ["No", "No", "Yes", 20]
        elif f5 == "DayAhead&FCR-N":
            df.loc[charger, ["NoDayAhead", "NoFCRD", "NoFCRN", "EnduranceFCRN"]] = ["No", "Yes", "No", 60]

        # DoD adjustment
        dod_vals = dict_DoD[f3]
        for col, val in dod_vals.items():
            if col in df.columns:
                df.loc[charger, col] = val

    # --- RETAILER ---
    elif "Retail" in fname:
        df["InitialPeriod"] = 2045
        retailer_idx = f"EleR_01_{retailer_name}"
        df.loc[retailer_idx, "InitialPeriod"] = 2020
        retail_vals = dict_retailer[f0]
        for col, val in retail_vals.items():
            if col in df.columns:
                df.loc[retailer_idx, col] = val

    # --- DURATION ---
    elif "Duration" in fname:
        match = df.index[df["Duration"] == 1]
        if not match.empty:
            df["Duration"] = 0.0
            start_hr, end_hr = dict_month_hours[f4]
            start_row = start_hr - 1
            num_rows = end_hr - start_row
            dur_col = df.columns.get_loc("Duration")
            df.iloc[start_row:start_row + num_rows, dur_col] = 1
            # print(f'    ✏️ Set Duration=1 for rows {start_row} to {start_row + num_rows}')
        else:
            print("    ⚠️ 'Duration' value of 1 not found.")

    # --- VarMaxOutflows ---
    if "VarMaxOutflows" in fname and storage_val != 70:
        charger_cols = [c for c in df.columns if charger in c]
        non_charger_cols = [c for c in df.columns if charger not in c]
        df[charger_cols] = storage_val
        df[non_charger_cols] = 0

    # --- VarMinStorage ---
    if "VarMinStorage" in fname and storage_val != 70:
        charger_cols = [c for c in df.columns if charger in c]
        non_charger_cols = [c for c in df.columns if charger not in c]
        df[charger_cols] = df[charger_cols] * storage_val / 70
        df[non_charger_cols] = 0

    # --- VarMaxStorage ---
    if "VarMaxStorage" in fname and storage_val != 70 and f0 in ["UC7", "UC8", "UC9", "UC10"]:
        charger_cols = [c for c in df.columns if charger in c]
        non_charger_cols = [c for c in df.columns if charger not in c]
        df[charger_cols] = df[charger_cols] * storage_val / 70
        df[non_charger_cols] = 0

    # --- Parameter ---
    if "Parameter" in fname:
        df.loc["Parameters", "NumberPowerPeaks"] = dict_power_peaks[f0]

    # --- Save ---
    df.to_csv(csv_path, index=True)


# === Main loop ===
# Pre-cache source files (read from disk once per base case)
csv_cache = {base: preload_source_csvs(base) for base in base_cases}

for base, f0, f1, f2, f3, f4, f5, f6, f7, f8, f9 in product(
    base_cases, factor0, factor1, factor2, factor3, factor4, factor5, factor6, factor7, factor8, factor9
):
    if f2 == "V1G" and f5 in ("FCR-D", "FCR-N"):
        continue

    case_name = f"{base}_{short(f5)}_{short(f4)}_{f0}_{f1}_{f2}_{short(f3)}_{short(f6)}_{short(f7)}_{short(f8)}_{short(f9)}"
    case_folder = CASES_DIR / case_name
    case_folder.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Created case folder: {case_folder}")

    # Pre-compute values used across all CSVs in this case
    power_val = float(f6[6:])
    storage_val = float(f7[8:])
    charger = f"{f1}_{dict_factor0[f0]}"
    retailer_name = dict_factor0[f0].replace("_tariff", "")

    cache = csv_cache[base]
    if not cache:
        print(f"  ⚠️ No matching CSV files found for {base}")
        continue

    for src_name, src_data in cache.items():
        new_name = src_name.replace(base, case_name)
        dest_file = case_folder / new_name

        if "oM_Data" in src_name:
            # Read from cached bytes, modify, and save (skip shutil.copy2)
            df = read_and_set_index(src_data["bytes"])
            modify_csv(dest_file, df, f0, f1, f2, f3, f4, f5, f6, f7, f8, f9,
                       power_val, storage_val, charger, retailer_name)
        else:
            # oM_Dict files: just write cached bytes directly (faster than shutil.copy2)
            dest_file.write_bytes(src_data["bytes"])
    print(f'  ✅ Case "{case_name}" set up with modified parameters.')

print("\n✅ All case folders created and parameter CSVs customized successfully.")