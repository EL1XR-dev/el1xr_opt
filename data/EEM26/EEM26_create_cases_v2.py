# This copy the case name and creates the cases into the folder case



import shutil
import numpy as np
import pandas as pd

from pathlib import Path
from itertools import product

# === Base directories ===
BASE_DIR = Path(r"C:\Users\ealvarezq\Documents\GitHub\Comillas\Models\el1xr_opt\data\EEM26")
CASES_DIR = BASE_DIR / "Cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

# === Factors definition ===
base_cases = ["Home1"]
# factor0 = ["ClusterA"]
factor0 = ["ClusterA", "ClusterB", "ClusterC", "ClusterD", "ClusterE"]
factor1 = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]
# factor1 = ["H1", "H6"]
factor2 = ["T0", "T1", "T2", "T3", "T4"]
factor3 = ["woDoD"]

# Define columns
columns_retailer = ["Case", "TariffType","Fastavgift", "Overforingsavgift", "EnergyTax", "PowerTariff", "Paslag", "Moms"]
columns_DoD = ["Case", "DoDS1", "DoDS2", "DoDS3", "DoDC1", "DoDC2", "DoDC3"]
columns_V2G = ["Case", "MaximumPower", "MinimumPower"]
columns_parameter = ["Case", "NumberPowerPeaks"]
columns_MinStorage = ["Case", "MinCapacity", "InitialStorage"]
columns_cluster = ["Case", "Load", "PV", "BESS", "EV"]

