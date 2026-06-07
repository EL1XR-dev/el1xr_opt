# Developed by: Erik F. Alvarez

# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import os
import time                                         # count clock time
from   pyomo.environ     import ConcreteModel

from .oM_InputData        import data_processing, create_variables
from .oM_Investment        import create_investment
from .oM_ModelFormulation import create_objective_function, create_objective_function_components, create_constraints
from .oM_GreenHydrogen      import create_green_hydrogen
from .oM_Community         import create_community_variables, create_community_constraints
from .oM_ProblemSolving   import solving_model
from .oM_SolverSetup      import ensure_ampl_solvers
from .utils.oM_Utils      import log_time

# The output modules (oM_OutputData, oM_OutputData_duckdb) are imported lazily
# inside routine() rather than here. They pull in heavy plotting libraries
# (matplotlib, plotly, altair) that are not needed to import the package, and
# keeping them out of the import-time chain lets documentation tooling import the
# package without those libraries installed.

def build_model(dir_name, case, date, indlog='False'):
    """Build the full el1xr model (all layers) without solving and return it.

    This is the build half of ``routine``, factored out so other entry points
    (e.g. the Benders decomposition, which builds an operating subproblem per
    block) can reuse the exact same, validated construction.
    """
    oModel = ConcreteModel('el1xr_opt  - Optimisation Model')
    model = data_processing(dir_name, case, date, oModel, indlog)
    model = create_variables(model, model, indlog)
    model = create_community_variables(model, model, indlog)
    model = create_investment(model, model, indlog)
    model = create_objective_function(model, model, indlog)
    model = create_objective_function_components(model, model, indlog)
    model = create_constraints(model, model, indlog)
    model = create_community_constraints(model, model, indlog)
    model = create_green_hydrogen(model, model, indlog)
    return model


def routine(dir, case, solver, date, rawresults, plots, indlog, duckdbresults='True'):
    initial_time = time.time()

    # Try to ensure HiGHS AMPL module is installed; do nothing if it already is.
    ensure_ampl_solvers(["highs"], quiet=True)
    print(f'- Using solver: {solver}\n')

    # reading, processing the data, and building the full model
    print('- Initializing the model\n')
    model = build_model(dir, case, date, indlog)
    log_time('- Total time for reading, processing and building the model:', initial_time, ind_log=indlog)
    start_time = time.time()
    # solving the model
    pWrittingLPFile = 1
    model = solving_model(dir, case, solver, model, pWrittingLPFile, indlog)
    log_time('- Total time for solving the model:', start_time, ind_log=indlog)
    start_time = time.time()
    # outputting the results
    if rawresults == 'True':
        from .oM_OutputData import saving_rawdata
        model = saving_rawdata(dir, case, solver, model, model, indlog)
        log_time('- Total time for outputting the raw data:', start_time, ind_log=indlog)
        start_time = time.time()
    # outputting the results
    if plots == 'True':
        from .oM_OutputData import saving_results
        model = saving_results(dir, case, date, model, model, indlog)
        log_time('- Total time for outputting the results:', start_time, ind_log=indlog)
        start_time = time.time()
    # outputting the results to duckdb (default output; CSV outputs above are optional)
    if duckdbresults == 'True':
        from .oM_OutputData_duckdb import save_to_duckdb
        save_to_duckdb(dir, case, model, model, date=date, solver=solver)
        log_time('- Total time for outputting the results to duckdb:', start_time, ind_log=indlog)
        start_time = time.time()
    for i in range(0, 117):
        print('-', end="")
    print('\n')
    elapsed_time = round(time.time() - initial_time)
    print('Elapsed time: {} seconds'.format(elapsed_time))
    path_to_write_time = os.path.join(dir, case, f'oM_Result_rExecutionTime_{case}.txt')
    with open(path_to_write_time, 'w') as f:
         f.write(str(elapsed_time))
    for i in range(0, 117):
        print('-', end="")
    print('\n')

    return model
