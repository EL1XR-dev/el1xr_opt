# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Feature catalogue and problem-class logic for el1xr_opt (architecture Stage A).
#
# One place that answers three questions:
#   1. Which optional features exist, how they are switched on/off, and their
#      default (so a case missing a flag column still runs).
#   2. What mathematical class the configured model is (LP / MILP / QP / MIQP /
#      SOCP / MISOCP / NLP), detected from the actually-built model.
#   3. Given that class, which solvers can solve it and which modelling libraries
#      can build it (the capability matrices from the framework study,
#      docs/modeling_framework_problem_classes.md).
#
# The class is the lever for choosing both the solver and (for a future migration)
# the model-building library: e.g. a MISOCP case rules out HiGHS as a solver and
# linopy as a builder; an NLP case needs Ipopt and Pyomo or JuMP.

# --------------------------------------------------------------------------- #
# 1. Feature catalogue: optional features gated by an Option-CSV flag.
#    (flag, default, makes_integer, module) — module is the *_variables/
#    *_constraints owner when the feature is its own module, else None.
#    makes_integer flags which features introduce binary/integer variables (a
#    hint; the true class is detected from the built model below).
# --------------------------------------------------------------------------- #
class Feature:
    def __init__(self, name, flag, default=0, makes_integer=False,
                 makes_cone=False, module=None, doc=""):
        self.name = name
        self.flag = flag                  # the pOpt{flag} key in model.Par
        self.default = default
        self.makes_integer = makes_integer
        self.makes_cone = makes_cone
        self.module = module
        self.doc = doc


FEATURES = [
    Feature("unit_commitment",        "IndBinGenOperat",     0, makes_integer=True,
            doc="binary generator commitment/start/shutdown (else continuous)"),
    Feature("network_commitment",     "IndBinNetOperat",     0, makes_integer=True,
            doc="binary line/pipeline operation"),
    Feature("gen_min_up_down_time",   "IndBinGenMinTime",    0, makes_integer=True,
            doc="minimum up/down time (needs commitment binaries)"),
    Feature("gen_ramps",              "IndBinGenRamps",      0, makes_integer=False,
            doc="ramp-rate limits (continuous; LP-preserving)"),
    Feature("binary_gen_investment",  "IndBinGenInvest",     0, makes_integer=True,
            doc="all-or-nothing generation investment"),
    Feature("binary_gen_retirement",  "IndBinGenRetirement", 0, makes_integer=True,
            doc="binary generation retirement"),
    Feature("binary_net_investment",  "IndBinPowerNetInvest", 0, makes_integer=True,
            doc="binary electricity-network investment"),
    Feature("binary_h2net_investment", "IndBinH2NetInvest",  0, makes_integer=True,
            doc="binary hydrogen-network investment"),
    Feature("line_commitment",        "IndBinLineCommit",    0, makes_integer=True,
            doc="line switching"),
    Feature("network_losses",         "IndBinNetLosses",     0, makes_integer=False,
            doc="transmission losses"),
    Feature("single_node",            "IndBinSingleNode",    0, makes_integer=False,
            doc="ignore the network (single aggregated node)"),
    Feature("energy_community",       "IndBinCommunity",     0, makes_integer=False,
            module="oM_Community",
            doc="energy-community / virtual sharing among members in a zone"),
]

FLAG_DEFAULTS = {f.flag: f.default for f in FEATURES}


def apply_flag_defaults(parameters_dict):
    """Give every catalogue flag a default so a case whose Option file predates the
    flag still runs (no KeyError). Existing values are left untouched."""
    for flag, default in FLAG_DEFAULTS.items():
        parameters_dict.setdefault(f"pOpt{flag}", default)
    # balance formulation (nodal / arc); orthogonal to the network mode
    parameters_dict.setdefault("pParBalanceMode", "nodal")
    return parameters_dict


