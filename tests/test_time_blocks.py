"""Resolutions declared per asset and flow (oM_TimeBlocks).

H2VPP Home1 with 48 active hours. Solar_01 output is declared at 2 h, so its output is constant
over each pair of hours. Its availability changes every hour around noon (0.068, 0.037, 0.063,
0.091 kW in hours 11-14), so the two capacity rules give different limits:
Level keeps the output below the lowest availability of each block, Mean below the block mean.

In the shipped case solar is must-take (its lower limit equals its availability), so a 2-h
constant output is impossible under Level and must be refused when the case is read. The solved
tests make Solar_01 curtailable by setting its lower limit to zero.
"""
import datetime
import os
import shutil

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb
from el1xr_opt.Modules.oM_Sequence import build_structure, routine

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CASE = "Home1"
DATE = datetime.datetime(2025, 1, 1)


def _case(dst, resolution=None, rule=None, curtailable=False):
    """H2VPP Home1 with 48 active hours, an optional resolution table and capacity rule."""
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", CASE), dst / CASE)
    folder = dst / CASE
    path = folder / f"oM_Data_Duration_{CASE}.csv"
    dur = pd.read_csv(path, index_col=[0, 1, 2])
    col = dur.columns.get_loc("Duration")
    dur.iloc[:48, col] = 1.0
    dur.iloc[48:, col] = np.nan
    dur.to_csv(path)
    if resolution is not None:
        pd.DataFrame.from_dict(resolution, orient="index", columns=["Output", "Charge"]).to_csv(folder / f"oM_Data_Resolution_{CASE}.csv")
    if curtailable:
        path = folder / f"oM_Data_VarMinGeneration_{CASE}.csv"
        vmin = pd.read_csv(path, index_col=[0, 1, 2])
        vmin["Solar_01"] = 0.0
        vmin.to_csv(path)
    if rule is not None:
        path = folder / f"oM_Data_Parameter_{CASE}.csv"
        par = pd.read_csv(path, index_col=0)
        par["BlockLimit"] = rule
        par.to_csv(path)
    return dst


def _solve(d):
    return routine(dir=str(d), case=CASE, solver="highs", date=DATE,
                   rawresults="False", plots="False", indlog="False", duckdbresults="False")


SOLAR_2H = {"Solar_01": {"Output": "uniform 2h", "Charge": None}}


def _solar(m):
    """Solar_01 output and its availability per level, as arrays of 48."""
    p, sc = list(m.ps)[0]
    lv = list(m.n)
    out = np.array([m.vEleTotalOutput[p, sc, n, "Solar_01"].value for n in lv])
    avail = np.array([m.Par["pEleMaxPower"]["Solar_01"][p, sc, n] for n in lv])
    return out, avail


# --- declarations -----------------------------------------------------------------------------

def test_without_a_table_nothing_is_declared(tmp_path):
    m = build_structure(str(_case(tmp_path)), CASE, DATE)
    assert m.flow_res == {} and m.block_start == {}
    assert m.Par["pParBlockLimit"] == "Level"


def test_declaration_maps_levels_to_block_starts(tmp_path):
    m = build_structure(str(_case(tmp_path, SOLAR_2H, curtailable=True)), CASE, DATE)
    first = m.block_start[("Ele", "Solar_01", "Output")]
    lv = list(m.n)
    assert [first[n] for n in lv[:4]] == [lv[0], lv[0], lv[2], lv[2]]
    assert m.flow_res[("Ele", "Solar_01", "Output")].size == 24


def test_declaration_is_read_from_duckdb_too(tmp_path):
    d = _case(tmp_path / "csv", SOLAR_2H, curtailable=True)
    work = tmp_path / "db"
    os.makedirs(work / CASE)
    csv_case_to_duckdb(str(d), CASE, db_path=str(work / f"{CASE}.duckdb"))
    m = build_structure(str(work), CASE, DATE)
    assert m.flow_res[("Ele", "Solar_01", "Output")].size == 24


