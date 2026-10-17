"""The H2VPPFCR paper case at 15-min load levels (data/H2VPPFCR/build_case.py).

One week from 1 October 2025, when the SE3 day-ahead prices went to 15 min. The hourly case reads
the 15-min prices and averages them over each hour. The quarter-hour case reads them as they are,
keeps every other series hourly, and holds the FCR bids constant over each hour.
"""
import datetime
import importlib.util
import os

import pandas as pd
import pytest

from el1xr_opt.Modules.oM_Sequence import build_structure

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FOLDER = os.path.join(REPO, "data", "H2VPPFCR")
CASE = "H2VPPFCR"
DATE = datetime.datetime(2025, 1, 1)
OCTOBER = "6552"                                  # hour of the year of 2025-10-01 00:00 UTC
SPOT = ("VarEnergyCost", "VarEnergyPrice")


def _build(dst, monkeypatch, minutes, spot="15min", start=OCTOBER):
    """Build the one-week case into dst/H2VPPFCR and return dst."""
    for k, v in {"H2VPP_HORIZON": "week", "H2VPP_START_HOUR": start, "MONEY_BASE": "1000",
                 "H2VPP_LEVEL_MINUTES": str(minutes), "H2VPP_SPOT": spot}.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("build_case", os.path.join(FOLDER, "build_case.py"))
    bc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc)
    bc.BASE_DIR = bc.REPO / "data" / "H2VPP"     # the builder expects the model under model/
    bc.OUT_DIR = dst / CASE
    bc.build()
    return dst


def _spot(m):
    return {k: m.Par[f"p{k}"]["EleR_01"].to_numpy() for k in SPOT}


def test_hourly_case_reads_the_hourly_mean_of_the_15min_spot(tmp_path, monkeypatch):
    d = _build(tmp_path / "h", monkeypatch, 60)
    table = pd.read_csv(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv", index_col=0)
    assert table["Resolution"].to_dict() == {k: "uniform 15min" for k in SPOT}
    declared = build_structure(str(d), CASE, DATE)
    # the same case with the hourly means written by hand
    for stem in SPOT:
        f = d / CASE / f"oM_Data_{stem}_{CASE}.csv"
        df = pd.read_csv(f, index_col=[0, 1, 2])
        df = df.groupby(pd.RangeIndex(len(df)) // 4).mean().set_index(declared.Par["pDuration"].index)
        df.index.names = [None] * 3
        df.to_csv(f)
    os.remove(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv")
    by_hand = build_structure(str(d), CASE, DATE)
    assert len(list(declared.n)) == 168
    for k in SPOT:
        pd.testing.assert_frame_equal(declared.Par[f"p{k}"], by_hand.Par[f"p{k}"], check_dtype=False, obj=k)


def test_quarter_case_has_15min_prices_and_hourly_bids(tmp_path, monkeypatch):
    hourly = build_structure(str(_build(tmp_path / "h", monkeypatch, 60)), CASE, DATE)
    d = _build(tmp_path / "q", monkeypatch, 15)
    quarter = build_structure(str(d), CASE, DATE)
    lv = list(quarter.n)
    assert len(lv) == 672
    assert quarter.Par["pDuration"].iloc[0] == 0.25
    # the 15-min prices average to the prices of the hourly case
    for k, q in _spot(quarter).items():
        assert q.reshape(-1, 4).mean(axis=1) == pytest.approx(_spot(hourly)[k], rel=1e-12)
        assert len(set(q[:4])) > 1                # 2025-10-01 00:00 has four prices
    # every other series is hourly: the FCR price holds over each hour
    table = pd.read_csv(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv", index_col=0)
    assert "OperatingReservePrice" in table.index and not set(SPOT) & set(table.index)
    fcr = [k for k in quarter.Par if k.startswith("pOperatingReservePrice_")]
    assert fcr
    for k in fcr:
        assert (quarter.Par[k].to_numpy().reshape(-1, 4).std(axis=1) == 0).all(), k
    # the FCR bids are one variable per hour for every unit that can bid
    bidders = pd.read_csv(d / CASE / f"oM_Data_Resolution_{CASE}.csv", index_col=0).index
    assert {"BESS_2h", "Wind_01"} <= set(bidders)
    for g in bidders:
        key = next(k for k in quarter.flow_res if k[1] == g and k[2] == "Reserve")
        start = quarter.block_start[key]
        assert [start[n] for n in lv[:8]] == [lv[0]] * 4 + [lv[4]] * 4


def test_a_week_before_october_is_refused(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="2025-10-01"):
        _build(tmp_path, monkeypatch, 15, start="0")


def test_a_ramp_costs_the_same_at_any_level_length(tmp_path, monkeypatch):
    """The ramp degradation cost is per kW of change. The row of each level is weighted by its
    duration in the objective, so its coefficient times the duration is the cost of a change."""
    from pyomo.repn import generate_standard_repn
    from el1xr_opt.Modules.oM_Sequence import build_model

    def cost_of_a_change(m):
        p, sc = list(m.ps)[0]
        n = list(m.n)[1]
        repn = generate_standard_repn(m.eTotalHydGCost[p, sc, n].body, compute_values=True)
        coef = {v.name: c for v, c in zip(repn.linear_vars, repn.linear_coefs)
                if v.parent_component().name == "vHydGenRampAbs"}
        assert coef
        return {k.replace(n, "n"): c * m.Par["pDuration"][p, sc, n] for k, c in coef.items()}

    hourly = cost_of_a_change(build_model(str(_build(tmp_path / "h", monkeypatch, 60)), CASE, DATE))
    quarter = cost_of_a_change(build_model(str(_build(tmp_path / "q", monkeypatch, 15)), CASE, DATE))
    assert quarter.keys() == hourly.keys()
    for k, c in hourly.items():
        assert quarter[k] == pytest.approx(c, rel=1e-12), k
