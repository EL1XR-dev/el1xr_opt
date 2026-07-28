"""H2VPP FCR sweep runner -- the case ADAPTER for el1xr_opt.sweep.

The three sweep modes (A cold registry / B overlay-parallel / C warm hot-swap) now live in the
reusable el1xr_opt.sweep package; this file is the H2VPP-specific part: how a cell becomes a
solved summary via build_case.py + run_year.py. The spec JSON format and CLI are unchanged:

    python experiments/h2vpp_fcr/run_sweep.py <spec.json> [--force]        # Mode A
    python experiments/h2vpp_fcr/run_sweep.py <spec.json> --parallel <N>   # Mode B
    python experiments/h2vpp_fcr/run_sweep.py <spec.json> --warm           # Mode C
    python experiments/h2vpp_fcr/run_sweep.py <spec.json> --validate <tag> [--parallel N]

Case specifics kept here:
  * _cell_env / _work_name -- the env-knob + work-dir convention run_year.py uses.
  * Mode A / B -- run_year.py subprocesses; Mode B builds the case once and reproduces each
    cell by scaling a fixed input-column set (_OVERLAY_MAP, proven an exact uniform scaling),
    solving cells in parallel via run_year's SWEEP_PREBUILT_WORK build-skip.
  * Mode C -- gurobi_persistent build-once + chgCoeff on the FCR revenue coefficient family
    (_FCR_REV_CONS); _apply_run_year_post_build_edits replays ELE_RAMP_CAP so the warm model
    equals the cold one; validation_base_override forces Crossover=1 so the degenerate LP's
    capacity check is a vertex-vs-vertex comparison.
"""
import os
import sys
import json
import shutil
import datetime
import subprocess
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# el1xr_opt sits at model/src in the paper's companion repo and at src/ in el1xr_opt
# itself, so this file is the same in both; an installed package wins over both.
for _cand in (REPO / "model" / "src", REPO / "src"):
    if (_cand / "el1xr_opt").is_dir():
        sys.path.insert(0, str(_cand))
        break
from el1xr_opt.sweep import SweepAdapter, Summary, WarmSession, main as sweep_main

RESULTS = REPO / "results" / "h2vpp_fcr"
RUN_YEAR = HERE / "run_year.py"
CASE = "H2VPPFCR"
# Interpreter for the run_year subprocesses; default the one running this script (invoke with
# the el1xr_opt venv python so children get pyomo/solvers).
PYTHON = os.environ.get("SWEEP_PYTHON", sys.executable)

# Option flags patched into the work-dir Option CSV (same mapping as run_year.py).
_OPT_ENV = {"PEAK_THRESHOLD_LP": "IndPeakThresholdLP", "STOR_FCR_LEG": "IndStorFCRLegExclusive",
            "ELE_3STATE_TIGHT": "IndElectrolyser3StateTight",
            "ELE_OPER_SYMBREAK": "IndElectrolyserOperSymBreak",
            "ELE_PWL_RELAX": "IndElectrolyserPWLRelax",
            "RESERVE_DELIVERY": "IndReserveDeliverySettlement"}

# Mode C coefficient family: the three FCR revenue-defining constraints + the revenue variable
# each defines. Every other variable in those rows is a bid with an FCR price coefficient.
_FCR_REV_CONS = (("eEleMarketFCRDUpRevenue", "vTotalEleFCRDUpRev"),
                 ("eEleMarketFCRDDwRevenue", "vTotalEleFCRDDwRev"),
                 ("eEleMarketFCRNRevenue", "vTotalEleFCRNRev"))

# Mode B overlay map: each sweep knob is an EXACT uniform scaling of a fixed set of
# (built-input file, columns), verified by diffing build_case outputs. Files carry {CASE}.
_OVERLAY_MAP = {
    "DEG_SCALE": [("oM_Data_HydrogenGeneration_{CASE}.csv",
                   ["DegradationCost", "DegradationCost2ndBlock", "RampDegradationCost"])],
    "H2_PRICE_SCALE": [("oM_Data_HydrogenDemand_{CASE}.csv", ["Price"])],
    "FCR_PRICE_SCALE": [("oM_Data_OperatingReservePrice_{CASE}.csv",
                         ["FCRD_Up", "FCRD_Down", "FCRN_Up", "FCRN_Down"])],
}


# --------------------------------------------------------------------------
# env-knob + work-dir convention (matches run_year.py)
# --------------------------------------------------------------------------

