"""Load levels shorter than one hour (LoadLevelHours).

An hourly case and the same case with every hour split into four identical quarters
(LoadLevelHours = 0.25) describe the same problem once ramp limits are switched off: inputs
given in hours are converted to load levels, costs are weighted by the level duration, FCR
bids stay constant within each hour, and green-hydrogen matching is checked per clock hour.
The two optimal costs must then agree.

With ramp limits the quarter case can only cost more. Averaging a quarter-hour schedule over
each hour gives a feasible hourly schedule, but a step from one hour to the next must now
happen within one quarter, so the hourly optimum may break a ramp limit.
"""
import datetime
import importlib.util
import os
import shutil

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_Sequence import routine

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
H2VPP = os.path.join(REPO, "data", "H2VPP")
HOURS = 48  # load levels kept from the hourly case


def _run(d, case):
    return routine(dir=str(d), case=case, solver="highs",
                   date=datetime.datetime(2025, 1, 1, 0, 0),
                   rawresults="False", plots="False", indlog="False", duckdbresults="False")


def _cost(m):
    return float(pyo.value(m.eTotalSCost))


def _source(tmp_path, case):
    """Folder holding the hourly CSV case: H2VPP 'Home1', or a sizing variant built from it."""
    if case == "Home1":
        return H2VPP
    spec = importlib.util.spec_from_file_location("make_sizing_cases", os.path.join(REPO, "data", "sizing", "make_sizing_cases.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.OUT_ROOT = str(tmp_path / "src")
    os.makedirs(mod.OUT_ROOT, exist_ok=True)
    mod.build_case(case, mod.CASES[case])
    return mod.OUT_ROOT


def _time_files(folder, case):
    """CSV files indexed by (period, scenario, load level)."""
    levels = set(pd.read_csv(folder / f"oM_Dict_LoadLevel_{case}.csv")["LoadLevel"])
    out = []
    for f in sorted(os.listdir(folder)):
        if f.startswith("oM_Data_") and f.endswith(".csv"):
            with open(os.path.join(folder, f)) as fh:
                fh.readline()
                first = fh.readline().split(",")
            if len(first) > 2 and first[2].strip() in levels:
                out.append(f)
    return out


def _write_case(src, dst, case, split, ramps=True):
    """Copy the case, keep the first HOURS hours, and split each hour into ``split`` levels."""
    shutil.copytree(os.path.join(src, case), dst / case)
    folder = dst / case
    names = [f"t{i:04d}" for i in range(1, HOURS * split + 1)]
    for f in _time_files(folder, case):
        df = pd.read_csv(folder / f, index_col=[0, 1, 2]).iloc[:HOURS]
        df = df.loc[df.index.repeat(split)]
        p, sc = df.index.get_level_values(0), df.index.get_level_values(1)
        df.index = pd.MultiIndex.from_arrays([p, sc, names])
        if f.startswith("oM_Data_Duration_"):
            df["Duration"] = 1.0 / split
        df.to_csv(folder / f)
    pd.DataFrame({"LoadLevel": names}).to_csv(folder / f"oM_Dict_LoadLevel_{case}.csv", index=False)
    if not ramps:
        opt = pd.read_csv(folder / f"oM_Data_Option_{case}.csv", index_col=0)
        opt["IndBinGenRamps"] = 0
        opt.to_csv(folder / f"oM_Data_Option_{case}.csv")
    if split > 1:
        par = pd.read_csv(folder / f"oM_Data_Parameter_{case}.csv", index_col=0)
        par["LoadLevelHours"] = 1.0 / split
        par.to_csv(folder / f"oM_Data_Parameter_{case}.csv")
        # the demand shift window is given in load levels
        dem = pd.read_csv(folder / f"oM_Data_ElectricityDemand_{case}.csv", index_col=0)
        dem["ShiftedSteps"] = dem["ShiftedSteps"] * split
        dem.to_csv(folder / f"oM_Data_ElectricityDemand_{case}.csv")


@pytest.mark.solve
@pytest.mark.parametrize("case", ["Home1", "ElectrolyserFCR"])
def test_quarter_hours_reproduce_hourly_cost(case, tmp_path, deterministic_highs):
    src = _source(tmp_path, case)
    _write_case(src, tmp_path / "h", case, 1, ramps=False)
    _write_case(src, tmp_path / "q", case, 4, ramps=False)
    hourly = _run(tmp_path / "h", case)
    quarter = _run(tmp_path / "q", case)
    assert len(quarter.n) == 4 * len(hourly.n)
    assert _cost(quarter) == pytest.approx(_cost(hourly), rel=1e-6)
    # FCR bids are equal over the four quarters of each hour
    p, sc = list(quarter.ps)[0]
    levels = list(quarter.n)
    for name in ("vEleFreqContReserveDisUpwardBid", "vEleFreqContReserveDisDownwardBid", "vEleFreqContReserveNorBid"):
        var = getattr(quarter, name)
        for g in quarter.ege2h:
            bids = np.array([var[p, sc, n, g].value or 0.0 for n in levels]).reshape(-1, 4)
            assert np.allclose(bids, bids[:, :1])
    # the calendar advances 15 minutes per level, and four levels share a clock hour
    dt = quarter.Par['pDate']['DateTime']
    assert (dt.iloc[1] - dt.iloc[0]) == pd.Timedelta(minutes=15)
    n2h = dict(quarter.n2h.data())
    assert n2h[levels[0]] == n2h[levels[3]] != n2h[levels[4]]
    # green-hydrogen matching, when built, has one constraint per clock hour
    if hasattr(quarter, "eGreenH2Matching"):
        assert len(quarter.eGreenH2Matching) == len(hourly.eGreenH2Matching) > 0


@pytest.mark.solve
def test_quarter_hours_with_ramps_cost_no_less(tmp_path, deterministic_highs):
    _write_case(H2VPP, tmp_path / "h", "Home1", 1)
    _write_case(H2VPP, tmp_path / "q", "Home1", 4)
    assert _cost(_run(tmp_path / "q", "Home1")) >= _cost(_run(tmp_path / "h", "Home1")) * (1 - 1e-6)
