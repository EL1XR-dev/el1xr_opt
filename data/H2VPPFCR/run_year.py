"""Full-year (8736 h) H2VPP FCR run for the Comillas remote desktop (Gurobi).

Regenerates the case at the year horizon from the real 2025 data, solves on Gurobi,
and writes a results summary. Heavy: this is a year-long investment+commitment MILP,
intended for a workstation with Gurobi, not a laptop.

Usage (from the repo root, with the el1xr_opt env active and PYTHONPATH=model/src):
    H2VPP_HORIZON=year python experiments/h2vpp_fcr/run_year.py

Environment knobs (all optional):
    H2VPP_HORIZON   week | month | year      (default year here; set by this script)
    FIRM            1 to make the HRS demand a firm must-serve contract (default 0)
    TIMELIMIT       Gurobi seconds            (default 21600 = 6 h)
    MIPGAP          target relative gap       (default 0.01)
    THREADS         Gurobi threads            (default: all cores)
"""
import os, sys, json, shutil, datetime, importlib.util
from pathlib import Path

os.environ.setdefault("H2VPP_HORIZON", "year")
FIRM = os.environ.get("FIRM", "0") == "1"
TIMELIMIT = int(os.environ.get("TIMELIMIT", "21600"))
MIPGAP = float(os.environ.get("MIPGAP", "0.01"))
THREADS = os.environ.get("THREADS")

REPO = Path(__file__).resolve().parents[2]
# el1xr_opt sits at model/src in the paper's companion repo and at src/ in el1xr_opt
# itself, so this file is the same in both; an installed package wins over both.
for _cand in (REPO / "model" / "src", REPO / "src"):
    if (_cand / "el1xr_opt").is_dir():
        sys.path.insert(0, str(_cand))
        break

# --- regenerate the case at the year horizon ---
spec = importlib.util.spec_from_file_location("bc_year", Path(__file__).resolve().parent / "build_case.py")
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
# Horizon comes from H2VPP_HORIZON (week | month | year). Year is the headline solve;
# week/month are for validation that the case builds and solves on this machine.
HZ = bc.HORIZON
CASE = bc.CASE
# Demand mode (elastic | firm | quota) is owned by build_case.py, driven by the same env
# (H2VPP_DEMAND_MODE, or FIRM=1 -> firm). Read it back here for the work dir and summary.
MODE = bc.DEMAND_MODE

# SWEEP_PREBUILT_WORK=<dir>: the Mode B sweep runner has already built the case once and
# written this cell's (overlaid) inputs into <dir>/<CASE>. Skip build_case + the copy and
# solve that work dir as-is. Everything downstream (Option patch, build_model, post-build
# edits, solve, summary) is identical, so the solve path stays single-sourced in this file.
PREBUILT = os.environ.get("SWEEP_PREBUILT_WORK")

# OUT_BASE redirects the (large) build + results output to another disk (e.g. D:\h2vpp_work on the
# Comillas box, which has far more free space than C:). Unset = the default in-repo layout, so
# existing/local runs are unchanged. When set, builds go to <OUT_BASE>\inputs and results to
# <OUT_BASE>\results\h2vpp_fcr.
_OUTBASE = os.environ.get("OUT_BASE")
_BUILD_BASE   = (Path(_OUTBASE) / "inputs")            if _OUTBASE else (REPO / "experiments" / "h2vpp_fcr" / "inputs")
_RESULTS_BASE = (Path(_OUTBASE) / "results" / "h2vpp_fcr") if _OUTBASE else (REPO / "results" / "h2vpp_fcr")

# Build into a PER-VARIANT inputs dir, not the shared inputs/<CASE>. build_case writes the
# case CSVs to bc.OUT_DIR; under a parallel runner two jobs building into the same shared
# path race and clobber each other's inputs (observed: A2 and B0 solved identical problems).
# A per-variant OUT_DIR isolates each job's build. RUN_TAG keeps sweep points distinct too.
VARIANT = bc.VARIANT
if not PREBUILT:
    _buildtag = f"{VARIANT}" if VARIANT else MODE
    _buildtag += f"_{os.environ.get('RUN_TAG','')}" if os.environ.get("RUN_TAG") else ""
    _BUILD_BASE.mkdir(parents=True, exist_ok=True)
    bc.OUT_DIR = _BUILD_BASE / f"{CASE}__build_{_buildtag}"
    print(f"building {CASE} {HZ} case (factor1={bc.FACTOR1}, HNSCost={bc.HNSCOST}, mode={MODE}, "
          f"N_LOADLEVELS={bc.N_LOADLEVELS}) -> {bc.OUT_DIR.name} ...", flush=True)
    bc.build()

