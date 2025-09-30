import datetime
import os
import pyomo.environ as pyo
import numpy as np
import pandas as pd
import logging

from src.el1xr_opt.Modules.oM_Sequence import routine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CASE_NAMES = ["Grid1", "Home1"]  # Add more case names as needed
EXPECTED_COSTS = {
    "Grid1": 7871.908957833342,
    "Home1": 417.8402972105073}  # Replace with actual expected costs

def setup_test_case(case_name):
    """
    Set up the test case by modifying the necessary CSV files and preparing input data.
    Returns the data required for running el1xr_opt.
    """
    data = dict(
        dir=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../src/el1xr_opt")
        ),
        case=case_name,
        solver="gurobi",  # You can change the solver here
        date= datetime.datetime.now().replace(second=0, microsecond=0),
        rawresults="False",
        plots="False",
    )

    print("Setting up test case...")
    # Added print for console feedback
    duration_csv = os.path.join(data["dir"], data["case"], f"oM_Data_Duration_{data['case']}.csv")
    #RESEnergy_csv = os.path.join(data["DirName"], data["CaseName"], f"oM_Data_RESEnergy_{data['CaseName']}.csv")
    #stage_csv = os.path.join(data["DirName"], data["CaseName"], f"oM_Data_Stage_{data['CaseName']}.csv")

    # Read original data
    original_duration_df = pd.read_csv(duration_csv, index_col=[0, 1, 2])
    #original_resenergy_df = pd.read_csv(RESEnergy_csv, index_col=[0, 1])
    #original_stage_df = pd.read_csv(stage_csv, index_col=[0])

    try:
        print("Modifying CSV files...")  # Added print for console feedback
        # Modify and save the modified DataFrames
        modify_and_save_csv(original_duration_df, "Duration", 720, duration_csv, 0)
        #modify_and_save_csv(original_resenergy_df, "RESEnergy", 0, RESEnergy_csv, 0)
        #modify_and_save_csv(original_stage_df, "Weight", 0, stage_csv, 1)

        yield data  # Yielding allows cleanup even if there's an early return or exception

    except Exception as e:
        logger.error(f"Error occurred during test setup: {e}")
        raise

    finally:
        print("Restoring original CSV files...")  # Added print for console feedback
        # Restore original data
        logger.info("Restoring original CSV files.")
        original_duration_df.to_csv(duration_csv)
        #original_resenergy_df.to_csv(RESEnergy_csv)
        #original_stage_df.to_csv(stage_csv)


def modify_and_save_csv(df, column_name, start_row, file_path, idx):
    """
    Modify the specified column starting from the given row, setting values to NaN, and save to the file.
    """
    df_copy = df.copy()
    if idx == 0:
        df_copy.iloc[start_row:, df_copy.columns.get_loc(column_name)] = np.nan
    elif idx == 1:
        df_copy.iloc[start_row:, df_copy.columns.get_loc(column_name)] = 12
    df_copy.to_csv(file_path)
    print(f"Modified {file_path} and saved.")  # Added print for console feedback


def test_el1xr_opt_run():
    """
    Test function for running openTEPES with the modified test case.
    Asserts the run was successful.
    """
    print("Starting the el1xr_opt run...")  # Added print for console feedback
    for case_name in CASE_NAMES:
        print(f'Running test for {case_name}...')
        for case_data in setup_test_case(case_name):
            model = routine(**case_data)

            assert model is not None, f"{case_name} failed: model is None."
            logger.info(f"{case_name} passed. Total system cost: {model.eTotalSCost}")
            print(f"{case_name} - Total system cost: {model.eTotalSCost}")  # Added print for console feedback
            np.testing.assert_approx_equal(pyo.value(model.eTotalSCost), EXPECTED_COSTS[case_name])


# Run the test function
if __name__ == "__main__":
    print("Running the test...")
    test_el1xr_opt_run()
    print("Test complete.")