# --------------------------------------------------------------------------- #
# 1b. Network-representation modes (architecture Stage C).
#    The network model is a selectable mode. Each mode declares the problem class
#    it implies and whether it is built inside the main operational model
#    (in_core) or run as a decoupled downstream analysis (like oM_ACOPF).
#    'lindist3flow' is the unbalanced *linear* OPF — an LP, so it can be built by
#    linopy and solved by HiGHS, unlike the exact unbalanced AC OPF (NLP/SOCP,
#    the PowerModelsDistribution.jl path of Phase 5c).
# --------------------------------------------------------------------------- #
NETWORK_MODES = {
    "single_node":   {"problem_class": "LP",   "in_core": True,
                      "doc": "ignore the network; one aggregated node"},
    "dc":            {"problem_class": "LP",   "in_core": True,
                      "doc": "DC power flow (angle + reactance); today's default"},
    "distflow_socp": {"problem_class": "SOCP", "in_core": False,
                      "doc": "single-phase branch-flow SOC relaxation (oM_ACOPF)"},
    "acopf_nlp":     {"problem_class": "NLP",  "in_core": False,
                      "doc": "single-phase exact polar AC OPF (oM_ACOPF)"},
    "lindist3flow":  {"problem_class": "LP",   "in_core": False,
                      "doc": "unbalanced linear three-phase OPF (LinDist3Flow); LP"},
}


def network_mode_class(mode):
    """Problem class implied by a network mode."""
    if mode not in NETWORK_MODES:
        raise ValueError(f"unknown network mode '{mode}' (use one of {list(NETWORK_MODES)})")
    return NETWORK_MODES[mode]["problem_class"]


# --------------------------------------------------------------------------- #
# 1c. Balance formulation -- how power conservation is written. This is a
#     separate, orthogonal axis from the network *mode* above: the mode is the
#     network physics (single node / DC / AC / three-phase), the balance is the
#     bookkeeping (one balance per node, or one per asset with explicit arc flows).
#     Any balance can express any network mode.
#       * nodal -- one balance per node: incident flows + injections == demand.
#                  Today's default; the smallest, fastest monolithic model.
#       * arc   -- one balance per asset with explicit arc-flow variables, the node
#                  reduced to flow conservation. Block-angular (one block per
#                  asset), the clean base for decomposition and the multi-vector
#                  (heat) extension, but ~3-5x larger and ~4x slower solved
#                  monolithically (benchmarks/balance_formulation.py). It reaches
#                  the same optimum. Planned modernization; not wired in-core yet.
#     Compatibility with the network modes: arc expresses all of them. For the AC
#     modes the arc simply carries active and reactive power and both line ends
#     (so losses, with P_ij != -P_ji); the branch-flow modes (distflow_socp,
#     lindist3flow) are arc/branch-based by construction, so arc is their natural
#     form. The problem class is set by the physics (arc + DC = LP, arc + AC = NLP,
#     arc + SOC relaxation = SOCP), not by the balance formulation.
# --------------------------------------------------------------------------- #
BALANCE_MODES = {
    "nodal": {"in_core": True,
              "doc": "one balance per node (incident flows + injections == demand); default"},
    "arc":   {"in_core": False,
              "doc": "per-asset balance + explicit arc flows, node = flow conservation; "
                     "block-angular, same optimum, ~4x slower monolithic; not in-core yet"},
}


def select_balance_mode(model):
    """Read and validate the balance formulation for a model. Defaults to 'nodal'
    when the case predates the flag (apply_flag_defaults seeds it)."""
    par = getattr(model, "Par", {})
    mode = str(par.get("pParBalanceMode", "nodal")).strip().lower()
    if mode not in BALANCE_MODES:
        raise ValueError(f"unknown balance mode '{mode}' (use one of {list(BALANCE_MODES)})")
    return mode


def balance_compatible_with_network(balance_mode, network_mode):
    """Whether a balance formulation can express a network mode. Always True --
    balance (bookkeeping) and network mode (physics) are orthogonal axes. The helper
    exists to validate the names and to make the orthogonality explicit: arc works
    with the AC and three-phase modes too (carrying active+reactive power and both
    line ends), and the branch-flow modes are arc-based by construction."""
    if balance_mode not in BALANCE_MODES:
        raise ValueError(f"unknown balance mode '{balance_mode}' (use one of {list(BALANCE_MODES)})")
    if network_mode not in NETWORK_MODES:
        raise ValueError(f"unknown network mode '{network_mode}' (use one of {list(NETWORK_MODES)})")
    return True


def require_balance_mode_implemented(model):
    """Guard for the in-core build: only 'nodal' is wired into the main model.
    Selecting 'arc' raises with a pointer to the modernization plan, rather than
    silently building a nodal model. Returns the validated mode ('nodal')."""
    mode = select_balance_mode(model)
    if not BALANCE_MODES[mode]["in_core"]:
        raise NotImplementedError(
            f"balance mode '{mode}' is not wired into the main model yet -- only "
            "'nodal' is built in-core. The arc/asset (block-angular) formulation is a "
            "planned modernization: it reaches the same optimum but is about four "
            "times slower solved monolithically (benchmarks/balance_formulation.py); "
            "its payoff is decomposition and multi-vector support. See "
            "docs/decomposition.md section 3.")
    return mode