# --- solve on Gurobi in a clean work dir (one per horizon/variant, else per demand mode) ---
_modesuffix = {"elastic": "", "firm": "_firm", "shift": "_shift"}.get(MODE, f"_{MODE}")
work_name = f"work_{HZ}_{VARIANT}" if VARIANT else f"work_{HZ}{_modesuffix}"
# Optional tag to keep sweep points (e.g. degradation-cost scale) in distinct work dirs.
RUN_TAG = os.environ.get("RUN_TAG", "")
if RUN_TAG:
    work_name += f"_{RUN_TAG}"
if PREBUILT:
    work = Path(PREBUILT)
    wc = work / CASE
    print(f"SWEEP_PREBUILT_WORK: solving prebuilt inputs at {work} (build skipped)", flush=True)
else:
    work = _RESULTS_BASE / work_name
    wc = work / CASE
    if wc.exists():
        shutil.rmtree(wc)
    wc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bc.OUT_DIR, wc)   # per-variant build dir (race-safe under parallel runners)

# Optional feature flags patched into the work-dir Option CSV by env knob so build_model picks
# them up. All default unset = existing behaviour. PEAK_THRESHOLD_LP -> exact binary-free CVaR
# peak charge; STOR_FCR_LEG -> leg-exclusive storage FCR (closes the simultaneous
# charge+discharge reserve loophole).
_opt_env = {"PEAK_THRESHOLD_LP": "IndPeakThresholdLP", "STOR_FCR_LEG": "IndStorFCRLegExclusive",
            "ELE_3STATE_TIGHT": "IndElectrolyser3StateTight",
            "ELE_OPER_SYMBREAK": "IndElectrolyserOperSymBreak",
            "ELE_PWL_RELAX": "IndElectrolyserPWLRelax",
            "RESERVE_DELIVERY": "IndReserveDeliverySettlement"}
_opt_set = {col: int(os.environ[ev]) for ev, col in _opt_env.items() if os.environ.get(ev) is not None}
if _opt_set:
    import pandas as _pd
    _optf = wc / f"oM_Data_Option_{CASE}.csv"
    _od = _pd.read_csv(_optf)
    for _col, _v in _opt_set.items():
        _od[_col] = _v
    _od.to_csv(_optf, index=False)
    print(f"option overrides {_opt_set} -> {_optf.name}", flush=True)

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from el1xr_opt.Modules.oM_Sequence import build_model

NOW = datetime.datetime.now().replace(second=0, microsecond=0)

# BENDERS=1 solves the INTEGER model by temporal decomposition (investment + storage-boundary
# inventory in the master, integer operating recourse per time block) instead of the monolith.
# LP optimality cuts fail on the binary subproblems (no LP duals), so the default cut family is
# the integer-aware 'lagrangian' (SDDiP-style), which needs a MILP solver with master duals
# (gurobi). Opt-in and separate from the LP path -- this is the integer-decomposition route.
if os.environ.get("BENDERS") == "1":
    from el1xr_opt.Modules.oM_Decomposition import el1xr_temporal_benders, BendersConfig
    nblocks = int(os.environ.get("BENDERS_BLOCKS", "12"))
    cut = os.environ.get("BENDERS_CUT", "lagrangian")
    bsolver = os.environ.get("BENDERS_SOLVER", "gurobi")
    cfg = BendersConfig(max_iterations=int(os.environ.get("BENDERS_ITERS", "60")),
                        relative_gap=float(os.environ.get("BENDERS_GAP", "1e-3")))
    print(f"BENDERS: temporal decomposition (blocks={nblocks}, cut={cut}, solver={bsolver}) ...", flush=True)
    res = el1xr_temporal_benders(str(work), CASE, NOW, n_time_blocks=nblocks, solver=bsolver,
                                 config=cfg, cut_mode=cut)
    summary = {"case": CASE, "variant": VARIANT or "A3", "mode": MODE, "method": "temporal_benders", "cut_mode": cut,
               "n_blocks": nblocks, "horizon": bc.HORIZON, "factor1": bc.FACTOR1,
               "converged": res.get("converged"), "objective": res.get("objective"),
               "lower_bound": res.get("lower_bound"), "gap": res.get("gap"),
               "iterations": res.get("iterations")}
    out = work / f"summary_{CASE}.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\n" + "=" * 60 + "\n" + json.dumps(summary, indent=2) + "\n" + "=" * 60, flush=True)
    print(f"summary -> {out}", flush=True)
    raise SystemExit(0)

