# oM_SolverSetup.py
from __future__ import annotations
import logging, sys, subprocess
from typing import Iterable, Dict, Optional

log = logging.getLogger(__name__)

# Supported solvers (extend carefully)
_SUPPORTED_SOLVERS = {"highs", "cbc"}

# Pre-built, static commands per solver
_CMD = {
    "highs":  [sys.executable, "-m", "amplpy.modules", "install", "highs"],
    "cbc":    [sys.executable, "-m", "amplpy.modules", "install", "cbc"],
}

# ---------- AMPL module helpers ----------
def _ampl_module_available(name: str) -> bool:
    try:
        from amplpy import modules
        modules.find(name)  # raises if missing
        return True
    except Exception:
        return False

def _install_ampl_module(name: str) -> bool:
    solver = name.lower()
    if solver not in _SUPPORTED_SOLVERS:
        raise ValueError(
            f"Unsupported solver '{solver}'. Allowed: {sorted(_SUPPORTED_SOLVERS)}"
        )
    # Try Python API first (safer than subprocess)
    try:
        from amplpy import modules
        if hasattr(modules, "install"):
            modules.install(name)  # may raise
            modules.find(name)
            return True
    except Exception:
        pass

    # Fallback: subprocess with static command
    try:
        # installing ampl module via subprocess and consider --upgrade
        subprocess.run(_CMD[solver],
                       check=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
        # subprocess.run([sys.executable, "-m", "amplpy.modules", "install", name],
        #                check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return _ampl_module_available(name)
    except Exception:
        return False

def ensure_ampl_solvers(targets: Iterable[str] = ("highs",), quiet: bool = False) -> Dict[str, bool]:
    print(f'- Ensuring AMPL solver modules {", ".join(targets)} are installed...\n')
    out: Dict[str, bool] = {}
    for s in targets:
        s = s.lower()
        try:
            out[s] = _ampl_module_available(s) or _install_ampl_module(s)
        except ValueError as e:
            out[s] = False
            if not quiet:
                log.warning(str(e))
            continue

        if not quiet and not out[s]:
            log.warning("AMPL module '%s' not available. Try: %s -m amplpy.modules install %s",
                        s, sys.executable, s)
    return out

# ---------- Unified solver selection ----------
def pick_solver(preferred: Optional[str], *, allow_fallback: bool = False):
    """
    Strict by default:
      - Use AMPL '<solver>nl' if available.
      - If not available and allow_fallback=False -> raise.
      - If allow_fallback=True, you *may* add other strategies here.
    """
    name = (preferred or "highs").lower()

    if name not in _SUPPORTED_SOLVERS:
        raise ValueError(
            f"Unsupported solver '{name}'. Allowed: {sorted(_SUPPORTED_SOLVERS)}"
        )

    # AMPL module
    if _ampl_module_available(name):
        from amplpy import modules
        exe = modules.find(name)
        return {"factory": name + "nl", "solve_io": "nl", "executable": exe, "resolved": name + " (AMPL module)"}

    if not allow_fallback:
        raise RuntimeError(
            f"AMPL solver module '{name}' not found. "
            f"Install it with: {sys.executable} -m amplpy.modules install {name}"
        )
