"""Fast tests for the feature catalogue and problem-class logic (Stage A).

No model build or solve, so these run in the fast CI tier.
"""
from el1xr_opt.Modules import oM_Features as F


def test_flag_defaults_cover_catalogue():
    params = {}
    F.apply_flag_defaults(params)
    for feat in F.FEATURES:
        assert f"pOpt{feat.flag}" in params
    # existing values are not overwritten
    params2 = {"pOptIndBinCommunity": 1}
    F.apply_flag_defaults(params2)
    assert params2["pOptIndBinCommunity"] == 1


def test_problem_class_from_traits():
    cf = F._class_from_traits
    assert cf(False, False, False, False) == "LP"
    assert cf(True, False, False, False) == "MILP"
    assert cf(False, True, False, False) == "QP"
    assert cf(True, True, False, False) == "MIQP"
    assert cf(False, False, True, False) == "SOCP"
    assert cf(True, False, True, False) == "MISOCP"
    assert cf(False, False, False, True) == "NLP"
    assert cf(True, False, False, True) == "MINLP"


def test_capability_matrices():
    # the framework-study facts: linopy stops at MIQP, HiGHS can't do cones
    assert "linopy" in F.builders_for("MILP")
    assert "linopy" not in F.builders_for("SOCP")
    assert "linopy" not in F.builders_for("MISOCP")
    assert "pyoframe" in F.builders_for("MISOCP")
    assert "cvxpy" not in F.builders_for("NLP")        # convex only
    assert "jump" in F.builders_for("SDP")
    assert "highs" in F.solvers_for("MILP")
    assert "highs" not in F.solvers_for("SOCP")
    assert "gurobi" in F.solvers_for("MISOCP")
    assert "ipopt" in F.solvers_for("NLP")


def test_solver_supports():
    assert F.solver_supports("highs", "MILP")
    assert not F.solver_supports("highs", "SOCP")
    assert F.solver_supports("gurobi", "MISOCP")
    assert F.solver_supports("appsi_highs", "LP")       # prefix-matched


def test_cost_registry_seed_and_extend():
    import types
    m = types.SimpleNamespace()
    F.seed_objective_registry(m)
    # the built-in terms are registered in the expected groups
    assert ("vTotalEleNCost", "ps") in m._cost_terms
    assert ("vTotalEleMCost", "psn") in m._cost_terms
    assert ("vTotalEleDCost", "psd") in m._cost_terms
    assert ("vTotalEleMRev", "psn") in m._revenue_terms
    n0 = len(m._cost_terms)
    # a feature can register its own cost term without editing the core rules
    F.register_cost(m, "vTotalCommunitySettlement", "psn")
    assert len(m._cost_terms) == n0 + 1
    assert ("vTotalCommunitySettlement", "psn") in m._cost_terms
    import pytest
    with pytest.raises(ValueError):
        F.register_cost(m, "vBad", "bogus_kind")


def test_balance_mode_default_and_validation():
    # apply_flag_defaults seeds the balance mode for cases that predate the flag
    params = {}
    F.apply_flag_defaults(params)
    assert params["pParBalanceMode"] == "nodal"

    class _M:
        Par = {}
    assert F.select_balance_mode(_M()) == "nodal"          # default when absent
    _M.Par = {"pParBalanceMode": "ARC"}                     # case/whitespace tolerant
    assert F.select_balance_mode(_M()) == "arc"
    _M.Par = {"pParBalanceMode": "bogus"}
    import pytest
    with pytest.raises(ValueError):
        F.select_balance_mode(_M())


def test_balance_mode_gate():
    import pytest

    class _M:
        Par = {"pParBalanceMode": "nodal"}
    assert F.require_balance_mode_implemented(_M()) == "nodal"
    _M.Par = {"pParBalanceMode": "arc"}
    with pytest.raises(NotImplementedError):
        F.require_balance_mode_implemented(_M())


def test_balance_compatible_with_all_network_modes():
    # balance (bookkeeping) and network mode (physics) are orthogonal: every
    # balance expresses every network mode, including the AC / three-phase ones.
    for bm in F.BALANCE_MODES:
        for nm in F.NETWORK_MODES:
            assert F.balance_compatible_with_network(bm, nm) is True
    import pytest
    with pytest.raises(ValueError):
        F.balance_compatible_with_network("arc", "bogus_mode")