m = build_model(str(work), CASE, NOW, "False")

# LP=1 relaxes all integer/binary vars to continuous. For the year horizon the full MILP
# root relaxation alone takes ~20 min on barrier and the MIP rarely finds an incumbent in
# hours; the LP relaxation (continuous commitment) is the tractable headline solve and gives
# the FCR split + sizing directly. Barrier solves it in ~20 min.
LP = os.environ.get("LP", "0") == "1"
if LP:
    pyo.TransformationFactory("core.relax_integer_vars").apply_to(m)
    print("LP=1: relaxed integer/binary vars to continuous", flush=True)


def _envn(name, default, cast=float):
    v = os.environ.get(name)
    return cast(v) if v not in (None, "") else default


# MIN_BID_FLOOR (MW): market minimum bid size. Enforce a semi-continuous floor on the
# plant-total reserve bid per product per hour (bid = 0 or >= floor). Needs integrality, so it
# applies only to the MILP (not LP=1). Adds one binary per product-hour -- keep the horizon short.
_min_bid = _envn("MIN_BID_FLOOR", 0.0)
if _min_bid > 0 and not LP:
    _BIGM = 100.0
    m.mbfloor = pyo.Block()
    _nb = 0
    for _tag, _var in [("DUp", m.vEleFreqContReserveDisUpwardBid),
                       ("DDn", m.vEleFreqContReserveDisDownwardBid),
                       ("Nor", m.vEleFreqContReserveNorBid)]:
        _keys = {}
        for _idx in _var:
            _keys.setdefault(tuple(_idx[:3]), []).append(_idx)
        _psn = list(_keys); _rng = list(range(len(_psn)))
        _u = pyo.Var(_rng, domain=pyo.Binary)
        m.mbfloor.add_component(f"u_{_tag}", _u)
        m.mbfloor.add_component(f"lo_{_tag}", pyo.Constraint(
            _rng, rule=lambda b, i, _var=_var, _keys=_keys, _psn=_psn, _u=_u:
            sum(_var[k] for k in _keys[_psn[i]]) >= _min_bid * _u[i]))
        m.mbfloor.add_component(f"hi_{_tag}", pyo.Constraint(
            _rng, rule=lambda b, i, _var=_var, _keys=_keys, _psn=_psn, _u=_u:
            sum(_var[k] for k in _keys[_psn[i]]) <= _BIGM * _u[i]))
        _nb += len(_psn)
    print(f"MIN_BID_FLOOR={_min_bid} MW: semi-continuous plant-total bids ({_nb} binaries)", flush=True)


# ELE_RAMP_CAP=1: cap each electrolyser's FCR-D-up bid by the reserve it can ramp within the
# 7.5 s FCR-D window: bid <= rho * (7.5/0.86) * built consumption capacity, rho = load ramp rate.
# Sources for the assumptions (also to cite in the paper):
#   - FCR-D full-activation criterion (>=86% within 7.5 s): Nordic TSOs, "Technical Requirements
#     for FCR Provision in the Nordic Synchronous Area" v1.1 (2025).
#   - Electrolyser ramp rates rho: AEL ~0.5-5 %/s, PEM ~10 %/s -- Cozzolino & Bella (2024,
#     Front. Energy Res. 12:1358333) from Bertuccioli et al. (2014). Defaults AEL 2 %/s, PEM 10 %/s.
#   - Conservative direction: uses the datasheet ramp-UP rate as a proxy; load-DOWN (the upward-FCR
#     direction) is rectifier-limited and faster -- Dorn et al. (2026, arXiv:2602.20842).
#   - Min-load FCR headroom (already enforced in the model) & AEL FCR feasibility: Cammann, Alves &
#     Jaeschke (2024, IECON); QualyGridS (Reissner et al. 2020, Clean Energy 4(4):379).
# Applies to FCR-D only (FCR-N's 60/180 s window makes a ramp cap non-binding). rho env-tunable.
if os.environ.get("ELE_RAMP_CAP") == "1":
    _rho = {'AEL': _envn("AEL_RAMP_PCTS", 2.0) / 100.0, 'PEM': _envn("PEM_RAMP_PCTS", 10.0) / 100.0}
    _fac = 7.5 / 0.86
    m.elerampcap = pyo.Block()

    def _ramp(b, p, sc, n, u):
        tech = 'AEL' if 'AEL' in u else ('PEM' if 'PEM' in u else None)
        if tech is None:
            return pyo.Constraint.Skip
        return m.vEleFreqContReserveDisUpwardBid[p, sc, n, u] \
            <= _rho[tech] * _fac * m.Par['pHydMaxCharge'][u][p, sc, n] * m.vHydGenInvest[u]
    m.elerampcap.cap = pyo.Constraint(m.psne2h, rule=_ramp)
    print(f"ELE_RAMP_CAP: FCR-D-up ramp cap (AEL {_rho['AEL']*100:.1f}%/s, PEM {_rho['PEM']*100:.1f}%/s)", flush=True)