dict_retailer = {
    "H1":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H2":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H3":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H4":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H5":  {"TariffType": "Daily", "Fastavgift": 260, "Overforingsavgift": 0.09, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H6":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H7":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H8":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H9":  {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
    "H10": {"TariffType": "Daily", "Fastavgift": 292, "Overforingsavgift": 0.05, "EnergyTax": 0.439, "PowerTariff": 65.0, "Paslag": 0.05, "Moms": 0.25},
}

dict_DoD = {
    "wDoD":  {"DoDS1": 0.25, "DoDS2": 0.5, "DoDS3": 0.25, "DoDC1": 0.2, "DoDC2": 0.4, "DoDC3": 0.8},
    "woDoD": {"DoDS1": 0, "DoDS2": 0, "DoDS3": 0, "DoDC1": 0, "DoDC2": 0, "DoDC3": 0},
}

dict_V2G = {
    "V2G": {"MaximumPower": 11, "MinimumPower": 0},  # MaximumPower set from f6
    "V1G": {"MaximumPower": 1e-5, "MinimumPower": 0},
}

dict_power_peaks = {
    "T0": 3, "T1": 3, "T2": 3, "T3": 1, "T4": 1
}

dict_tariff_type = {
    "T0": "Daily", "T1": "Daily", "T2": "Daily", "T3": "Hourly", "T4": "Daily",
}

dict_cluster = {
    "ClusterA": {"Load": 1.0, "PV": 1.0, "BESS": 0.0, "EV": 0.0},
    "ClusterB": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": 0.0},
    "ClusterC": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": "V1G"},
    "ClusterD": {"Load": 1.0, "PV": 1.0, "BESS": 1.0, "EV": "V2G"},
    "ClusterE": {"Load": 1.0, "PV": 0.0, "BESS": 0.0, "EV": 0.0},
}

# === Abbreviations ===
abbrev = {
    "ClusterA": "ClA", "ClusterB": "ClB", "ClusterC": "ClC", "ClusterD": "ClD", "ClusterE": "ClE",
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
def modify_csv(csv_path: Path, df: pd.DataFrame, f0, f1, f2, f3):
    """Modify DataFrame in-place and save. Receives pre-parsed values."""

    fname = csv_path.name

    # Settings for scenario T0
    load = f"EleD_{f1[1:].zfill(2)}"
    pv = f"Solar_{f1[1:].zfill(2)}"
    ev = f"EV_{f1[1:].zfill(2)}"
    bess = f"BESS_01"

    # if "Option" in fname and f0 in ["ClusterA", "ClusterE"]:
    if "Option" in fname:
        df.loc["Options", "IndBinGenOperat"] = 0

    # Activating load according to f1
    if "ElectricityDemand" in fname:
        df["InitialPeriod"] = 2045
        df.loc[load, "InitialPeriod"] = 2020

    # Activating PV, BESS and EV according to f  and according to cluster f0
    if "ElectricityGeneration" in fname:
        df["InitialPeriod"] = 2045
        if f0 == "ClusterA":
            df.loc[pv, "InitialPeriod"] = 2020
        elif f0 == "ClusterB":
            df.loc[pv, "InitialPeriod"] = 2020
            df.loc[bess, "InitialPeriod"] = 2020
        elif f0 == "ClusterC":
             df.loc[pv, "InitialPeriod"] = 2020
             df.loc[bess, "InitialPeriod"] = 2020
             df.loc[ev, "InitialPeriod"] = 2020
             # using dict_cluster to set V2G or V1G for EV
             ev_type = dict_cluster[f0]["EV"]
             # using dict_V2G to set MaximumPower and MinimumPower for EV based on V2G or V1G
             v2g_settings = dict_V2G[str(ev_type)]
             df.loc[ev, "MaximumPower"] = v2g_settings["MaximumPower"]
             df.loc[ev, "MinimumPower"] = v2g_settings["MinimumPower"]
        elif f0 == "ClusterD":
            df.loc[pv, "InitialPeriod"] = 2020
            df.loc[bess, "InitialPeriod"] = 2020
            df.loc[ev, "InitialPeriod"] = 2020
            # using dict_cluster to set V2G or V1G for EV
            ev_type = dict_cluster[f0]["EV"]
            # using dict_V2G to set MaximumPower and MinimumPower for EV based on V2G or V1G
            v2g_settings = dict_V2G[str(ev_type)]
            df.loc[ev, "MaximumPower"] = v2g_settings["MaximumPower"]
            df.loc[ev, "MinimumPower"] = v2g_settings["MinimumPower"]
        elif f0 == "ClusterE":
            pass  # No PV, BESS, or EV activated


    # setting the degradation according to f0 and f3
    if "ElectricityGeneration" in fname:
        if f3 == "wDoD":
            # using dict_DoD to set DoDS1, DoDS2, DoDS3, DoDC1, DoDC2, DoDC3 for BESS and EV based on wDoD or woDoD
            dod_settings = dict_DoD[f3]
            for col, val in dod_settings.items():
                if col in df.columns:
                    df.loc[bess, col] = val
                    df.loc[ev, col] = val
        elif f3 == "woDoD":
            pass

    # setting the scenario T# according to f0 and f2
    if "Parameter" in fname:
        df.loc["Parameters", "NumberPowerPeaks"] = dict_power_peaks[f2]

    if "ElectricityRetail" in fname:
        # --- ensure numeric columns can take decimals (avoid int64 -> float assignment crash) ---
        float_cols = ["Fastavgift", "Overforingsavgift", "EnergyTax", "PowerTariff", "Paslag", "Moms"]
        for c in float_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

        df["InitialPeriod"] = 2045
        retailer_name = f"EleR_01"
        df.loc[retailer_name, "InitialPeriod"] = 2020

        retailer_tariff = dict_tariff_type[f2]

        retail_vals = dict_retailer[f1]
        for col, val in retail_vals.items():
            if col in df.columns:
                df.loc[retailer_name, col] = val

        df.loc[retailer_name, "TariffType"] = retailer_tariff

        if f2 == "T1":
            df.loc[retailer_name, "PowerTariff"] = 0.0
        elif f2 == "T2":
            df.loc[retailer_name, "PowerTariff"] = 32.5
        elif f2 == "T3":
            df.loc[retailer_name, "PowerTariff"] = 65.0
        elif f2 == "T4":
            df.loc[retailer_name, "PowerTariff"] = 65.0

    # --- Save ---
    df.to_csv(csv_path, index=True)


# === Main loop ===
# Pre-cache source files (read from disk once per base case)
csv_cache = {base: preload_source_csvs(base) for base in base_cases}

for base, f2, f1, f0, f3 in product(base_cases, factor2, factor1, factor0, factor3):

    case_name = f"{base}_{short(f2)}_{f1}_{f0}_{f3}"
    case_folder = CASES_DIR / case_name
    case_folder.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Created case folder: {case_folder}")

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
            modify_csv(dest_file, df, f0, f1, f2, f3)
        else:
            # oM_Dict files: just write cached bytes directly (faster than shutil.copy2)
            dest_file.write_bytes(src_data["bytes"])
    print(f'  ✅ Case "{case_name}" set up with modified parameters.')

print("\n✅ All case folders created and parameter CSVs customized successfully.")