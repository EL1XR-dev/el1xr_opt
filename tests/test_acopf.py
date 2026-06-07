"""Phase 5a — AC OPF module validated against the IEEE 33-bus feeder.

The IEEE 33-bus radial distribution system (Baran & Wu, 1989) is the canonical
DistFlow benchmark, with a published base-case active loss of ~202.7 kW and a
minimum voltage of ~0.913 pu. This checks that ``oM_ACOPF``:

  * the SOC (DistFlow) relaxation reproduces the published loss and min voltage,
    with a tight relaxation gap (so the relaxation is exact here), and
  * the exact polar NLP (warm-started from the SOC solution) agrees with it.

The SOC path needs a cone-capable solver (Gurobi); the NLP needs Ipopt. The test
skips if the required solver is unavailable so it does not fail on a bare runner.
"""
import sys
import os

import pytest

from pyomo.environ import SolverFactory

sys.path.insert(0, os.path.dirname(__file__))
import _ieee33 as ieee33  # noqa: E402
from el1xr_opt.Modules.oM_ACOPF import (solve_acopf, run_acopf_sweep,  # noqa: E402
                                        scaled_snapshots, write_acopf_sweep)


def _have(solver):
    try:
        return bool(SolverFactory(solver).available(exception_flag=False))
    except Exception:
        return False


@pytest.mark.solve
@pytest.mark.skipif(not _have("gurobi"), reason="needs a cone-capable solver (gurobi)")
def test_ieee33_socp_matches_published():
    df = ieee33.network_df()
    Pd, Qd = ieee33.loads_pu()
    r = solve_acopf(df, Pd, Qd, slack=ieee33.SLACK, formulation="socp")
    loss_kw = r["objective"] * 1000.0
    vmin = min(r["V"].values())
    assert abs(loss_kw - ieee33.PUBLISHED_LOSS_MW * 1000.0) < 2.0, f"loss {loss_kw:.2f} kW"
    assert abs(vmin - ieee33.PUBLISHED_VMIN) < 0.005, f"Vmin {vmin:.4f}"
    assert r["relaxation_gap_max"] < 1e-3, f"relaxation not tight: {r['relaxation_gap_max']:.2e}"


@pytest.mark.solve
@pytest.mark.skipif(not (_have("gurobi") and _have("ipopt")),
                    reason="needs gurobi (SOC warm start) and ipopt (NLP)")
def test_ieee33_nlp_matches_socp():
    df = ieee33.network_df()
    Pd, Qd = ieee33.loads_pu()
    socp = solve_acopf(df, Pd, Qd, slack=ieee33.SLACK, formulation="socp")
    nlp = solve_acopf(df, Pd, Qd, slack=ieee33.SLACK, formulation="nlp", vmin=0.85)
    loss_socp = socp["objective"] * 1000.0
    loss_nlp = (nlp["objective"] - sum(Pd.values())) * 1000.0   # slack inj - load = losses
    assert abs(loss_nlp - loss_socp) < 1.0, f"nlp {loss_nlp:.2f} vs socp {loss_socp:.2f} kW"
    vmin_socp = min(socp["V"].values())
    vmin_nlp = min(nlp["V"].values())
    assert abs(vmin_nlp - vmin_socp) < 0.01, f"Vmin nlp {vmin_nlp:.4f} vs socp {vmin_socp:.4f}"


@pytest.mark.solve
@pytest.mark.skipif(not _have("gurobi"), reason="needs a cone-capable solver (gurobi)")
def test_ieee33_sweep(tmp_path):
    """Phase 5b: a load-profile sweep gives monotone, physically coherent
    voltage/loss behaviour and the base snapshot reproduces the 5a benchmark."""
    Pd, Qd = ieee33.loads_pu()
    snaps = scaled_snapshots(Pd, Qd, {"light": 0.5, "mid": 0.8, "base": 1.0, "peak": 1.3})
    rows = run_acopf_sweep(ieee33.network_df(), snaps, slack=ieee33.SLACK,
                           formulation="socp", vmin_check=0.95)
    by = {r["label"]: r for r in rows}

    # base snapshot matches the IEEE 33-bus published values (consistency with 5a)
    assert abs(by["base"]["loss_pu"] * 1000 - ieee33.PUBLISHED_LOSS_MW * 1000) < 2.0
    assert abs(by["base"]["vmin"] - ieee33.PUBLISHED_VMIN) < 0.005

    # voltage falls and losses rise monotonically with load
    order = ["light", "mid", "base", "peak"]
    vmins = [by[k]["vmin"] for k in order]
    losses = [by[k]["loss_pu"] for k in order]
    assert all(vmins[i] > vmins[i + 1] for i in range(len(vmins) - 1)), vmins
    assert all(losses[i] < losses[i + 1] for i in range(len(losses) - 1)), losses
    # more (or equal) violations under heavier load; light load is clean
    assert by["light"]["violations"] <= by["peak"]["violations"]
    assert by["light"]["violations"] == 0

    # the sweep summary writes to DuckDB
    import duckdb
    db = str(tmp_path / "results.duckdb")
    write_acopf_sweep(db, "IEEE33", rows)
    con = duckdb.connect(db, read_only=True)
    try:
        n = con.execute('SELECT count(*) FROM "oM_Result_ACOPF_Sweep"').fetchone()[0]
    finally:
        con.close()
    assert n == len(rows)
