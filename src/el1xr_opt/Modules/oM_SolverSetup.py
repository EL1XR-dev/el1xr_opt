# oM_SolverSetup.py
from __future__ import annotations
import logging
import sys
import subprocess
from typing import Iterable, Dict, Optional

log = logging.getLogger(__name__)

# Supported solvers (extend carefully)
_SUPPORTED_SOLVERS = {"highs", "cbc"}

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
            modules.install(solver)  # may raise
            modules.find(solver)
            return True
    except Exception:
        pass

    # Fallback: subprocess with STATIC commands (no variables in the argv list)
    try:
        if solver == "highs":
            argv = [sys.executable, "-m", "amplpy.modules", "install", "highs"]
        elif solver == "cbc":
            argv = [sys.executable, "-m", "amplpy.modules", "install", "cbc"]
        else:
            # Defensive—should never reach here due to whitelist check above
            raise ValueError(
                f"Unsupported solver '{solver}'. Allowed: {sorted(_SUPPORTED_SOLVERS)}"
            )

        subprocess.run(
            argv,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,        # be explicit for linters
        )
        return _ampl_module_available(solver)
    except Exception:
        return False


def ensure_ampl_solvers(
    targets: Iterable[str] = ("highs",),
    quiet: bool = False
) -> Dict[str, bool]:
    try:
        printable = ", ".join(list(targets))
    except Exception:
        printable = "<targets>"
    print(f'- Ensuring AMPL solver modules {printable} are installed...\n')

    out: Dict[str, bool] = {}
    for s in targets:
        s = str(s).lower()
        try:
            out[s] = _ampl_module_available(s) or _install_ampl_module(s)
        except ValueError as e:
            out[s] = False
            if not quiet:
                log.warning(str(e))
            continue

        if not quiet and not out[s]:
            log.warning(
                "AMPL module '%s' not available. Try: %s -m amplpy.modules install %s",
                s, sys.executable, s
            )
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
        return {
            "factory": name + "nl",
            "solve_io": "nl",
            "executable": exe,
            "resolved": name + " (AMPL module)",
        }

    if not allow_fallback:
        raise RuntimeError(
            f"AMPL solver module '{name}' not found. "
            f"Install it with: {sys.executable} -m amplpy.modules install {name}"
        )