def _cell_env(spec, cell):
    """Merged env for one cell: base + cell params + variant/horizon/RUN_TAG."""
    env = dict(spec.base)
    env.update(cell.params)
    if spec.case.get("variant"):
        env["VARIANT"] = spec.case["variant"]
    if spec.case.get("horizon"):
        env["H2VPP_HORIZON"] = spec.case["horizon"]
    env["RUN_TAG"] = cell.tag
    return {k: str(v) for k, v in env.items()}


def _work_name(env):
    """run_year.py's work-dir naming rule, so the adapter finds each cell's summary."""
    hz = env.get("H2VPP_HORIZON", "year")
    variant = env.get("VARIANT", "").upper()
    if variant:
        base = f"work_{hz}_{variant}"
    else:
        mode = (env.get("H2VPP_DEMAND_MODE")
                or ("firm" if env.get("FIRM") == "1" else "elastic")).lower()
        base = f"work_{hz}" + {"elastic": "", "firm": "_firm", "shift": "_shift"}.get(mode, f"_{mode}")
    return f"{base}_{env['RUN_TAG']}"


def _envn(env, name, default, cast=float):
    v = env.get(name)
    return cast(v) if v not in (None, "") else default


def _run_year(env, log_path):
    """Run run_year.py as a subprocess with this cell's env; return its returncode."""
    with open(log_path, "w") as lf:
        p = subprocess.run([PYTHON, str(RUN_YEAR)], env={**os.environ, **env},
                           cwd=str(REPO), stdout=lf, stderr=subprocess.STDOUT)
    return p.returncode


def _summary_to_normalised(d):
    """Map a run_year summary dict into the sweep package's Summary."""
    caps = {**(d.get("ele_build") or {}), **(d.get("hyd_build") or {}), **(d.get("comp_build") or {})}
    if d.get("ele_conn_cap_MW") is not None:
        caps["ele_conn_cap_MW"] = d["ele_conn_cap_MW"]
    return Summary(objective=d.get("eTotalSCost_SEK"), capacities=caps,
                   termination=d.get("termination"), raw=d)


# --------------------------------------------------------------------------
# Mode B: build once + overlay
# --------------------------------------------------------------------------

def _materialize_base(spec):
    """Build the case ONCE with every overlay knob forced to 1.0, patch the Option CSV, and
    return the base input dir. Cells reproduce their cold build by scaling overlay columns."""
    import pandas as pd
    env = dict(spec.base)
    for knob in _OVERLAY_MAP:
        env[knob] = "1.0"
    if spec.case.get("variant"):
        env["VARIANT"] = spec.case["variant"]
    if spec.case.get("horizon"):
        env["H2VPP_HORIZON"] = spec.case["horizon"]
    env.pop("RUN_TAG", None)
    env = {k: str(v) for k, v in env.items()}
    os.environ.update(env)
    mspec = importlib.util.spec_from_file_location("bc_modeb", HERE / "build_case.py")
    bc = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(bc)
    bc.OUT_DIR = HERE / "inputs" / f"{CASE}__build_modeb_base_{spec.name}"
    print(f"Mode B: building {CASE} {bc.HORIZON} base once (overlay knobs = 1.0) "
          f"-> {bc.OUT_DIR.name} ...", flush=True)
    bc.build()
    opt_set = {col: int(os.environ[ev]) for ev, col in _OPT_ENV.items()
               if os.environ.get(ev) is not None}
    if opt_set:
        optf = bc.OUT_DIR / f"oM_Data_Option_{CASE}.csv"
        od = pd.read_csv(optf)
        for col, v in opt_set.items():
            od[col] = v
        od.to_csv(optf, index=False)
        print(f"Mode B: option overrides {opt_set} -> {optf.name}", flush=True)
    return bc.OUT_DIR


def _apply_overlays(case_dir, env):
    """Scale the overlay columns in case_dir by this cell's knob values (base is at knob=1.0)."""
    import pandas as pd
    for knob, targets in _OVERLAY_MAP.items():
        factor = float(env.get(knob, "1.0") or "1.0")
        if factor == 1.0:
            continue
        for fname, cols in targets:
            fp = case_dir / fname.format(CASE=CASE)
            if not fp.exists():
                continue
            df = pd.read_csv(fp)
            for c in cols:
                if c in df.columns:
                    df[c] = df[c] * factor
            df.to_csv(fp, index=False)


