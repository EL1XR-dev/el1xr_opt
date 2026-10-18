"""Load levels shorter than an hour (Parameter LoadLevelMinutes).

H2VPP Home1 with 48 active hours, and the same case split into 192 quarter-hour levels with every
time series repeated four times. Times given in hours (up and down times, storage cycles, demand
shift windows) become four times as many levels, durations become 0.25 h, and the peak tariff is
set on the clock-hour mean of the import.
"""
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_Sequence import build_model, build_structure
from test_time_blocks import CASE, DATE, SAME, _case, _cost, _solve


def _to_quarters(folder, k=4, keep=()):
    """Split every load level of the case in ``folder`` into k levels, repeating each series.

    The series named in ``keep`` (data file stems, or "all" for every series but Duration) stay
    hourly and are declared ``uniform 1h`` in oM_Data_SeriesResolution instead.
    """
    path = folder / f"oM_Dict_LoadLevel_{CASE}.csv"
    levels = pd.read_csv(path).iloc[:, 0].tolist()
    new = {n: [f"t{i * k + j + 1:05d}" for j in range(k)] for i, n in enumerate(levels)}
    pd.DataFrame({"LoadLevel": [q for n in levels for q in new[n]]}).to_csv(path, index=False)
    kept = []
    for f in sorted(folder.glob(f"oM_Data_*_{CASE}.csv")):
        df = pd.read_csv(f, header=None, dtype=str, keep_default_na=False)
        body = df.iloc[1:]
        if len(body) and body.shape[1] >= 3 and body.iloc[:, 2].isin(levels).all():
            stem = f.name[len("oM_Data_"):-len(f"_{CASE}.csv")]
            if stem != "Duration" and (keep == "all" or stem in keep):
                kept.append(stem)
                continue
            rows = body.loc[body.index.repeat(k)].copy()
            rows.iloc[:, 2] = [q for n in body.iloc[:, 2] for q in new[n]]
            pd.concat([df.iloc[[0]], rows]).to_csv(f, header=False, index=False)
    _set_parameter(folder, "LoadLevelMinutes", 60 // k)
    if kept:
        pd.DataFrame({"Resolution": "uniform 1h"}, index=kept).to_csv(folder / f"oM_Data_SeriesResolution_{CASE}.csv")
    return kept


def _set_parameter(folder, name, value):
    path = folder / f"oM_Data_Parameter_{CASE}.csv"
    par = pd.read_csv(path, index_col=0)
    par[name] = value
    par.to_csv(path)


def _edit_battery(folder, **values):
    path = folder / f"oM_Data_ElectricityGeneration_{CASE}.csv"
    gen = pd.read_csv(path, index_col=0)
    for column, value in values.items():
        gen.loc["BESS_01", column] = value
    gen.to_csv(path)


def _no_storage_ramps(folder):
    path = folder / f"oM_Data_ElectricityGeneration_{CASE}.csv"
    gen = pd.read_csv(path, index_col=0)
    gen[["RampUp", "RampDown"]] = 0.0
    gen.to_csv(path)


def _quarter_case(dst, edit=None, keep=()):
    d = _case(dst)
    if edit is not None:
        edit(d / CASE)
    _to_quarters(d / CASE, keep=keep)
    return d


# --- reading the case -------------------------------------------------------------------------

def test_hourly_levels_by_default(tmp_path):
    m = build_structure(str(_case(tmp_path)), CASE, DATE)
    assert m.Par["pParLoadLevelMinutes"] == 60
    assert m.Par["pDuration"].iloc[0] == 1.0
    assert all(len(levels) == 1 for levels in m.hour_levels.values())


@pytest.mark.parametrize("value", [0, -15, 7.5])
def test_level_length_must_be_whole_minutes(tmp_path, value):
    d = _case(tmp_path)
    _set_parameter(d / CASE, "LoadLevelMinutes", value)
    with pytest.raises(ValueError, match="LoadLevelMinutes"):
        build_structure(str(d), CASE, DATE)


def test_quarter_levels_have_quarter_durations_and_dates(tmp_path):
    m = build_structure(str(_quarter_case(tmp_path)), CASE, DATE)
    lv = list(m.n)
    assert len(lv) == 192
    assert m.Par["pDuration"].iloc[0] == 0.25
    dates = m.Par["pDate"]["DateTime"]
    assert [d.strftime("%H:%M") for d in dates.iloc[:5]] == ["00:00", "00:15", "00:30", "00:45", "01:00"]
    assert dates.iloc[-1].strftime("%d %H:%M") == "02 23:45"
    assert len(m.hour_levels) == 48
    assert m.hour_levels[lv[4]] == lv[4:8]


def test_times_in_hours_become_levels(tmp_path):
    edit = lambda f: _edit_battery(f, UpTime=3, DownTime=2, StorageType="Weekly")
    d = _case(tmp_path / "h")
    edit(d / CASE)
    hourly = build_structure(str(d), CASE, DATE)
    quarter = build_structure(str(_quarter_case(tmp_path / "q", edit)), CASE, DATE)
    for name, levels in (("pEleGenUpTime", 3), ("pEleGenDownTime", 2), ("pEleCycleTimeStep", 24)):
        assert hourly.Par[name]["BESS_01"] == levels, name
        assert quarter.Par[name]["BESS_01"] == 4 * levels, name
    shifted = [ed for ed in hourly.ed if hourly.Par["pEleDemShiftedSteps"][ed]]
    assert shifted
    for ed in shifted:
        assert quarter.Par["pEleDemShiftedSteps"][ed] == 4 * hourly.Par["pEleDemShiftedSteps"][ed]


def test_peak_is_set_on_the_hourly_mean_import(tmp_path):
    m = build_model(str(_quarter_case(tmp_path)), CASE, DATE)
    lv = list(m.n)
    con = m.eElePeakHourValue
    rows = [idx for idx in con if con[idx].active]
    assert len(rows) == 48 * len(m.Peaks)                        # one row per clock hour and peak
    assert {idx[2] for idx in rows} == set(m.hour_levels)
    first = next(idx for idx in rows if idx[2] == lv[0] and idx[5] == m.Peaks.first())
    imports = {v.name: c for v, c in _linear(con[first].body) if v.parent_component().name == "vEleImport"}
    assert len(imports) == 4
    assert len(set(round(c, 12) for c in imports.values())) == 1   # the four quarters weigh the same


def _linear(expr):
    from pyomo.repn import generate_standard_repn
    repn = generate_standard_repn(expr, compute_values=True)
    return zip(repn.linear_vars, repn.linear_coefs)


# --- solved -----------------------------------------------------------------------------------

@pytest.mark.solve
def test_quarter_levels_reproduce_the_hourly_cost(tmp_path, deterministic_highs):
    """Without ramp limits on the stores, the quarter-hour case with hourly data is the hourly
    case: every quarter solution averages to an hourly one of the same cost."""
    hourly = _case(tmp_path / "h")
    _no_storage_ramps(hourly / CASE)
    quarter = _quarter_case(tmp_path / "q", _no_storage_ramps)
    assert _cost(_solve(quarter)) == pytest.approx(_cost(_solve(hourly)), rel=SAME)


@pytest.mark.solve
def test_ramp_limits_bind_harder_at_quarter_hours(tmp_path, deterministic_highs):
    """A ramp limit in kW per hour lets an hourly model jump a whole hour of ramp between two
    levels. At quarter hours the same rate allows a quarter of it per level, so the case with
    the shipped EV ramps costs more."""
    hourly = _cost(_solve(_case(tmp_path / "h")))
    quarter = _cost(_solve(_quarter_case(tmp_path / "q")))
    assert quarter > hourly + 1e-3


# --- ramps between blocks ---------------------------------------------------------------------

RAMPED = [f"EV_{i:02d}" for i in range(1, 11)] + ["BESS_01"]


def _declare_hourly(folder):
    """Declare the output and charge of every ramp-limited unit at 1 h."""
    pd.DataFrame({"Output": "uniform 1h", "Charge": "uniform 1h"}, index=RAMPED).to_csv(
        folder / f"oM_Data_Resolution_{CASE}.csv")


def test_a_ramp_spans_the_time_between_block_midpoints(tmp_path):
    """At the first level of an hourly block the ramp spans (1 h + 1 h) / 2; inside the block, and
    for a flow that is not declared, one quarter-hour level."""
    from el1xr_opt.Modules.oM_TimeBlocks import ramp_hours
    d = _quarter_case(tmp_path)
    _declare_hourly(d / CASE)
    m = build_structure(str(d), CASE, DATE)
    p, sc = list(m.ps)[0]
    lv = list(m.n)
    declared = ramp_hours(m, p, sc, "Ele", "BESS_01", "Output")
    assert [declared[n] for n in lv[:9]] == [0.25, 0.25, 0.25, 0.25, 1.0, 0.25, 0.25, 0.25, 1.0]
    assert set(ramp_hours(m, p, sc, "Ele", "BESS_01", "Inventory").values()) == {0.25}


@pytest.mark.solve
def test_hourly_flows_at_quarter_hours_reproduce_the_hourly_ramps(tmp_path, deterministic_highs):
    """With the ramp-limited units declared at 1 h, the quarter-hour case is the hourly case with
    the shipped ramp limits: a change between two hourly blocks is allowed the ramp of one hour."""
    hourly = _cost(_solve(_case(tmp_path / "h")))
    quarter = _cost(_solve(_quarter_case(tmp_path / "q", _declare_hourly)))
    assert quarter == pytest.approx(hourly, rel=SAME)


# --- storage reset (Parameter StorageResetHours) ---------------------------------------------

def _reset_levels(m, unit="BESS_01"):
    """Ordinal positions of the levels where the store's inventory is fixed."""
    lv = list(m.n)
    return [lv.index(n) + 1 for (p, sc, n, g) in m.vEleInventory if g == unit and m.vEleInventory[p, sc, n, g].fixed]


@pytest.mark.parametrize("hours, quarters, expected", [
    (None, False, []),             # default 744 h: no reset inside 48 h
    (24, False, [24, 48]),
    (0, False, []),
    (24, True, [96, 192]),         # 24 h is 96 quarter-hour levels
])
def test_storage_reset_hours(tmp_path, hours, quarters, expected):
    """An Hourly store is set back to its initial inventory every StorageResetHours."""
    edit = (lambda f: _set_parameter(f, "StorageResetHours", hours)) if hours is not None else None
    d = _quarter_case(tmp_path, edit) if quarters else _case(tmp_path)
    if hours is not None and not quarters:
        edit(d / CASE)
    m = build_model(str(d), CASE, DATE)
    assert m.Par["pEleGenStorageType"]["BESS_01"] == "Hourly"
    assert _reset_levels(m) == expected
    for n in expected:
        assert m.vEleInventory["period1", "sc01", list(m.n)[n - 1], "BESS_01"].value == pytest.approx(
            m.Par["pEleInitialInventory"]["BESS_01"]["period1", "sc01", m.n.first()])


@pytest.mark.parametrize("hours", [-1, 0.5])
def test_storage_reset_hours_must_be_zero_or_a_level(tmp_path, hours):
    d = _case(tmp_path)
    _set_parameter(d / CASE, "StorageResetHours", hours)
    with pytest.raises(ValueError, match="StorageResetHours"):
        build_structure(str(d), CASE, DATE)