def test_block_off_the_level_boundaries_is_refused(tmp_path):
    d = _case(tmp_path, {"Solar_01": {"Output": "uniform 90min", "Charge": None}})
    with pytest.raises(ValueError, match="load level boundaries"):
        build_structure(str(d), CASE, DATE)


def test_charge_of_a_unit_that_cannot_charge_is_refused(tmp_path):
    d = _case(tmp_path, {"Solar_01": {"Output": None, "Charge": "uniform 2h"}})
    with pytest.raises(ValueError, match="no charge flow"):
        build_structure(str(d), CASE, DATE)


def test_must_take_profile_is_refused_under_level(tmp_path):
    with pytest.raises(ValueError, match="cannot be constant over its block"):
        build_structure(str(_case(tmp_path, SOLAR_2H)), CASE, DATE)


def test_must_take_profile_becomes_the_block_mean_under_mean(tmp_path):
    m = build_structure(str(_case(tmp_path, SOLAR_2H, rule="Mean")), CASE, DATE)
    p, sc = list(m.ps)[0]
    lv = list(m.n)
    lo = [m.Par["pEleMinPower"]["Solar_01"][p, sc, n] for n in lv[10:12]]
    hi = [m.Par["pEleMaxPower"]["Solar_01"][p, sc, n] for n in lv[10:12]]
    assert lo == pytest.approx([(0.06776 + 0.03745) / 2] * 2, abs=1e-5)
    assert hi == pytest.approx(lo)


def test_unknown_capacity_rule_is_refused(tmp_path):
    with pytest.raises(ValueError, match="BlockLimit"):
        build_structure(str(_case(tmp_path, SOLAR_2H, rule="Median")), CASE, DATE)


# --- solved -----------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def deterministic_highs_module():
    """Module-scoped twin of conftest.deterministic_highs, for the shared solves below."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("EL1XR_HIGHS_DETERMINISTIC", "1")
        yield


@pytest.fixture(scope="module")
def solved(tmp_path_factory, deterministic_highs_module):
    base = tmp_path_factory.mktemp("blocks")
    out = {}
    for label, res, rule in (("hourly", None, None), ("level", SOLAR_2H, None), ("mean", SOLAR_2H, "Mean")):
        out[label] = _solve(_case(base / label, res, rule, curtailable=True))
    return out


@pytest.mark.solve
def test_level_rule_holds_output_below_the_lowest_availability(solved):
    m = solved["level"]
    out, avail = _solar(m)
    pairs = out.reshape(-1, 2)
    assert np.allclose(pairs[:, 0], pairs[:, 1])                       # constant within 2 h
    assert np.all(pairs[:, 0] <= avail.reshape(-1, 2).min(axis=1) + 1e-9)
    assert len(m.eEleOutputBlock_Solar_01) == 24
    # a unit at a lower resolution can only cost more
    cost = lambda k: float(pyo.value(solved[k].eTotalSCost))
    assert cost("level") >= cost("hourly") - 1e-9


@pytest.mark.solve
def test_mean_rule_holds_output_below_the_block_mean(solved):
    m = solved["mean"]
    out, _ = _solar(m)
    _, avail = _solar(solved["hourly"])                                 # the hourly availability
    pairs = out.reshape(-1, 2)
    mean = avail.reshape(-1, 2).mean(axis=1)
    assert np.allclose(pairs[:, 0], pairs[:, 1])
    assert np.all(pairs[:, 0] <= mean + 1e-9)
    # in hours 11-12 (0.068, 0.037) the output may exceed the lower hour, unlike under Level
    assert pairs[5, 0] > avail[11] + 1e-6
    # Mean never creates energy: each block delivers at most its available energy
    assert np.all(pairs.sum(axis=1) <= avail.reshape(-1, 2).sum(axis=1) + 1e-9)
    # Mean allows all that Level allows, so it costs no more. It is not a restriction of the
    # hourly model, though: it spreads a block's energy evenly over the block, which moves
    # energy between its hours, and on this case it costs less than the hourly model.
    cost = lambda k: float(pyo.value(solved[k].eTotalSCost))
    assert cost("mean") <= cost("level") + 1e-9
    assert cost("mean") < cost("hourly")
