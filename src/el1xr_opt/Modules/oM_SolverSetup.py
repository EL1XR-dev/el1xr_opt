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
    try:
        from ampltools.modules import modules
        if hasattr(modules, "install"):
            modules.install(name)  # may raise
            modules.find(name)
            return True
    except Exception:
        pass
    try:
        # installing ampl module via subprocess and consider --upgrade
        subprocess.run([sys.executable, "-m", "pip", "install", "amplpy", "--upgrade", ],)
        subprocess.run([sys.executable, "-m", "amplpy.modules", "install", name],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return _ampl_module_available(name)
    except Exception:
        return False

def ensure_ampl_solvers(targets: Iterable[str] = ("highs",), quiet: bool = False) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    for s in targets:
        out[s] = _ampl_module_available(s) or _install_ampl_module(s)
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

    # AMPL module
    if _ampl_module_available(name):
        from ampltools.modules import modules
        exe = modules.find(name)
        return {"factory": name + "nl", "solve_io": "nl", "executable": exe, "resolved": name + " (AMPL module)"}

    if not allow_fallback:
        raise RuntimeError(
            f"AMPL solver module '{name}' not found. "
            f"Install it with: {sys.executable} -m amplpy.modules install {name}"
        )
