# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import time          # count clock time
import os
import psutil        # access the number of CPUs
import logging
from pyomo.opt     import SolverFactory, SolverStatus, TerminationCondition
from pyomo.environ import Var, Suffix
from pyomo.util.infeasible import log_infeasible_constraints
from .oM_SolverSetup import pick_solver
from .utils.oM_Utils import log_time


def solving_model(DirName, CaseName, SolverName, optmodel, pWriteLP, indlog):
    """Solves a Pyomo optimization model with a selected solver and handles post-processing.

    This function orchestrates the model solving process. It first selects a solver
    based on availability, prioritizing high-performance AMPL modules (like HiGHS)
    for speed. If the requested solver is not available as an AMPL module, it may
    fall back to other configurations depending on the setup in ``oM_SolverSetup``.

    The process includes:

    1. **Solver Selection**: Chooses and configures the solver (e.g., HiGHS, GAMS, CPLEX).
    2. **LP File Generation**: Optionally writes the model to an LP file for debugging.
    3. **Initial Solve**: Solves the optimization problem.
    4. **Post-processing for Duals**: If the model contains binary or integer
       variables, it fixes them to their optimal values and re-solves the
       now-continuous problem. This is a common technique to obtain meaningful
       dual values (shadow prices) for all constraints in a mixed-integer problem.
    5. **Results Logging**: Prints the objective function value and total solving time.

    Args:
        DirName (str): The base directory where case-related files are stored.
        CaseName (str): The specific name of the case folder.
        SolverName (str): The name of the desired solver (e.g., 'highs', 'gurobi', 'cbc', 'gams', 'cplex').
        optmodel (pyomo.environ.ConcreteModel): The Pyomo model instance to be solved.
        pWriteLP (str or bool): If 'Yes' or True, writes the model formulation to an
            LP file.

    Returns:
        pyomo.environ.ConcreteModel: The solved Pyomo model instance, with variable
        values, objective function, and duals populated.
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

    # ---- Detect the problem class and check the solver can handle it ----
    # The class (LP/MILP/QP/SOCP/MISOCP/NLP) is detected from the built model and
    # determines which solvers (and, for a future build-library choice, which
    # modelling libraries) can handle it. A mismatch (e.g. a conic case on HiGHS)
    # is warned about rather than silently failing inside the solver.
    try:
        from .oM_Features import check_solver_for_model
        pc, ok, msg = check_solver_for_model(optmodel, resolved)
        print(f"- Problem class: {msg}")
        if not ok:
            print(f"WARNING: solver '{resolved}' may not support a {pc} model; "
                  f"consider one of: see the list above.")
    except Exception as exc:
        print(f"- Problem-class detection skipped ({exc})")

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
        Solver.options["Crossover"]       = -1         # skip crossover: the kW-scale model with
                                                       # tight must-serve equalities makes crossover
                                                       # numerically declare a feasible barrier
                                                       # optimum "infeasibleOrUnbounded"
        Solver.options["BarHomogeneous"]  = 1          # robust infeasible/unbounded detection
        # Solver.options["FeasibilityTol"]  = 1e-9
        Solver.options["FeasibilityTol"]  = 1e-8
        Solver.options["NumericFocus"]    = 3
        Solver.options["MIPGap"]          = 0.02
        Solver.options["Threads"]         = int((psutil.cpu_count(True) + psutil.cpu_count(False)) / 2)
        Solver.options["TimeLimit"]       = 1000
        Solver.options["IterationLimit"]  = 1800000
        print("Gurobi solver options configured.")

    if "asl" in solver_name_lower:
        # Example HiGHS options (customize as needed)
        # Solver.options["log_file"]             = os.path.join(_path, f"oM_{CaseName}.log")
        # Solver.options["log_to_console"]         = True
        Solver.options["presolve"]               = "on"
        # Use simplex (not the interior-point method) as the LP algorithm. On these
        # home/community-scale LPs simplex is fast AND it reports infeasibility quickly
        # and reliably. The interior-point path could not cleanly prove infeasibility on a
        # near-infeasible model: it ran out the whole time limit and returned a
        # tolerance-violating pseudo-solution, which then read as a (wrong) "feasible"
        # answer downstream. Simplex flags the same model infeasible in a fraction of a
        # second.
        Solver.options["solver"]               = "simplex"
        # Scale the constraint matrix before solving. The model spans a wide coefficient
        # range (operating costs ~1, the value-of-lost-load penalty ~1e5, efficiency and
        # reserve-block terms ~1e-3), so explicit equilibration scaling tightens the
        # conditioning and reduces solver tolerance warnings.
        Solver.options["simplex_scale_strategy"] = 2
        Solver.options["parallel"]             = "on"
        Solver.options["run_crossover"]        = "on"  # HiGHS allows on/off only
        Solver.options["mip_rel_gap"]          = 0.02  # equivalent to MIPGap
        Solver.options["mip_abs_gap"]          = 1e-4
        # Solver.options["mip_detect_symmetry"]  = "on"
        # Solver.options["mip_heuristic_effort"] = 0.1  # equivalent to RINS intensity
        Solver.options["mip_max_nodes"]        = 1000000
        Solver.options["mip_max_leaves"]       = 1000000
        Solver.options["threads"]              = int((psutil.cpu_count(True) + psutil.cpu_count(False)) / 2)
        Solver.options["time_limit"]           = 150
        Solver.options["ipm_iteration_limit"]  = 1800000
        print("HiGHS solver options configured.")

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
            tee=True,
            report_timing=True,
        )

    # print('Termination condition: ', SolverResults.solver.termination_condition)
    # if SolverResults.solver.termination_condition == TerminationCondition.infeasible or SolverResults.solver.termination_condition == TerminationCondition.maxTimeLimit or SolverResults.solver.termination_condition == TerminationCondition.infeasible.maxIterations:
    #     log_infeasible_constraints(optmodel, log_expression=True, log_variables=True)
    #     logging.basicConfig(filename=f'{_path}/oM_Infeasibilities_{CaseName}.log', level=logging.INFO)
    #     raise ValueError('Problem infeasible')

    SolverResults.write()  # summary of results
    optmodel.SolverResults1 = SolverResults

    # Surface a non-optimal solve loudly. A solver that stops infeasible, or hits the time
    # or iteration limit, leaves the model holding a meaningless (or only partially solved)
    # point; using those values silently is how an infeasible case looked like a feasible
    # one. Warn clearly so callers and tests see it rather than trusting the variables.
    _tc = SolverResults.solver.termination_condition
    if _tc != TerminationCondition.optimal:
        print(f"WARNING: solver did not reach an optimal solution (termination: {_tc}); "
              f"the model variable values may be meaningless. Check feasibility and limits.")

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
            SolverResults = Solver.solve(optmodel, tee=True, report_timing=True)
        SolverResults.write()  # summary of the solver results

    log_time('-- Total time for solving the model:', StartTime, ind_log=indlog)

    _currency = optmodel.Par.get('pParCurrency', 'SEK') if hasattr(optmodel, 'Par') else 'SEK'
    print('Objective function value                  ', round(optmodel.eTotalSCost.expr(), 2), _currency)

    # Adding SolverResults to optmodel
    optmodel.SolverResults2 = SolverResults

    return optmodel