from .el1xr_opt import main
from .Modules.oM_SolverSetup import ensure_ampl_solvers

if __name__ == "__main__":
    # Making sure that the solvers are correctly set up
    ensure_ampl_solvers()
    raise SystemExit(main())
