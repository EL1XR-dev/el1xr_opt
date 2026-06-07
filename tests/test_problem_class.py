"""End-to-end problem-class detection on the validation cases (Stage A).

Builds each case (no solve needed beyond construction) and checks the detected
class and the solver/builder capability mapping. Marked ``solve`` because it
builds a full model (slow), though it does not call a solver.
"""
import datetime
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest
from pyomo.environ import ConcreteModel

from el1xr_opt.Modules.oM_InputData import data_processing, create_variables
from el1xr_opt.Modules.oM_Investment import create_investment
from el1xr_opt.Modules.oM_ModelFormulation import (create_objective_function,
                                                   create_objective_function_components,
                                                   create_constraints)
from el1xr_opt.Modules import oM_Features as F

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _build(d, case, n=72):
    path = os.path.join(d, case, f"oM_Data_Duration_{case}.csv")
    fd, bk = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    shutil.copy2(path, bk)
    try:
        df = pd.read_csv(path, index_col=[0, 1, 2])
        df.iloc[n:, df.columns.get_loc("Duration")] = np.nan
        df.to_csv(path)
        m = ConcreteModel()
        m = data_processing(d, case, datetime.datetime.now().replace(second=0, microsecond=0), m, "False")
        m = create_variables(m, m, "False")
        m = create_investment(m, m, "False")
        m = create_objective_function(m, m, "False")
        m = create_objective_function_components(m, m, "False")
        m = create_constraints(m, m, "False")
    finally:
        shutil.move(bk, path)
    return m


@pytest.mark.solve
@pytest.mark.parametrize("d,case,expected", [
    (os.path.join(REPO, "src", "el1xr_opt"), "Home1", "LP"),    # default flags: continuous
    (os.path.join(REPO, "data", "EEM26"),    "Home1", "MILP"),  # unit-commitment binaries on
])
def test_detected_class(d, case, expected):
    m = _build(d, case)
    pc = F.detect_problem_class(m)
    assert pc == expected, f"{case}: detected {pc}, expected {expected}"
    # the capability mapping is consistent with the detected class
    assert "pyomo" in F.builders_for(pc)
    if expected == "LP":
        assert "linopy" in F.builders_for(pc) and "highs" in F.solvers_for(pc)
    if expected == "MILP":
        assert "linopy" in F.builders_for(pc) and "highs" in F.solvers_for(pc)
