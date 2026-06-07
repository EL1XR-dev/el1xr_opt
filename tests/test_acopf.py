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
from el1xr_opt.Modules.oM_ACOPF import solve_acopf  # noqa: E402


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
