"""Stage C — unbalanced linear OPF (LinDist3Flow).

Validates the LinDist3Flow LP on a small radial three-phase feeder:
  * a balanced feeder with diagonal impedance reduces, phase by phase, to the
    single-phase LinDistFlow (the exact correctness check on the diagonal terms);
  * unbalanced per-phase loading produces a per-phase voltage spread (the heavily
    loaded phase is lowest) - the thing a single-phase model cannot show.

The rigorous validation of the mutual (off-diagonal) coupling terms against
OpenDSS / PowerModelsDistribution.jl is the Phase-5c follow-on.

Solve needs an LP solver (HiGHS via appsi); skipped if unavailable.
"""
import math

import pytest

from pyomo.environ import SolverFactory

from el1xr_opt.Modules.oM_LinDist3Flow import solve_lindist3flow, balanced_branch, PHASES
from el1xr_opt.Modules import oM_Features as F


def _have_highs():
    try:
        return bool(SolverFactory("appsi_highs").available(exception_flag=False))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _have_highs(), reason="needs an LP solver (HiGHS)")


def _feeder():
    R, X = balanced_branch(0.03, 0.05)
    return [{"i": "B1", "j": "B2", "R": R, "X": X},
            {"i": "B2", "j": "B3", "R": R, "X": X}]


@pytest.mark.solve
def test_balanced_reduces_to_single_phase():
    branches = _feeder()
    loads = {"B2": {p: (0.3, 0.1) for p in PHASES},
             "B3": {p: (0.2, 0.05) for p in PHASES}}
    V = solve_lindist3flow(branches, loads, "B1")
    # single-phase LinDistFlow reference (downstream flow sums)
    w2 = 1.0 - 2 * (0.03 * 0.5 + 0.05 * 0.15)
    w3 = w2 - 2 * (0.03 * 0.2 + 0.05 * 0.05)
    ref = {"B2": math.sqrt(w2), "B3": math.sqrt(w3)}
    for bus in ("B2", "B3"):
        for p in PHASES:
            assert abs(V[bus][p] - ref[bus]) < 1e-9, f"{bus}{p}: {V[bus][p]} vs {ref[bus]}"


@pytest.mark.solve
def test_unbalanced_voltage_spread():
    branches = _feeder()
    loads = {"B2": {p: (0.1, 0.03) for p in PHASES},
             "B3": {"a": (0.6, 0.2), "b": (0.1, 0.03), "c": (0.1, 0.03)}}
    V = solve_lindist3flow(branches, loads, "B1")
    assert V["B3"]["a"] < V["B3"]["b"] - 1e-6          # heavy phase lowest
    assert abs(V["B3"]["b"] - V["B3"]["c"]) < 1e-6     # equal light phases


def test_lindist3flow_is_lp():
    # the mode catalogue classifies it as LP, so linopy can build and HiGHS solve it
    assert F.network_mode_class("lindist3flow") == "LP"
    assert "linopy" in F.builders_for("LP")
    assert "highs" in F.solvers_for("LP")