# --------------------------------------------------------------------------
# Mode C: gurobi_persistent warm session
# --------------------------------------------------------------------------

def _gurobi_ok():
    try:
        import gurobipy
        genv = gurobipy.Env(params={"OutputFlag": 0})
        gurobipy.Model(env=genv).dispose()
        genv.dispose()
        return True
    except Exception as exc:
        print(f"gurobi not usable here: {exc}", flush=True)
        return False


def _apply_run_year_post_build_edits(m):
    """Replay run_year.py's env-gated model edits that come AFTER build_model. ELE_RAMP_CAP is
    the one that matters for the price sweep (MIN_BID_FLOOR/FIX_INVEST are refused in
    warm_eligible). Keep in lockstep with run_year.py."""
    import pyomo.environ as pyo
    if os.environ.get("ELE_RAMP_CAP") == "1":
        rho = {"AEL": float(os.environ.get("AEL_RAMP_PCTS", "2.0")) / 100.0,
               "PEM": float(os.environ.get("PEM_RAMP_PCTS", "10.0")) / 100.0}
        fac = 7.5 / 0.86
        m.elerampcap = pyo.Block()

        def _ramp(b, p, sc, n, u):
            tech = "AEL" if "AEL" in u else ("PEM" if "PEM" in u else None)
            if tech is None:
                return pyo.Constraint.Skip
            return m.vEleFreqContReserveDisUpwardBid[p, sc, n, u] \
                <= rho[tech] * fac * m.Par["pHydMaxCharge"][u][p, sc, n] * m.vHydGenInvest[u]
        m.elerampcap.cap = pyo.Constraint(m.psne2h, rule=_ramp)
        print(f"warm: ELE_RAMP_CAP FCR-D-up ramp cap (AEL {rho['AEL']*100:.1f}%/s, "
              f"PEM {rho['PEM']*100:.1f}%/s)", flush=True)


def _build_warm_model(spec, anchor_env):
    """Build the case + Pyomo model once, the way run_year.py does, at FCR_PRICE_SCALE=1.0."""
    env = dict(anchor_env)
    env.pop("RUN_TAG", None)
    env["FCR_PRICE_SCALE"] = "1.0"
    os.environ.update(env)
    mspec = importlib.util.spec_from_file_location("bc_sweep", HERE / "build_case.py")
    bc = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(bc)
    bc.OUT_DIR = HERE / "inputs" / f"{CASE}__build_warm_{spec.name}"
    print(f"warm: building {CASE} {bc.HORIZON} case once (FCR_PRICE_SCALE=1.0) "
          f"-> {bc.OUT_DIR.name} ...", flush=True)
    bc.build()

    warm_work = RESULTS / f"sweep_{spec.name}" / "warm_model"
    wc = warm_work / CASE
    if wc.exists():
        shutil.rmtree(wc)
    wc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bc.OUT_DIR, wc)
    opt_set = {col: int(os.environ[ev]) for ev, col in _OPT_ENV.items()
               if os.environ.get(ev) is not None}
    if opt_set:
        import pandas as pd
        optf = wc / f"oM_Data_Option_{CASE}.csv"
        od = pd.read_csv(optf)
        for col, v in opt_set.items():
            od[col] = v
        od.to_csv(optf, index=False)
        print(f"warm: option overrides {opt_set} -> {optf.name}", flush=True)

    import pyomo.environ as pyo
    from el1xr_opt.Modules.oM_Sequence import build_model
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(str(warm_work), CASE, now, "False")
    pyo.TransformationFactory("core.relax_integer_vars").apply_to(m)
    print("warm: LP=1, relaxed integer/binary vars to continuous", flush=True)
    _apply_run_year_post_build_edits(m)
    return bc, m, warm_work


def _fcr_price_rows(m, opt):
    """Base (scale-1.0) FCR price coefficients as (gurobi_con, gurobi_var, coeff) triples: every
    variable in the FCR revenue rows except the revenue variable each row defines."""
    grb = opt._solver_model
    grb.update()
    con_map = opt._pyomo_con_to_solver_con_map
    var_map = opt._pyomo_var_to_solver_var_map
    rows = []
    for cname, vname in _FCR_REV_CONS:
        con = getattr(m, cname, None)
        rev = getattr(m, vname, None)
        if con is None or rev is None:
            continue
        for idx in con:
            gcon = con_map[con[idx]]
            gskip = var_map[rev[idx]]
            row = grb.getRow(gcon)
            for j in range(row.size()):
                gv = row.getVar(j)
                if gv.sameAs(gskip):
                    continue
                rows.append((gcon, gv, row.getCoeff(j)))
    return rows


