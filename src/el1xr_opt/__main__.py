from .el1xr_Main import main
from .Modules.oM_SolverSetup import ensure_ampl_solvers

if __name__ == "__main__":
    # Making sure that the solvers are correctly set up
    ensure_ampl_solvers()
    raise SystemExit(main())


# __main__.py
from .el1xr_opt import main
from .Modules.oM_SolverSetup import ensure_ampl_solvers

if __name__ == "__main__":
    # Try to ensure HiGHS AMPL module is installed; do nothing if it already is.
    try:
        ensure_ampl_solvers(["highs"], quiet=True)
    except Exception:
        # Don’t crash here; pick_solver() will still fall back gracefully.
        pass
    raise SystemExit(main())