# FIX_INVEST=path/to/summary_H2VPPFCR.json: fix every investment variable at the builds of a
# previous solve (fix-and-solve). Used for the integer-consistency anchor: fix the sizing at
# the year-LP optimum, then solve the operating problem as a MILP on a shorter horizon. Build
# fractions are stored raw in the summary; the connection capacity is stored in MW as
# phys(var)/1000 = var/(factor1*1000), so the inverse is MW * 1000 * factor1.
if os.environ.get("FIX_INVEST"):
    _fs = json.loads(Path(os.environ["FIX_INVEST"]).read_text())
    _nfix = 0
    for _vr, _key in ((m.vEleGenInvest, "ele_build"), (m.vHydGenInvest, "hyd_build"),
                      (m.vHydCompInvest, "comp_build")):
        for _u, _x in (_fs.get(_key) or {}).items():
            try:
                _vr[_u].fix(float(_x))
                _nfix += 1
            except KeyError:
                print(f"FIX_INVEST: unit {_u} not an investment candidate here, skipped", flush=True)
    if hasattr(m, "vEleConnCap") and _fs.get("ele_conn_cap_MW") is not None:
        m.vEleConnCap.fix(float(_fs["ele_conn_cap_MW"]) * 1000.0 * float(m.factor1))
        _nfix += 1
    print(f"FIX_INVEST: fixed {_nfix} investment variables from {os.environ['FIX_INVEST']}", flush=True)

# FIX_RESERVE_SPLIT=path/to/lp_summary.json: pin each asset's per-product month reserve total to
# the values in that summary's fcr_sum_by_asset, within a tolerance band (FIX_RESERVE_TOL, default
# 1%). Paired with FIX_INVEST on the fixed-build MILP check, this removes the reserve-split
# degeneracy: instead of reporting an arbitrary alternate-optimum split, the MILP must reproduce
# the linear-relaxation's reserve role and we read off whether that role is deliverable under
# integer commitment and at what cost (infeasible => the LP over-books reserve the units can't
# sustain with integer commitment).
_frs = os.environ.get("FIX_RESERVE_SPLIT")
if _frs:
    _fd = (json.loads(Path(_frs).read_text()).get("fcr_sum_by_asset") or {})
    _tol = float(os.environ.get("FIX_RESERVE_TOL", "0.01"))
    _rscale = float(os.environ.get("FIX_RESERVE_SCALE", "1.0"))
    _prodmap = {"FCR-D up": getattr(m, "vEleFreqContReserveDisUpwardBid", None),
                "FCR-D down": getattr(m, "vEleFreqContReserveDisDownwardBid", None),
                "FCR-N": getattr(m, "vEleFreqContReserveNorBid", None)}
    # FIX_RESERVE_LEVEL=unit (default) pins each unit's per-product total; =class pins only the
    # aggregate battery-class vs electrolyser-class total per product -- the latter is the role
    # (ranking) test: it lets integer commitment reallocate freely within a class but forces the
    # relaxation's between-class split, so infeasibility means the ROLE itself is not deliverable.
    _rlevel = os.environ.get("FIX_RESERVE_LEVEL", "unit").lower()
    def _uclass(u):
        return "bat" if (u.startswith("BESS") or u.startswith("FC")) else "ele"
    m.cFixReserveSplit = pyo.ConstraintList()
    _nrs = 0
    for _prod, _var in _prodmap.items():
        if _var is None:
            continue
        _byu = {}
        for _idx in _var:
            _byu.setdefault(_idx[-1], []).append(_idx)
        _tgt = _fd.get(_prod) or {}
        if _rlevel == "class":
            _groups = {}   # class -> (target_sum, [indices])
            for _u, _target in _tgt.items():
                if _u not in _byu:
                    continue
                _c = _uclass(_u)
                _g = _groups.setdefault(_c, [0.0, []])
                _g[0] += float(_target)
                _g[1].extend(_byu[_u])
            _items = [(_c, _g[0], _g[1]) for _c, _g in _groups.items()]
        else:
            _items = [(_u, float(_target), _byu[_u]) for _u, _target in _tgt.items() if _u in _byu]
        for _lbl, _tval, _idxs in _items:
            _expr = sum(_var[_i] for _i in _idxs)
            _t = _tval * _rscale
            m.cFixReserveSplit.add(_expr <= _t * (1.0 + _tol) + 1e-6)
            if _t * (1.0 - _tol) > 0:
                m.cFixReserveSplit.add(_expr >= _t * (1.0 - _tol))
            _nrs += 1
    print(f"FIX_RESERVE_SPLIT: pinned {_nrs} per-{_rlevel} per-product reserve totals "
          f"(scale {_rscale:g}, +-{_tol:.1%}) from {_frs}", flush=True)