def _warm_summary(m, bc, tc, env):
    """The summary fields run_year.py writes, extracted from the in-process model."""
    import pyomo.environ as pyo
    f1 = float(m.factor1)
    mb = float(env.get("MONEY_BASE", "1.0"))
    val = lambda v: float(pyo.value(v))
    phys = lambda x: x / f1
    summary = {"case": CASE, "variant": bc.VARIANT or "A3", "mode": bc.DEMAND_MODE,
               "firm": bc.DEMAND_MODE == "firm", "horizon": bc.HORIZON, "factor1": f1,
               "money_base": mb, "hnscost": bc.HNSCOST, "termination": tc,
               "method": "warm_gurobi_persistent",
               "eTotalSCost_SEK": val(m.eTotalSCost) * mb}
    try:
        summary["peak_cost_SEK"] = sum(val(m.vTotalElePeakCost[i]) for i in m.vTotalElePeakCost) * mb
    except Exception:
        summary["peak_cost_SEK"] = None
    summary["HNS_total_kgH2"] = phys(sum(val(m.vHNS[i]) for i in m.vHNS))
    summary["H2_demand_served_kgH2"] = phys(sum(val(m.vHydDemand[i]) for i in m.vHydDemand))
    summary["H2_import_buy_kgH2"] = phys(sum(val(m.vHydBuy[i]) for i in m.vHydBuy))
    summary["ele_build"] = {u: val(m.vEleGenInvest[u]) for u in m.egc}
    summary["hyd_build"] = {u: val(m.vHydGenInvest[u]) for u in m.hgc}
    summary["comp_build"] = {u: val(m.vHydCompInvest[u]) for u in m.hgcompc}
    try:
        summary["ele_conn_cap_MW"] = phys(val(m.vEleConnCap)) / 1000.0 if hasattr(m, "vEleConnCap") else None
    except Exception:
        summary["ele_conn_cap_MW"] = None
    fcr_vars = {"vEleFreqContReserveDisUpwardBid": "FCR-D up",
                "vEleFreqContReserveDisDownwardBid": "FCR-D down",
                "vEleFreqContReserveNorBid": "FCR-N"}
    fcr = {}
    for vn, label in fcr_vars.items():
        comp = getattr(m, vn, None)
        if comp is None:
            continue
        by_asset = {}
        for idx in comp:
            by_asset[idx[-1]] = by_asset.get(idx[-1], 0.0) + val(comp[idx])
        fcr[label] = by_asset
    summary["fcr_sum_by_asset"] = fcr
    return summary


class _FCRWarmSession(WarmSession):
    """Build the FCR model once on gurobi_persistent; each cell re-scales the FCR price
    coefficient family in place and re-solves (barrier+crossover on the first cell for a basis,
    dual simplex from that basis after)."""

    def __init__(self, spec):
        from pyomo.opt import SolverFactory
        self.spec = spec
        anchor_env = _cell_env(spec, spec.cells[0])
        self.bc, self.m, self.warm_work = _build_warm_model(spec, anchor_env)
        self.opt = SolverFactory("gurobi_persistent")
        self.opt.set_instance(self.m)
        self.rows = _fcr_price_rows(self.m, self.opt)
        self.grb = self.opt._solver_model
        print(f"warm: captured {len(self.rows)} FCR price coefficients across the "
              f"{len(_FCR_REV_CONS)} revenue constraint families", flush=True)
        e0 = anchor_env
        self.base_opts = dict(Presolve=_envn(e0, "PRESOLVE", 2, int),
                              NumericFocus=_envn(e0, "NUMERICFOCUS", 2, int),
                              FeasibilityTol=_envn(e0, "FEASTOL", 1e-6),
                              TimeLimit=_envn(e0, "TIMELIMIT", 21600, int))
        if e0.get("THREADS"):
            self.base_opts["Threads"] = int(e0["THREADS"])
        if e0.get("SCALEFLAG") not in (None, ""):
            self.base_opts["ScaleFlag"] = int(e0["SCALEFLAG"])
        if e0.get("BARHOMOGENEOUS") not in (None, ""):
            self.base_opts["BarHomogeneous"] = int(e0["BARHOMOGENEOUS"])
        self.have_basis = False

    def solve_cell(self, cell, first):
        env = _cell_env(self.spec, cell)
        s = float(env.get("FCR_PRICE_SCALE", "1.0"))
        for gcon, gvar, c0 in self.rows:
            self.grb.chgCoeff(gcon, gvar, c0 * s)
        self.opt.options.update(self.base_opts)
        if self.have_basis:
            self.opt.options["Method"] = 1              # dual simplex from the previous basis
        else:
            self.opt.options["Method"] = _envn(env, "METHOD", 2, int)
            self.opt.options["Crossover"] = 1           # anchor: leave a basis to warm-start from
        self.opt.options["LogFile"] = str(self.warm_work / f"gurobi_{CASE}_{cell.tag}.log")
        try:
            res = self.opt.solve(save_results=False, tee=False)
            tc = str(res.solver.termination_condition)
        except Exception as exc:
            tc = f"error: {type(exc).__name__}: {exc}"
        if tc == "optimal":
            raw = _warm_summary(self.m, self.bc, tc, env)
            raw["fcr_price_scale"] = s
            self.have_basis = True
            return _summary_to_normalised(raw)
        return Summary(objective=None, capacities={}, termination=tc, raw={})


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