# --------------------------------------------------------------------------- #
# 2. Problem-class detection from the built Pyomo model (the source of truth).
# --------------------------------------------------------------------------- #
def _class_from_traits(integer, quad_obj, quad_con, nonlinear):
    if nonlinear:
        return "MINLP" if integer else "NLP"
    if quad_con:                       # quadratic/conic constraint
        return "MISOCP" if integer else "SOCP"
    if quad_obj:
        return "MIQP" if integer else "QP"
    return "MILP" if integer else "LP"


def detect_problem_class(model):
    """Classify the built model by inspecting its variables, constraints and
    objective. Robust and feature-agnostic: it reflects what was actually built,
    not what flags claim. Returns one of LP/MILP/QP/MIQP/SOCP/MISOCP/NLP/MINLP."""
    from pyomo.environ import Var, Constraint, Objective

    integer = False
    for v in model.component_data_objects(Var, active=True):
        if not v.is_continuous():
            integer = True
            break

    quad_con = False
    nonlinear = False
    for c in model.component_data_objects(Constraint, active=True):
        body = getattr(c, "body", None)
        if body is None:
            continue
        deg = body.polynomial_degree()
        if deg is None:
            nonlinear = True
            break
        if deg >= 2:
            quad_con = True

    quad_obj = False
    for o in model.component_data_objects(Objective, active=True):
        deg = o.expr.polynomial_degree()
        if deg is None:
            nonlinear = True
        elif deg >= 2:
            quad_obj = True

    return _class_from_traits(integer, quad_obj, quad_con, nonlinear)