# COMMIT_AHEAD=1: pin each FCR capacity bid to a flat level over the horizon -- committed on
# D-2 information, with no tuning to the realised hourly prices. This is the foresight-rent check
# (reviewer M1): the profit gap to the free-foresight solve bounds the value that perfect price
# foresight confers on the capacity bids. Each bid variable is tied equal across all time steps
# within its (period, scenario, unit) group; the optimiser still picks the best flat, deliverable
# level, and the endurance and ramp gates still bind every hour.
_ca_mode = os.environ.get("COMMIT_AHEAD", "0").lower()
if _ca_mode in ("1", "flat", "diurnal"):
    # flat: one bid level for the whole horizon (most restrictive). diurnal: an hour-of-day
    # profile repeated over the horizon -- the plant commits a 24 h bid schedule from forecast,
    # which its predictable diurnal running pattern supports (the fairer committed-ahead).
    from collections import defaultdict as _dd
    _bidvars = [getattr(m, _nm) for _nm in
                ("vEleFreqContReserveDisUpwardBid", "vEleFreqContReserveDisDownwardBid",
                 "vEleFreqContReserveNorBid") if hasattr(m, _nm)]
    _diurnal = (_ca_mode == "diurnal")
    _pos = {}
    if _diurnal:
        _all_n = sorted({_idx[2] for _bv in _bidvars for _idx in _bv})
        _pos = {n: i for i, n in enumerate(_all_n)}
    m.cCommitAhead = pyo.ConstraintList()
    _nca = 0
    for _bv in _bidvars:
        _grp = _dd(list)
        for _idx in _bv:
            _p, _sc, _n, _u = _idx
            _key = (_p, _sc, _u, _pos[_n] % 24) if _diurnal else (_p, _sc, _u)
            _grp[_key].append(_n)
        for _k, _ns in _grp.items():
            _p, _sc, _u = _k[0], _k[1], _k[2]
            _ns.sort()
            _n0 = _ns[0]
            for _n in _ns[1:]:
                m.cCommitAhead.add(_bv[_p, _sc, _n, _u] == _bv[_p, _sc, _n0, _u])
                _nca += 1
    print(f"COMMIT_AHEAD={_ca_mode}: pinned {len(_bidvars)} FCR bid families "
          f"({'hour-of-day profile' if _diurnal else 'flat'}; {_nca} tie constraints)", flush=True)


S = SolverFactory("gurobi")
# Solver options are env-tunable. For a MIP, Gurobi IGNORES Crossover=0 (you must use
# NodeMethod=2 to skip crossover); for a pure LP, Crossover=0 gives the barrier optimum
# directly and is the fast path. DualReductions=0 makes an unsolved MIP return a definite
# status instead of the ambiguous "infeasible or unbounded".
opts = dict(
    Method=_envn("METHOD", 2, int),
    Crossover=_envn("CROSSOVER", 0, int),
    Presolve=_envn("PRESOLVE", 2, int),
    NumericFocus=_envn("NUMERICFOCUS", 2, int),
    FeasibilityTol=_envn("FEASTOL", 1e-6),
    TimeLimit=TIMELIMIT,
)
if not LP:
    opts.update(
        MIPFocus=_envn("MIPFOCUS", 1, int),
        NodeMethod=_envn("NODEMETHOD", 2, int),  # barrier at nodes, no crossover
        DualReductions=_envn("DUALRED", 0, int),
        MIPGap=MIPGAP,
    )
