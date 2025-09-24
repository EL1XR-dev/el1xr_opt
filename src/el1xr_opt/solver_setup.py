# src/el1xr_opt/solver_setup.py
import os
import warnings

def ensure_ampl_solvers(required=("highs", "cbc"), quiet=True):
    """
    Ensure AMPL open-source solvers are present. Installs missing ones if needed.
    Call this early in your main program, not at import time.
    """
    try:
        from amplpy import modules
    except Exception as e:
        raise RuntimeError(
            "amplpy is required. Please install it with `pip install amplpy`."
        ) from e

    missing = []
    for name in required:
        try:
            if hasattr(modules, "is_installed") and modules.is_installed(name):
                continue
            avail = getattr(modules, "available", lambda: [])()
            if name in avail:
                continue
            missing.append(name)
        except Exception:
            missing.append(name)

    if not missing:
        return

    if os.environ.get("EL1XR_SKIP_SOLVER_AUTO_INSTALL", "").lower() in ("1","true","yes"):
        warnings.warn(
            f"Skipping solver auto-install. Run manually:\n"
            f"python -m amplpy.modules install {' '.join(required)}"
        )
        return

    try:
        modules.install(*missing, verbose=not quiet)
    except Exception as e:
        warnings.warn(
            f"Couldn’t auto-install solvers {missing}. "
            f"Run manually:\npython -m amplpy.modules install {' '.join(required)}\n"
            f"Reason: {e}"
        )
