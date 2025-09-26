# oM_SolverSetup.py
from __future__ import annotations
import logging, sys, subprocess
from typing import Iterable, Dict, Optional

log = logging.getLogger(__name__)

# ---------- AMPL module helpers ----------
def _ampl_module_available(name: str) -> bool:
    try:
        from ampltools.modules import modules
        modules.find(name)  # raises if missing
        return True
    except Exception:
        return False

def _install_ampl_module(name: str) -> bool:
    # 1) Try the Python API if present
    try:
        from ampltools.modules import modules
        try:
            # Some versions expose modules.install(...)
            if hasattr(modules, "install"):
                modules.install(name)  # type: ignore[attr-defined]
                modules.find(name)
                return True
        except Exception:
            pass
    except Exception:
        pass

    # 2) Fallback to CLI: python -m amplpy.modules install <name>
    try:
        subprocess.run(
            [sys.executable, "-m", "amplpy.modules", "install", name],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return _ampl_module_available(name)
    except Exception as e:
        log.warning("Failed to install AMPL module '%s': %s", name, e)
        return False

def ensure_ampl_solvers(targets: Iterable[str] = ("highs",), quiet: bool = False) -> Dict[str, bool]:
    """
    Ensure the requested AMPL solver modules are present.
    Returns a dict {solver_name: installed_or_present}.
    """
    results: Dict[str, bool] = {}
    for s in targets:
        if _ampl_module_available(s):
            results[s] = True
            if not quiet:
                log.info("AMPL module '%s' already present.", s)
            continue

        ok = _install_ampl_module(s)
        results[s] = ok
        if not ok and not quiet:
            log.warning(
                "AMPL module '%s' is not available and could not be installed.\n"
                "You can install manually with:\n  %s -m amplpy.modules install %s",
                s, sys.executable, s
            )
    return results

# ---------- Unified solver selection ----------
def pick_solver(preferred: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Return a config dict for creating a Pyomo SolverFactory:
      - If AMPL module 'preferred' exists -> use '<preferred>nl' + solve_io='nl' + executable=<found path>
      - Else try Appsi HiGHS (pure Python)
      - Else try CBC/GLPK on PATH
    Result keys: 'factory', 'solve_io', 'executable', 'resolved'
    """
    name = (preferred or "highs").lower()

    # 1) AMPL module path (preferred)
    if _ampl_module_available(name):
        from ampltools.modules import modules
        exe = modules.find(name)
        return {"factory": name + "nl", "solve_io": "nl", "executable": exe, "resolved": name + " (AMPL module)"}

    # 2) Pyomo Appsi HiGHS
    try:
        from pyomo.opt import SolverFactory
        s = SolverFactory("appsi_highs")
        if s.available():
            return {"factory": "appsi_highs", "solve_io": None, "executable": None, "resolved": "appsi_highs"}
    except Exception:
        pass

    # 3) Other common fallbacks
    for cand in (name, "cbc", "glpk"):
        try:
            from pyomo.opt import SolverFactory
            s = SolverFactory(cand)
            if s.available():
                return {"factory": cand, "solve_io": None, "executable": None, "resolved": cand}
        except Exception:
            continue

    raise RuntimeError(
        "No available solver. Install an AMPL module (e.g., "
        f"`{sys.executable} -m amplpy.modules install {name}`) or "
        "install Pyomo Appsi HiGHS with:  pip install \"pyomo[appsi]\" highspy"
    )