_bh = _envn("BARHOMOGENEOUS", None, int)
if _bh is not None:
    opts["BarHomogeneous"] = _bh
# ScaleFlag tames a large matrix coefficient range (the year LP barrier hit numerical
# trouble from poor scaling); 2 = aggressive geometric-mean scaling. Env-tunable.
# PRACTICE (Phase 1, 2026-06-22): with MONEY_BASE=1000 the matrix span is down to ~7.6 oom
# and Gurobi's default scaling (ScaleFlag=-1) handles it -- leave ScaleFlag UNSET for the
# headline runs. Reach for ScaleFlag=2 (+ NumericFocus / BarHomogeneous / concurrent) only
# on a residual hard case, not by default. Per-unit scaling fixes the structure that
# solver auto-scaling can only approximate; see notes/scalability_conditioning_investigation.md.
_sf = _envn("SCALEFLAG", None, int)
if _sf is not None:
    opts["ScaleFlag"] = _sf
if THREADS:
    opts["Threads"] = int(THREADS)
log = str(work / f"gurobi_{CASE}.log")


def _gurobi_solve(method=None, crossover=None, dualred=None, logfile=log):
    o = dict(opts)
    if method is not None:
        o["Method"] = method
    if crossover is not None:
        o["Crossover"] = crossover
    if dualred is not None:
        o["DualReductions"] = dualred
    S.options.update(o)
    print(f"solving on gurobi (opts={o}); log -> {logfile}", flush=True)
    r = S.solve(m, tee=True, logfile=logfile, load_solutions=False)
    t = str(r.solver.termination_condition)
    hs = bool(getattr(r, "solution", None)) and len(r.solution) > 0
    print(f"termination = {t}", flush=True)
    return r, t, hs


SOLVER = os.environ.get("SOLVER", "gurobi").lower()
res = None
if SOLVER == "highs":
    # Free-solver path for the continuous (LP) model -- used for local sensitivity sweeps
    # when no Gurobi licence is available. Integer models should still use Gurobi. Reuses all
    # the summary extraction below (appsi loads the solution straight into the model).
    from pyomo.contrib.appsi.solvers.highs import Highs
    from pyomo.contrib.appsi.base import TerminationCondition as _ATC
    _h = Highs(); _h.config.stream_solver = True; _h.config.time_limit = TIMELIMIT
    print("solving on HiGHS (appsi); Gurobi options ignored", flush=True)
    _hr = _h.solve(m)
    tc = str(_hr.termination_condition)
    have_sol = _hr.termination_condition == _ATC.optimal
    if have_sol:
        _hr.solution_loader.load_vars()
else:
    res, tc, have_sol = _gurobi_solve()

# Concurrent fallback (opt out with CONCURRENT_FALLBACK=0). When the primary method returns no
# usable solution -- e.g. the barrier ends "sub-optimal/numerical" on a badly degenerate LP such
# as the FCR-N-only case, whose optimum provides no reserve and leaves the reserve constraints
# slack -- retry once with the concurrent method (3) so primal and dual simplex run alongside the
# barrier and one of them finishes where the barrier choked. Crossover on + DualReductions off give
# a clean vertex and a definite status. This solved B1 (year) when barrier and dual simplex alone
# could not.
if not have_sol and SOLVER != "highs" and os.environ.get("CONCURRENT_FALLBACK", "1") == "1" and opts.get("Method") != 3:
    print("no usable solution from primary method; retrying with concurrent (Method=3)", flush=True)
    res, tc, have_sol = _gurobi_solve(method=3, crossover=1, dualred=0,
                                      logfile=str(work / f"gurobi_{CASE}_concurrent.log"))

# Load a solution only if Gurobi returned one; otherwise Pyomo raises on an aborted,
# solutionless result (the firm case hit the time limit with only a bound).
if have_sol and res is not None:
    m.solutions.load_from(res)