# --------------------------------------------------------------------------- #
# 3. Capability matrices: which SOLVERS solve a class, which BUILDERS build it.
#    From docs/modeling_framework_problem_classes.md (measured) — the link from
#    problem class to both the solver and the model-building library.
# --------------------------------------------------------------------------- #
SOLVER_CAPABILITIES = {
    "highs":  {"LP", "MILP", "QP", "MIQP"},
    "gurobi": {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP"},
    "cplex":  {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP"},
    "cbc":    {"LP", "MILP"},
    "glpk":   {"LP", "MILP"},
    "ipopt":  {"LP", "QP", "SOCP", "NLP"},          # continuous only (no integers)
    "mosek":  {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP", "SDP"},
}

# Model-building libraries (for solver-agnostic build choices / a future migration)
BUILDER_CAPABILITIES = {
    "pyomo":    {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP", "NLP", "MINLP"},
    "linopy":   {"LP", "MILP", "QP", "MIQP"},
    "pyoframe": {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP"},
    "jump":     {"LP", "MILP", "QP", "MIQP", "SOCP", "MISOCP", "SDP", "NLP", "MINLP"},
    "cvxpy":    {"LP", "QP", "SOCP", "SDP"},          # convex only (no nonconvex MINLP)
}


# --------------------------------------------------------------------------- #
# 4. Objective cost/revenue registry (architecture Stage B).
#    Instead of hard-coding the cost/revenue terms inside the aggregation rules,
#    features register their term variable by name and aggregation kind, and the
#    aggregation sums whatever is registered. This removes the need to edit the
#    monolithic eTotalCComponent / eTotalRComponent rules to add a cost.
#
#    kind: how the per-(period,scenario) value is formed from the term variable
#      "ps"  -> term[p,sc]
#      "psn" -> sum_n pDuration[p,sc,n] * term[p,sc,n]   (duration-weighted)
#      "psd" -> sum_d term[p,sc,d]                        (per-day terms)
# --------------------------------------------------------------------------- #
COST_KINDS = ("ps", "psn", "psd")


def register_cost(model, var_name, kind="ps"):
    """Register a cost-component variable for the objective aggregation."""
    if kind not in COST_KINDS:
        raise ValueError(f"unknown cost kind '{kind}' (use one of {COST_KINDS})")
    if not hasattr(model, "_cost_terms"):
        model._cost_terms = []
    model._cost_terms.append((var_name, kind))


def register_revenue(model, var_name, kind="ps"):
    """Register a revenue-component variable for the objective aggregation."""
    if kind not in COST_KINDS:
        raise ValueError(f"unknown revenue kind '{kind}' (use one of {COST_KINDS})")
    if not hasattr(model, "_revenue_terms"):
        model._revenue_terms = []
    model._revenue_terms.append((var_name, kind))


def seed_objective_registry(model):
    """Seed the registry with the model's built-in cost/revenue components, in the
    original order, so the aggregation is identical to the previous hard-coded sum.
    Features may register additional terms after this."""
    model._cost_terms = []
    model._revenue_terms = []
    for name in ("vTotalEleNCost", "vTotalEleXCost", "vTotalEleSUCost", "vTotalHydSUCost"):
        register_cost(model, name, "ps")
    for name in ("vTotalEleMCost", "vTotalHydMCost", "vTotalEleOCost", "vTotalHydOCost"):
        register_cost(model, name, "psn")
    for name in ("vTotalEleDCost", "vTotalHydDCost"):
        register_cost(model, name, "psd")
    register_revenue(model, "vTotalEleXRev", "ps")
    for name in ("vTotalEleMRev", "vTotalHydMRev"):
        register_revenue(model, name, "psn")


def aggregate_terms(model, optmodel, p, sc, terms):
    """Sum the registered ``terms`` for one (period, scenario), by kind."""
    expr = 0.0
    for var_name, kind in terms:
        v = optmodel.__getattribute__(var_name)
        if kind == "ps":
            expr += v[p, sc]
        elif kind == "psn":
            expr += sum(model.Par['pDuration'][p, sc, n] * v[p, sc, n] for n in model.n)
        elif kind == "psd":
            expr += sum(v[p, sc, d] for d in model.doy)
    return expr


# --------------------------------------------------------------------------- #
# 4b. Horizon-coupling aggregate-cost descriptors (temporal decomposition).
#    Most cost terms split by time window on their own: the "psn"/"psd" kinds, and the
#    "ps" terms that are plain sums over the load levels (the net-use-variable charge,
#    the energy tax, the incentive revenue -- each a sum of the grid import/export over
#    n). A few per-(period, scenario) "ps" charges do NOT split by window:
#      * a charge that is CONSTANT over the horizon (the fixed network fee), and
#      * a "sum of the N largest <quantity> per <subgroup>" peak charge.
#    The temporal Benders (oM_Decomposition.el1xr_temporal_benders) handles those two
#    shapes generically; the sector that builds such a charge declares it here as a
#    descriptor, so no sector-specific name is baked into the decomposition. Today only
#    the electricity sector has them; a new sector adds its own to seed_horizon_coupling
#    (which reads the structure model, so the descriptor is available before the
#    operating variables are built).
# --------------------------------------------------------------------------- #
def register_horizon_constant(model, cost_var, amount):
    """Declare a per-(period, scenario) cost that is CONSTANT over the horizon.
    ``cost_var`` is the cost-component Var name (removed from every window's recourse)
    and ``amount`` is the once-counted full-horizon scalar (added to the master)."""
    model._horizon_coupling = getattr(model, "_horizon_coupling", [])
    model._horizon_coupling.append(
        {"kind": "constant", "cost_var": cost_var, "amount": float(amount)})


def register_horizon_threshold(model, cost_var, native_constraints, quantity_var,
                               count, items, node_of, coeff_of, subgroups,
                               level_subgroup):
    """Declare a 'sum of the N largest <quantity> per <subgroup>' peak charge for the
    threshold-LP reformulation. Fields (see ``el1xr_temporal_benders`` for the use)::

      cost_var           native peak-cost Var name (pinned to 0; the LP replaces it)
      native_constraints native peak constraint names to deactivate
      quantity_var       metered quantity Var name, indexed (period, scenario, n, node)
      count              N, the number of peaks
      items              the charge-bearing keys (e.g. the retailers)
      node_of            item -> node, to index the quantity Var
      coeff_of           item -> cost per unit threshold (already divided by N)
      subgroups          the per-period subgroups the top-N is taken within (months)
      level_subgroup     attr name of the (load level, subgroup) membership pairs on the
                         built model (e.g. ``n2m``)
    """
    model._horizon_coupling = getattr(model, "_horizon_coupling", [])
    model._horizon_coupling.append(
        {"kind": "threshold", "cost_var": cost_var,
         "native_constraints": tuple(native_constraints), "quantity_var": quantity_var,
         "count": int(count), "items": list(items), "node_of": dict(node_of),
         "coeff_of": dict(coeff_of), "subgroups": list(subgroups),
         "level_subgroup": level_subgroup})


def register_horizon_unsupported(model, reason):
    """Mark a horizon-coupling charge the temporal split cannot decompose yet, so the
    decomposition raises a clear error instead of returning a wrong objective."""
    model._horizon_coupling = getattr(model, "_horizon_coupling", [])
    model._horizon_coupling.append({"kind": "unsupported", "reason": reason})


# The "ps" composite cost/revenue terms the temporal split knows how to decompose. A
# new per-(period, scenario) composite outside these is refused by the split's guard;
# to handle it, register its non-separable parts above and extend these sets.
# vTotalEleSUCost / vTotalHydSUCost are plain sums of per-event start-up/shut-down costs
# over the load levels, so each window sums its own start-ups -- they split additively
# across windows like the net-use/tax sums, with no master coordination.
TEMPORAL_HANDLED_PS_COST = {"vTotalEleNCost", "vTotalEleXCost", "vTotalEleSUCost", "vTotalHydSUCost"}
TEMPORAL_HANDLED_PS_REV = {"vTotalEleXRev"}


def seed_horizon_coupling(model):
    """Seed the built-in (electricity) horizon-coupling descriptors on ``model``.

    Reads ``model.Par`` and the sets only, so it runs on a structure-only model
    (``oM_Sequence.build_structure``). The electricity fixed network charge is a
    constant; the peak demand charge is the sum of the N largest grid imports per month
    per retailer (a threshold). A Daily-tariff peak charge is not yet supported by the
    reformulation, so it is marked unsupported rather than mis-handled. A new sector
    with such a charge appends its own descriptor here."""
    model._horizon_coupling = []
    Par = model.Par
    factor1 = float(model.factor1)
    er = list(getattr(model, "er", []))
    months = list(getattr(model, "moy", []))

    def _moms(e):
        return float(Par['pEleRetMoms'][e])

    # fixed network charge: a per-retailer, per-month constant (fastavgift)
    netfix = sum(float(Par['pEleRetFastavgift'][e]) * factor1 * len(months) * (1 + _moms(e))
                 for e in er)
    register_horizon_constant(model, "vTotalEleNetUseFixCost", netfix)

    # peak demand charge: the sum of the N largest grid imports per month per retailer
    n_peaks = int(Par['pParNumberPowerPeaks'])

    def _tariff(e):
        return float(Par['pEleRetPowerTariff'][e])

    def _tariff_type(e):
        return str(Par['pEleRetTariffType'][e])

    peak_er = [e for e in er
               if n_peaks > 0 and _tariff(e) != 0 and _tariff_type(e) == 'Hourly']
    if n_peaks > 0 and any(_tariff(e) != 0 and _tariff_type(e) == 'Daily' for e in er):
        register_horizon_unsupported(model, "a Daily power-tariff peak charge")
    if peak_er:
        register_horizon_threshold(
            model, cost_var="vTotalElePeakCost",
            native_constraints=("eTotalElePeakCost", "eElePeakHourValue",
                                "eElePeakHourInd_C1", "eElePeakHourInd_C2",
                                "eElePeakNumberMonths"),
            quantity_var="vEleImport", count=n_peaks, items=peak_er,
            node_of={e: Par['pEleRetNode'][e] for e in peak_er},
            coeff_of={e: _tariff(e) * factor1 * (1 + _moms(e)) / n_peaks for e in peak_er},
            subgroups=months, level_subgroup="n2m")
    return model


def solvers_for(problem_class):
    return sorted(s for s, cap in SOLVER_CAPABILITIES.items() if problem_class in cap)


def builders_for(problem_class):
    return sorted(b for b, cap in BUILDER_CAPABILITIES.items() if problem_class in cap)


def solver_supports(solver, problem_class):
    name = str(solver).lower()
    for key, cap in SOLVER_CAPABILITIES.items():
        if key in name:
            return problem_class in cap
    return True            # unknown solver: do not block, just cannot vouch


def check_solver_for_model(model, solver):
    """Detect the model's class and check the chosen solver can solve it.

    Returns ``(problem_class, ok, message)``. ``ok`` is False only when the class
    is known-incompatible with a known solver (e.g. a SOCP case on HiGHS); the
    message also lists the solvers and builders that do support the class.
    """
    pc = detect_problem_class(model)
    ok = solver_supports(solver, pc)
    msg = (f"problem class = {pc}; solver '{solver}' "
           f"{'supports' if ok else 'does NOT support'} it. "
           f"solvers for {pc}: {', '.join(solvers_for(pc))}; "
           f"builders for {pc}: {', '.join(builders_for(pc))}.")
    return pc, ok, msg
