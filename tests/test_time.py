"""Time structure (oM_Time): timeline, resolutions, overlap and the two common resolutions.

The worked example is the one of Gao et al. (2025), Section 2, on a 6-hour horizon with an
hourly ruler: v1 has blocks 1:1, 2:4, 5:6 and v2 has 1:2, 3:3, 4:6 (1-based, inclusive).
"""
import numpy as np
import pandas as pd
import pytest

from el1xr_opt.Modules import oM_Time as T


def _hourly(hours=6, start="2025-01-01"):
    return T.Timeline([T.RepPeriod("k1", pd.Timestamp(start), hours)], unit_minutes=60)


def _blocks(res):
    """1-based inclusive (start, end) pairs, as written in the paper."""
    return [(int(s) + 1, int(e)) for s, e in zip(res.starts, res.ends)]


@pytest.fixture
def gao():
    tl = _hourly()
    v1 = T.from_lengths(tl, "k1", [1, 3, 2], "v1")
    v2 = T.from_lengths(tl, "k1", [2, 1, 3], "v2")
    return tl, v1, v2


def test_finest_common_follows_algorithm_1(gao):
    # eqs. (8)-(12): constraint blocks 1:1, 2:2, 3:3, 4:4, 5:6
    _, v1, v2 = gao
    assert _blocks(T.finest_common([v1, v2])) == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 6)]


def test_coarsest_common_follows_algorithm_2(gao):
    # Fig. 3b: 1:2, then 3:4 (v1 2:4 ends at 4), then 5:6
    _, v1, v2 = gao
    assert _blocks(T.coarsest_common([v1, v2])) == [(1, 2), (3, 4), (5, 6)]


def test_overlap_counts_shared_units(gao):
    _, v1, v2 = gao
    c = T.coarsest_common([v1, v2])
    ov = T.overlap(v1, c)
    # v1 block 2:4 (index 1) lies 1 h in c 1:2 and 2 h in c 3:4
    got = {(int(r.a), int(r.b)): int(r.units) for r in ov.itertuples()}
    assert got == {(0, 0): 1, (1, 0): 1, (1, 1): 2, (2, 2): 2}
    assert ov["units"].sum() == v1.horizon


def test_resample_rate_is_duration_weighted_mean(gao):
    tl, v1, _ = gao
    hourly = T.uniform(tl, "k1", 60)
    prices = np.array([10, 20, 30, 40, 50, 60.0])
    # v1 block 2:4 holds hours 2, 3, 4 -> mean 30
    assert np.allclose(T.resample(prices, hourly, v1, "rate"), [10, 30, 55])


def test_resample_amount_conserves_the_total(gao):
    tl, v1, _ = gao
    hourly = T.uniform(tl, "k1", 60)
    energy = np.array([1, 2, 3, 4, 5, 6.0])
    out = T.resample(energy, hourly, v1, "amount")
    assert np.allclose(out, [1, 9, 11])
    back = T.resample(out, v1, hourly, "amount")
    assert back.sum() == pytest.approx(energy.sum())


def test_one_minute_ruler_with_market_resolutions():
    # one week on a 1-min ruler; 15-min DA, hourly FCR, daily hydrogen demand
    tl = T.Timeline([T.RepPeriod("week", pd.Timestamp("2025-10-06"), 7 * 24 * 60)])
    da = T.from_spec(tl, "week", "uniform 15min")
    fcr = T.from_spec(tl, "week", "uniform 1h")
    day = T.from_spec(tl, "week", "calendar day")
    assert (da.size, fcr.size, day.size) == (672, 168, 7)
    assert _blocks(T.finest_common([da, fcr])) == _blocks(da)
    assert _blocks(T.coarsest_common([da, fcr, day])) == _blocks(day)
    # four quarters per FCR hour
    assert np.all(T.overlap(da, fcr).groupby("b").size() == 4)


def test_calendar_blocks_follow_the_clock():
    # starts at 22:00, so the first day has 2 h and the next a full 24 h
    tl = T.Timeline([T.RepPeriod("k", pd.Timestamp("2025-01-01 22:00"), 26 * 60)])
    day = T.calendar(tl, "k", "day")
    assert list(tl.hours(day.lengths)) == [2.0, 24.0]
    month = T.calendar(T.Timeline([T.RepPeriod("k", pd.Timestamp("2025-01-31"), 2 * 24 * 60)]), "k", "month")
    assert list(month.lengths) == [1440, 1440]


def test_explicit_specification_and_validation():
    tl = _hourly(4)
    res = T.from_spec(tl, "k1", "explicit 60,120,60")
    assert _blocks(res) == [(1, 1), (2, 3), (4, 4)]
    with pytest.raises(ValueError):
        T.from_spec(tl, "k1", "explicit 60,60")      # does not cover the period
    with pytest.raises(ValueError):
        tl.units(90)                                 # 1.5 h is not a whole number of 1-h base units
    with pytest.raises(ValueError):
        T.Resolution("bad", "k1", [0, 2], [3, 4])    # overlapping blocks


def test_representative_periods_are_independent():
    tl = T.Timeline([T.RepPeriod("winter", pd.Timestamp("2025-01-15"), 24 * 60, weight=90),
                     T.RepPeriod("summer", pd.Timestamp("2025-07-15"), 24 * 60, weight=92)])
    w, s = T.uniform(tl, "winter", 60), T.uniform(tl, "summer", 60)
    assert tl.timestamps("summer", [0])[0] == pd.Timestamp("2025-07-15")
    with pytest.raises(ValueError):
        T.overlap(w, s)


# --- the timeline inside the model ------------------------------------------------------------

import datetime
import os
import shutil

from el1xr_opt.Modules.oM_Sequence import build_structure

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _h2vpp_48h(dst, time_step):
    """Copy of H2VPP Home1 with 48 h of load levels and the given TimeStep."""
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", "Home1"), dst / "Home1")
    path = dst / "Home1" / "oM_Data_Duration_Home1.csv"
    dur = pd.read_csv(path, index_col=[0, 1, 2])
    col = dur.columns.get_loc("Duration")
    dur.iloc[:48, col] = 1.0        # the shipped case is active for 24 h only
    dur.iloc[48:, col] = np.nan
    dur.to_csv(path)
    path = dst / "Home1" / "oM_Data_Parameter_Home1.csv"
    par = pd.read_csv(path, index_col=0)
    par["TimeStep"] = time_step
    par.to_csv(path)
    return build_structure(str(dst), "Home1", datetime.datetime(2025, 6, 1, 14, 37))


@pytest.mark.parametrize("time_step", [1, 4])
def test_calendar_spans_the_real_horizon(tmp_path, time_step):
    """Each level is dated by the start of its block on the timeline, so merging hours with
    TimeStep does not compress the calendar (it used to date 48 h at TimeStep 4 as one day)."""
    m = _h2vpp_48h(tmp_path, time_step)
    dt = m.Par["pDate"]["DateTime"]
    assert len(m.n) == 48 // time_step
    assert dt.iloc[0] == pd.Timestamp("2025-01-01 00:00")
    assert dt.iloc[-1] == pd.Timestamp("2025-01-02 23:00") - pd.Timedelta(hours=time_step - 1)
    assert m.Par["pDate"]["Day"].nunique() == 2
    res = m.time_res["level"]
    assert res.horizon == 48 * 60
    assert set(m.timeline.hours(res.lengths)) == {float(time_step)}