# --- capture results ---
f1 = float(m.factor1)
# Money-base prescale (build_case MONEY_BASE): the solve is in MONEY_BASE-SEK, so multiply the
# reported objective and bounds back to SEK. Physical quantities (energy, builds, FCR) are unaffected.
mb = float(os.environ.get("MONEY_BASE", "1.0"))
val = lambda v: float(pyo.value(v))
phys = lambda x: x / f1
cost = None
if have_sol:
    try:
        cost = val(m.eTotalSCost) * mb
    except Exception:
        cost = None
summary = {"case": CASE, "variant": VARIANT or "A3", "mode": MODE, "firm": FIRM, "horizon": bc.HORIZON, "factor1": f1,
           "money_base": mb, "hnscost": bc.HNSCOST, "termination": tc, "timelimit_s": TIMELIMIT, "mipgap_target": MIPGAP,
           "currency": bc.CURRENCY, "eTotalSCost_SEK": cost}   # eTotalSCost_SEK holds the model currency (see 'currency')
for k, attr in (("bound_lower", "lower_bound"), ("bound_upper", "upper_bound")):
    try:
        summary[k] = float(getattr(res.problem, attr)) * mb
    except Exception:
        summary[k] = None
if cost is not None:
    # peak (demand) charge component, for comparing big-M vs CVaR peak formulations
    try:
        summary["peak_cost_SEK"] = sum(val(m.vTotalElePeakCost[i]) for i in m.vTotalElePeakCost) * mb
    except Exception:
        summary["peak_cost_SEK"] = None
    summary["HNS_total_kgH2"] = phys(sum(val(m.vHNS[i]) for i in m.vHNS))
    # How the hydrogen demand is actually met: served on-site vs bought from the import
    # backstop. With elastic (price-responsive) demand, unmet demand is FOREGONE (not HNS),
    # so a near-zero HNS can still hide a hydrogen business that produced nothing -- these
    # two totals make that visible.
    summary["H2_demand_served_kgH2"] = phys(sum(val(m.vHydDemand[i]) for i in m.vHydDemand))
    summary["H2_import_buy_kgH2"] = phys(sum(val(m.vHydBuy[i]) for i in m.vHydBuy))
    summary["ele_build"] = {u: val(m.vEleGenInvest[u]) for u in m.egc}
    summary["hyd_build"] = {u: val(m.vHydGenInvest[u]) for u in m.hgc}
    summary["comp_build"] = {u: val(m.vHydCompInvest[u]) for u in m.hgcompc}
    # standalone Technology="Compressor" units (PRESSURE_NODES) are sized by vHydCompBuild over hcc,
    # not the tank-welded vHydCompInvest above; include them so the compressor size is reported.
    if hasattr(m, "vHydCompBuild"):
        summary["comp_build"].update({u: val(m.vHydCompBuild[u]) for u in m.hcc})
    # Invested grid-connection capacity (MW). Present only when the connection-investment
    # feature is active (pParEleConnInvestCost > 0); phys() -> kW, /1000 -> MW.
    try:
        summary["ele_conn_cap_MW"] = phys(val(m.vEleConnCap)) / 1000.0 if hasattr(m, "vEleConnCap") else None
    except Exception:
        summary["ele_conn_cap_MW"] = None

    # FCR provision split: sum each product's bid over all load levels, per asset
    # (the last index is the asset). Shares are scale-invariant, so this captures
    # the headline battery-vs-electrolyser split without the model's result tables.
    fcr_vars = {
        "vEleFreqContReserveDisUpwardBid": "FCR-D up",
        "vEleFreqContReserveDisDownwardBid": "FCR-D down",
        "vEleFreqContReserveNorBid": "FCR-N",
    }
    fcr = {}
    for vname, label in fcr_vars.items():
        comp = getattr(m, vname, None)
        if comp is None:
            continue
        by_asset = {}
        for idx in comp:
            asset = idx[-1]
            by_asset[asset] = by_asset.get(asset, 0.0) + val(comp[idx])
        fcr[label] = by_asset
    summary["fcr_sum_by_asset"] = fcr

    # Storage dual-leg FCR simultaneity: hours where a storage unit bids FCR-up from BOTH the
    # charge and the discharge leg at once (the simultaneous charge+discharge reserve loophole).
    # With leg-exclusive FCR (STOR_FCR_LEG=1) this should drop toward zero.
    try:
        dual = {}
        for egs in m.egs:
            cnt = 0
            for (pp, ss, nn) in m.psn:
                up_cha = val(m.vEleFreqContReserveDisUpCha[pp, ss, nn, egs]) + val(m.vEleFreqContReserveNorUpCha[pp, ss, nn, egs])
                up_dis = val(m.vEleFreqContReserveDisUpDis[pp, ss, nn, egs]) + val(m.vEleFreqContReserveNorUpDis[pp, ss, nn, egs])
                if up_cha > 1e-3 and up_dis > 1e-3:
                    cnt += 1
            dual[egs] = cnt
        summary["fcr_dual_leg_hours"] = dual
    except Exception:
        pass

