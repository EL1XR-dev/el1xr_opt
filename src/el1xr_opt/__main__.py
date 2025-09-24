from .oM_Main import main
from .solver_setup import ensure_ampl_solvers

if __name__ == "__main__":
    ensure_ampl_solvers()
    main()