class H2VPPAdapter(SweepAdapter):
    """Binds el1xr_opt.sweep to this experiment's build_case.py + run_year.py."""

    def summary_path(self, spec, cell):
        return RESULTS / _work_name(_cell_env(spec, cell)) / f"summary_{CASE}.json"

    def read_summary(self, path):
        return _summary_to_normalised(json.loads(Path(path).read_text()))

    def workname(self, spec, cell):
        return _work_name(_cell_env(spec, cell))

    def validation_base_override(self):
        # degenerate LP: force a vertex on both sides so the capacity check is meaningful;
        # fall back to HiGHS when no Gurobi licence is present (local dev).
        return {"CROSSOVER": "1", "SOLVER": "gurobi" if _gurobi_ok() else "highs"}

    def validation_case_override(self):
        return {"horizon": "week"}   # validate on the cheap horizon

    # Mode A
    def solve_cold(self, spec, cell, log_path, threads=None):
        env = _cell_env(spec, cell)
        if threads:
            env["THREADS"] = str(threads)
        return _run_year(env, log_path)

    # Mode B
    def overlay_eligible(self, spec):
        unmapped = spec.varying_params() - set(_OVERLAY_MAP)
        if unmapped:
            return False, (f"cells vary in {sorted(unmapped)}, not overlay-mappable "
                           f"(only {sorted(_OVERLAY_MAP)} scale a fixed input-column set)")
        return True, ""

    def materialize_base(self, spec):
        return _materialize_base(spec)

    def prepare_overlay_cell(self, spec, base, cell):
        env = _cell_env(spec, cell)
        work = self.summary_path(spec, cell).parent
        wc = work / CASE
        if wc.exists():
            shutil.rmtree(wc)
        wc.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(base, wc)
        _apply_overlays(wc, env)
        return work

    def solve_prebuilt(self, spec, cell, workdir, log_path, threads=None):
        env = _cell_env(spec, cell)
        env["SWEEP_PREBUILT_WORK"] = str(workdir)
        if threads:
            env["THREADS"] = str(threads)
        return _run_year(env, log_path)

    # Mode C
    def warm_eligible(self, spec):
        bad = spec.varying_params() - {"FCR_PRICE_SCALE"}
        if bad:
            return False, (f"cells vary in {sorted(bad)} (only FCR_PRICE_SCALE maps to a single "
                           f"objective-coefficient family; other knobs run cold)")
        env = _cell_env(spec, spec.cells[0])
        if env.get("LP") != "1":
            return False, "warm start needs the LP relaxation (set LP=1 in base_env)"
        if float(env.get("MIN_BID_FLOOR", "0") or "0") > 0:
            return False, "MIN_BID_FLOOR adds binaries (a MIP); the warm path is LP-only"
        if env.get("FIX_INVEST"):
            return False, "FIX_INVEST fixes the sizing (anchor run), not a price sweep"
        if not _gurobi_ok():
            return False, "no usable Gurobi licence (gurobi_persistent)"
        return True, ""

    def open_warm(self, spec):
        return _FCRWarmSession(spec)


if __name__ == "__main__":
    sys.exit(sweep_main(H2VPPAdapter(), RESULTS))