# Conditioning probe (opt-in -- the measurement backbone for the scaling work). CONDITIONING=1
# records the constraint-matrix and variable-bound coefficient ranges (no solve, but iterates
# every constraint, so it is slow at year scale -- run it deliberately). KAPPA=1 additionally
# solves once with a simplex basis to read Gurobi's condition number (KappaExact); needs gurobipy.
# A lower matrix oom / kappa after a rescale (e.g. MONEY_BASE) is the evidence the rescale helped.
if os.environ.get("CONDITIONING") == "1" or os.environ.get("KAPPA") == "1":
    spec_c = importlib.util.spec_from_file_location(
        "conditioning", REPO / "analysis" / "conditioning.py")
    cond = importlib.util.module_from_spec(spec_c); spec_c.loader.exec_module(cond)
    summary["conditioning"] = {}
    if os.environ.get("CONDITIONING") == "1":
        print("conditioning: computing matrix + bound ranges ...", flush=True)
        summary["conditioning"]["ranges"] = cond.matrix_and_bound_ranges(m)
    if os.environ.get("KAPPA") == "1":
        print("conditioning: simplex probe for KappaExact ...", flush=True)
        summary["conditioning"]["kappa"] = cond.kappa_exact(m)

out = work / f"summary_{CASE}.json"
out.write_text(json.dumps(summary, indent=2))
print("\n" + "=" * 60, flush=True)
print(json.dumps(summary, indent=2), flush=True)
print("=" * 60, flush=True)
print(f"summary -> {out}", flush=True)

# Optional full results output (all oT_* tables, incl. hourly dispatch) -> work/CASE/results.duckdb.
# Opt-in (FULL_OUTPUT=1) because it is only needed for dispatch figures, not the matrix summary.
if os.environ.get("FULL_OUTPUT") == "1" and have_sol:
    from el1xr_opt.Modules.oM_OutputData_duckdb import save_to_duckdb
    save_to_duckdb(str(work), CASE, m, m, date=NOW, solver="gurobi")
    print(f"full output -> {wc / 'results.duckdb'}", flush=True)

# Slim hourly dispatch archive (SLIM_OUTPUT=1): a curated set of the time-resolved series, in
# physical units (/factor1), written as one tidy parquet per case. Small (a few MB), columnar and
# queryable -- the reusable record so we never re-solve just to recover a dispatch detail. Written
# via DuckDB so it needs no pyarrow. Money-base independent (only physical quantities).
if os.environ.get("SLIM_OUTPUT") == "1" and have_sol:
    import pandas as pd
    _SLIM_VARS = ["vEleTotalCharge", "vEleTotalOutput", "vHydTotalOutput", "vHydInventory",
                  "vEleFreqContReserveDisUpwardBid", "vEleFreqContReserveDisDownwardBid",
                  "vEleFreqContReserveNorBid", "vEleBuy", "vEleSell", "vHydDemand", "vHydBuy"]
    _recs = []
    for _vn in _SLIM_VARS:
        comp = getattr(m, _vn, None)
        if comp is None:
            continue
        for idx in comp:
            try:
                v = val(comp[idx])
            except Exception:
                continue
            _recs.append((idx[0], idx[1], idx[2], _vn, idx[-1] if len(idx) > 3 else "", v / f1))
    sdf = pd.DataFrame(_recs, columns=["period", "scenario", "loadlevel", "variable", "unit", "value"])
    spq = work / f"slim_dispatch_{CASE}.parquet"
    try:
        import duckdb
        con = duckdb.connect()
        con.register("slim", sdf)
        con.execute(f"COPY slim TO '{spq}' (FORMAT PARQUET)")
        con.close()
    except Exception:
        sdf.to_parquet(spq, index=False)   # fallback if a parquet engine is present
    print(f"slim output -> {spq} ({len(sdf)} rows, {sdf['variable'].nunique()} series)", flush=True)
