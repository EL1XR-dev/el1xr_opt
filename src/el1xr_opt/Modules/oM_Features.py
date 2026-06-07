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
    return parameters_dict


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
    for name in ("vTotalEleNCost", "vTotalEleXCost"):
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


def solvers_for(problem_class):
    return sorted(s for s, cap in SOLVER_CAPABILITIES.items() if problem_class in cap)


def builders_for(problem_class):
    return sorted(b for b, cap in BUILDER_CAPABILITIES.items() if problem_class in cap)


def solver_supports(solver, problem_class):
    base = str(solver).lower().split("_")[0].replace("appsi", "") or str(solver).lower()
    for key, cap in SOLVER_CAPABILITIES.items():
        if key in str(solver).lower():
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
