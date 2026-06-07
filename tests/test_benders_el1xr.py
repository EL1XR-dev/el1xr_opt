"""Stage D — el1xr Benders wiring on a real multi-scenario case.

Two things are checked:

  * the model now builds and solves with more than one (period, scenario) block.
    Multi-scenario / multi-period was previously unreachable because of a latent
    sizing bug in the initial-output parameters (fixed in oM_InputData); this test
    is the regression for that fix and exercises the block-restricted build seam.
  * el1xr Benders (``el1xr_benders``) reaches the same optimum as the monolithic
    solve. The H2VPP-derived case is not complete-recourse w.r.t. investment (a low
    investment can make a block's operating subproblem infeasible); the subproblems
    handle this with an elastic penalty relaxation that turns those infeasibilities
    into feasibility (steering) cuts, so the optimality-cut Benders loop still
    converges to the exact optimum. The generic machinery is in ``test_benders.py``;
    see docs/decomposition.md.

Needs an LP/dual-capable solver; skipped otherwise.
"""
import datetime
import tempfile

import pytest

from pyomo.environ import SolverFactory, value

from el1xr_opt.Modules.oM_Sequence import build_model
from el1xr_opt.Modules.oM_Decomposition import el1xr_benders, BendersConfig

import _make_2scenario as gen


def _solver():
    for s in ("gurobi", "appsi_highs"):
        try:
            if SolverFactory(s).available(exception_flag=False):
                return s
        except Exception:
            pass
    return None


_SOLVER = _solver()
pytestmark = pytest.mark.skipif(_SOLVER is None, reason="needs an LP/dual solver")


@pytest.mark.solve
def test_multiscenario_builds_and_solves():
    """Regression for the multi-scenario initial-output sizing fix + build seam."""
    work = tempfile.mkdtemp(prefix="benders_ms_")
    gen.build(work)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)
    blocks = list(m.ps)
    assert len(blocks) == 2, f"expected 2 (period,scenario) blocks, got {blocks}"
    SolverFactory(_SOLVER).solve(m)
    obj = float(value(m.eTotalSCost))
    assert obj > 0, f"monolithic objective should be finite/positive, got {obj}"


@pytest.mark.solve
def test_el1xr_benders_matches_monolithic():
    work = tempfile.mkdtemp(prefix="benders_el1xr_")
    gen.build(work)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    full = build_model(work, "Home1", date)
    SolverFactory(_SOLVER).solve(full)
    mono = float(value(full.eTotalSCost))
    res = el1xr_benders(work, "Home1", date, solver=_SOLVER,
                        config=BendersConfig(max_iterations=60, relative_gap=1e-6))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-4, \
        f"benders {res['objective']:.4f} vs monolithic {mono:.4f}"


@pytest.mark.solve
def test_el1xr_benders_parallel_matches_sequential():
    """Parallel subproblem solve (worker processes) reaches the same optimum as the
    sequential solve. The blocks are solved in separate processes (Pyomo solvers are
    not thread-safe); the result must be identical (the iteration count may differ
    because LP dual degeneracy yields different but equally valid cuts)."""
    work = tempfile.mkdtemp(prefix="benders_par_")
    gen.build(work)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    seq = el1xr_benders(work, "Home1", date, solver=_SOLVER,
                        config=BendersConfig(max_iterations=60, relative_gap=1e-6, n_workers=1))
    par = el1xr_benders(work, "Home1", date, solver=_SOLVER,
                        config=BendersConfig(max_iterations=60, relative_gap=1e-6, n_workers=4))
    assert par["converged"], f"parallel did not converge: gap={par['gap']:.2e}"
    assert abs(par["objective"] - seq["objective"]) / abs(seq["objective"]) < 1e-4, \
        f"parallel {par['objective']:.4f} vs sequential {seq['objective']:.4f}"
