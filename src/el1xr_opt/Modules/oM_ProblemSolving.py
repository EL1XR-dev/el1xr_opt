# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import time          # count clock time
import os
import psutil        # access the number of CPUs
from pyomo.environ import Var, Suffix, SolverFactory
from .oM_SolverSetup import pick_solver, ensure_ampl_solvers


def solving_model(DirName, CaseName, SolverName, optmodel, pWriteLP):
    """
    Solve the Pyomo model using a robust solver selection:

      - If AMPL module for the requested solver exists (e.g., 'highs'),
        use the fast *.nl route.
      - Otherwise fall back to Pyomo's Appsi HiGHS (pure Python),
        or CBC/GLPK on PATH.
      - Keep GAMS/CPLEX branch as in the original logic.

    Parameters
    ----------
    DirName : str
        Base directory of the case.
    CaseName : str
        Case folder name.
    SolverName : str
        Requested solver name (e.g., 'highs', 'gurobi', 'cbc', 'gams', 'cplex').
    optmodel : ConcreteModel
        Pyomo model instance.
    pWriteLP : str | bool
        Whether to write LP/MPS (original code uses 'Yes'/'No').
    """
    StartTime = time.time()
    _path = os.path.join(DirName, CaseName)
    os.makedirs(_path, exist_ok=True)

    # ---- Map special cases (keep your original behavior) ----
    SubSolverName = ""
    if SolverName and SolverName.lower() == "cplex":
        # Use GAMS front-end with CPLEX as sub-solver
        SubSolverName = "cplex"
        SolverName = "gams"

    # ---- Create solver instance ----
    if SolverName and SolverName.lower() == "gams":
        # You keep your GAMS flow as before
        Solver = SolverFactory("gams")
        resolved = "gams"
    else:
        if SolverName == "highs":
            # New robust path: AMPL module -> Appsi HiGHS -> CBC/GLPK
            cfg = pick_solver(SolverName, allow_fallback=False)
            if cfg["solve_io"] == "nl":
                Solver = SolverFactory(cfg["factory"], executable=cfg["executable"], solve_io="nl")
            else:
                Solver = SolverFactory(cfg["factory"])
            resolved = str(cfg["resolved"])
        else:
            # Other solvers via Pyomo's SolverFactory (e.g., 'gurobi', 'cbc', 'glpk')
            Solver = SolverFactory(SolverName)
            resolved = SolverName
        print(f"Using solver: {resolved}")

    # ---- Optional: write LP/MPS if requested ----
    want_lp = (str(pWriteLP).strip().lower() in {"yes", "y", "true", "1"})
    if want_lp:
        try:
            lp_name = os.path.join(_path, f"oM_{CaseName}.lp")
            optmodel.write(filename=lp_name, io_options={"symbolic_solver_labels": True})
            print(f"LP written to {lp_name}")
        except Exception as e:
            print(f"Warning: could not write LP file: {e}")

    # ---- Attach suffixes for importing duals/reduced costs ----
    # (remove existing to be safe on re-runs)
    if hasattr(optmodel, "dual"):
        optmodel.del_component(optmodel.dual)
    if hasattr(optmodel, "rc"):
        optmodel.del_component(optmodel.rc)
    optmodel.dual = Suffix(direction=Suffix.IMPORT)
    optmodel.rc = Suffix(direction=Suffix.IMPORT)

    # ---- Configure solver-specific options (preserve your Gurobi tuning) ----
    try:
        solver_name_lower = getattr(Solver, "name", resolved).lower()
    except Exception:
        solver_name_lower = str(resolved).lower()

    if "gurobi" in solver_name_lower:
        # Mirror your original Gurobi parameters
        Solver.options["LogFile"]         = os.path.join(_path, f"oM_{CaseName}.log")
        Solver.options["Method"]          = 2          # barrier
        Solver.options["MIPFocus"]        = 1
        Solver.options["Presolve"]        = 2
        Solver.options["RINS"]            = 100
        Solver.options["Crossover"]       = -1
        Solver.options["FeasibilityTol"]  = 1e-9
        Solver.options["MIPGap"]          = 0.02
        Solver.options["Threads"]         = int((psutil.cpu_count(True) + psutil.cpu_count(False)) / 2)
        Solver.options["TimeLimit"]       = 3600
        Solver.options["IterationLimit"]  = 1800000

    # ---- Solve ----
    if SolverName.lower() == "gams":
        # Build any GAMS add_options you previously used
        solver_options = []
        if SubSolverName:
            solver_options.append(f"--solver={SubSolverName}")
        SolverResults = Solver.solve(
            optmodel,
            tee=True,
            report_timing=True,
            symbolic_solver_labels=False,
            add_options=solver_options,
        )
    else:
        SolverResults = Solver.solve(
            optmodel,
            tee=False,
            report_timing=True,
        )

    SolverResults.write()  # summary of results

    # %% fix values of binary variables to get dual variables and solve it again
    print('# ============================================================================= #')
    print('# ============================================================================= #')
    idx = 0
    for var in optmodel.component_data_objects(Var, active=True, descend_into=True):
        if not var.is_continuous():
            # print("fixing: " + str(var))
            var.fixed = True  # fix the current value
            idx += 1
    print("Number of fixed variables: ", idx)
    print('# ============================================================================= #')
    print('# ============================================================================= #')
    if idx != 0:
        optmodel.del_component(optmodel.dual)
        optmodel.del_component(optmodel.rc)
        optmodel.dual = Suffix(direction=Suffix.IMPORT)
        optmodel.rc = Suffix(direction=Suffix.IMPORT)
        if SolverName == 'gams':
            SolverResults = Solver.solve(optmodel, tee=True, report_timing=True, symbolic_solver_labels=False, add_options=solver_options)
        else:
            SolverResults = Solver.solve(optmodel, tee=False, report_timing=True)
        SolverResults.write()  # summary of the solver results

    SolvingTime = time.time() - StartTime
    print('Solving                               ... ', round(SolvingTime), 's')

    print('Objective function value                  ', round(optmodel.eTotalSCost.expr(), 2), 'M€')

    return optmodel