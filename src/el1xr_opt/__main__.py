# __main__.py
from .el1xr_Main import main
from .Modules.oM_SolverSetup import ensure_ampl_solvers

if __name__ == "__main__":
    # Try to ensure HiGHS AMPL module is installed; do nothing if it already is.
    ensure_ampl_solvers(["highs"], quiet=True)
    raise SystemExit(main())
