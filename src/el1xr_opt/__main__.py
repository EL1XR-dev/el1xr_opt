# el1xr_opt/__main__.py
from .oM_Main import main, ensure_ampl_solvers

if __name__ == "__main__":
    ensure_ampl_solvers()
    main()
