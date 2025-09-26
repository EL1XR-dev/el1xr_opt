import datetime
import os
import pytest
import pyomo.environ as pyo
import numpy as np
import pandas as pd
# tests/test_run.py
from el1xr_opt.Modules.oM_Sequence import routine


# === Fixture definition ===
@pytest.fixture
def case_720h_system(request):
    """
    Fixture to temporarily modify the input files of a given case
    to simulate a 720-hours system and restore the originals afterward.
    """
    print(f'Setting up test case: {request.param}')
    print(f'Current working directory: {os.getcwd()}')
    print(f'File location: {os.path.abspath(__file__)}')
    case_name = request.param
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

    # File paths
    duration_csv = os.path.join(
        data['dir'], data['case'], f"oT_Data_Duration_{case_name}.csv"
    )

    # Backup original data
    original_duration_df = pd.read_csv(duration_csv, index_col=[0, 1, 2])

    try:
        # Modify Duration: keep only first 168 hours (1 week)
        df = original_duration_df.copy()
        df.iloc[720:, df.columns.get_loc("Duration")] = np.nan
        df.to_csv(duration_csv)

        yield data

    finally:
        # Restore original files
        original_duration_df.to_csv(duration_csv)


# === Parametrized Test ===
@pytest.mark.parametrize("case_720h_system,expected_cost", [
    ("Home1", 475.4938571171714),
], indirect=["case_720h_system"])
def test_model_run(case_720h_system, expected_cost):
    """
    Parametrized test for running model with 720-hours modification.
    Asserts that total system cost matches expected value.
    """
    print("Running test case:", case_720h_system['case'])
    model = routine(**case_720h_system)

    assert model is not None, "Model instance returned is None."

    actual_cost = pyo.value(model.eTotalSCost)
    print(f"Expected cost: {expected_cost:.5f}, Actual cost: {actual_cost:.5f}")

    np.testing.assert_approx_equal(actual_cost, expected_cost)