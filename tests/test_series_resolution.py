"""Time series at their own resolution (optional table oM_Data_SeriesResolution).

H2VPP Home1 with 48 active hours, split into 192 quarter-hour levels. A series declared
``uniform 1h`` keeps its 48 hourly rows and is resampled onto the quarter hours when the case is
read, so the case is the same as the one with the series repeated four times by hand.
"""
import os

import pandas as pd
import pytest

from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb
from el1xr_opt.Modules.oM_Sequence import build_structure
from test_load_level_minutes import _no_storage_ramps, _quarter_case
from test_time_blocks import CASE, DATE, SAME, _case, _cost, _solve

PRICE = "VarEnergyCost"


def test_hourly_series_is_repeated_over_the_quarters(tmp_path):
    repeated = build_structure(str(_quarter_case(tmp_path / "r")), CASE, DATE)
    declared = build_structure(str(_quarter_case(tmp_path / "d", keep=[PRICE])), CASE, DATE)
    tables = [k for k in repeated.Par if isinstance(repeated.Par[k], pd.DataFrame)
              and repeated.Par[k].shape == declared.Par[k].shape and repeated.Par[k].shape[0] == 192]
    assert tables
    for k in tables:
        pd.testing.assert_frame_equal(declared.Par[k], repeated.Par[k], check_dtype=False, obj=k)


def test_every_series_can_be_given_hourly(tmp_path):
    repeated = build_structure(str(_quarter_case(tmp_path / "r")), CASE, DATE)
    d = _quarter_case(tmp_path / "d", keep="all")
    declared = build_structure(str(d), CASE, DATE)
    table = pd.read_csv(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv", index_col=0)
    assert len(table) > 10
    for k, v in repeated.Par.items():
        if isinstance(v, pd.DataFrame) and v.shape[0] == 192:
            pd.testing.assert_frame_equal(declared.Par[k], v, check_dtype=False, obj=k)


def test_a_finer_series_is_averaged_over_each_level(tmp_path):
    """A quarter-hour series in an hourly case: each hour gets the mean of its four quarters."""
    d = _case(tmp_path)
    folder = d / CASE
    path = folder / f"oM_Data_{PRICE}_{CASE}.csv"
    hourly = pd.read_csv(path, index_col=[0, 1, 2])
    quarters = hourly.loc[hourly.index.repeat(4)].copy()
    step = pd.Series([-3.0, -1.0, 1.0, 3.0] * len(hourly), index=quarters.index)
    quarters = quarters.add(step, axis=0)
    quarters.index = pd.MultiIndex.from_tuples([(p, sc, f"q{i + 1:05d}") for i, (p, sc, _) in enumerate(quarters.index)])
    quarters.to_csv(path)
    pd.DataFrame({"Resolution": ["uniform 15min"]}, index=[PRICE]).to_csv(folder / f"oM_Data_SeriesResolution_{CASE}.csv")
    m = build_structure(str(d), CASE, DATE)
    ref = build_structure(str(_case(tmp_path / "ref")), CASE, DATE)
    for k, v in ref.Par.items():
        if isinstance(v, pd.DataFrame) and v.shape[0] == len(ref.nn):
            pd.testing.assert_frame_equal(m.Par[k], v, check_dtype=False, obj=k)


def test_a_wrong_row_count_is_refused(tmp_path):
    d = _quarter_case(tmp_path, keep=[PRICE])
    pd.DataFrame({"Resolution": ["uniform 2h"]}, index=[PRICE]).to_csv(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv")
    with pytest.raises(ValueError, match="8736 rows for period1, sc01"):
        build_structure(str(d), CASE, DATE)


def test_an_unknown_file_is_refused(tmp_path):
    d = _case(tmp_path)
    pd.DataFrame({"Resolution": ["uniform 1h"]}, index=["NoSuchSeries"]).to_csv(d / CASE / f"oM_Data_SeriesResolution_{CASE}.csv")
    with pytest.raises(ValueError, match="no data file"):
        build_structure(str(d), CASE, DATE)


def test_declaration_is_read_from_duckdb_too(tmp_path):
    d = _quarter_case(tmp_path / "csv", keep=[PRICE])
    work = tmp_path / "db"
    os.makedirs(work / CASE)
    csv_case_to_duckdb(str(d), CASE, db_path=str(work / f"{CASE}.duckdb"))
    from_db = build_structure(str(work), CASE, DATE)
    from_csv = build_structure(str(d), CASE, DATE)
    for k, v in from_csv.Par.items():
        if isinstance(v, pd.DataFrame) and v.shape[0] == 192:
            pd.testing.assert_frame_equal(from_db.Par[k], v, check_dtype=False, obj=k)


@pytest.mark.solve
def test_hourly_series_give_the_cost_of_the_repeated_case(tmp_path, deterministic_highs):
    repeated = _cost(_solve(_quarter_case(tmp_path / "r", _no_storage_ramps)))
    declared = _cost(_solve(_quarter_case(tmp_path / "d", _no_storage_ramps, keep="all")))
    hourly = _case(tmp_path / "h")
    _no_storage_ramps(hourly / CASE)
    assert declared == pytest.approx(repeated, rel=SAME)
    assert declared == pytest.approx(_cost(_solve(hourly)), rel=SAME)
