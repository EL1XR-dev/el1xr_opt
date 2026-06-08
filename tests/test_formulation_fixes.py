"""Regression tests for three formulation bugs found in the 2026-06 model audit.

1. The hydrogen O&M variable cost was **subtracted** in ``eTotalHydGCost`` while the
   electricity analogue adds it, so the model was effectively paid to run hydrogen
   generators.
2. The hydrogen storage inventory balance ``eHydInventory`` was gated on
   ``model.negs`` -- the *electricity* storage cycle set -- instead of
   ``model.nhgs``, so it was never built and hydrogen state-of-charge went
   untracked.
3. The ``eEleMaxRampDwOutput`` guard referenced ``model.Par['pEleGenRampDw']``, a
   misspelled parameter that exists nowhere, which would raise ``KeyError`` for any
   thermal unit with a ramp-down limit under ``IndBinGenRamps == 1``.

Bugs 1 and 2 are checked behaviourally on the ``H2Tank`` variant case, the only
shipped case that brings the hydrogen generation/storage units into the base year
(so the hydrogen sets are non-empty). The model is only *built*, not solved, so the
separate "no electricity->hydrogen converter" gap in that case (which makes its
hydrogen demand unservable) does not matter here.

Bug 3 is checked at the source, because no shipped case has a thermal generator and
constructing one by hand trips unrelated set-membership assumptions in the build.
"""
import datetime
import os
import subprocess
import sys

import pytest
from pyomo.repn import generate_standard_repn

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
from el1xr_opt.Modules.oM_Sequence import build_model  # noqa: E402

SIZING_DIR = os.path.join(REPO, "data", "sizing")
MODEL_FORMULATION = os.path.join(REPO, "src", "el1xr_opt", "Modules",
                                 "oM_ModelFormulation.py")


@pytest.fixture(scope="module")
def h2_model():
    """Build (not solve) the ``H2Tank`` variant, where the hydrogen storage unit and
    the electrolyser are active. Generated on the fly from the H2VPP base if absent."""
    if not os.path.isfile(os.path.join(SIZING_DIR, "H2Tank.duckdb")):
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    return build_model(SIZING_DIR, "H2Tank", date)


def test_hydrogen_storage_inventory_is_built(h2_model):
    """Bug 2: with a hydrogen storage unit present, ``eHydInventory`` must be built
    (it was silently skipped when gated on the electricity cycle set)."""
    assert len(h2_model.hgs) > 0, "test case has no hydrogen storage unit"
    assert len(h2_model.eHydInventory) > 0, \
        "hydrogen storage inventory balance was not built"


def test_hydrogen_om_cost_is_added(h2_model):
    """Bug 1: the output coefficient in ``eTotalHydGCost`` must reflect
    Linear + O&M (the O&M cost added), not Linear - O&M."""
    m = h2_model
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    hg = next((g for g in m.hg if m.Par['pHydGenOMVariableCost'][g]), None)
    assert hg is not None, "test case has no hydrogen generator with an O&M cost"
    lin = float(m.Par['pHydGenLinearVarCost'][hg])
    om = float(m.Par['pHydGenOMVariableCost'][hg])
    repn = generate_standard_repn(m.eTotalHydGCost[p, sc, n].body)
    out = m.vHydTotalOutput[p, sc, n, hg]
    coef = next((c for v, c in zip(repn.linear_vars, repn.linear_coefs) if v is out), None)
    assert coef is not None, "output variable absent from the hydrogen generation cost"
    # the linear + O&M terms on the same variable combine; the buggy '- O&M' would
    # give |Linear - O&M| (zero here, since Linear == O&M).
    assert abs(coef) == pytest.approx(lin + om, rel=1e-9), \
        f"coefficient {coef} should reflect Linear+O&M={lin + om} (O&M added)"


def test_ele_rampdown_uses_correct_param_name():
    """Bug 3: the ramp-down guard must use ``pEleGenRampDown``; the misspelled
    ``pEleGenRampDw`` raised KeyError for any ramp-limited thermal unit."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "pEleGenRampDw'" not in text, \
        "misspelled parameter pEleGenRampDw was reintroduced"
    assert "pEleGenRampDown'" in text
