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
from .oM_ProblemSolving   import solving_model
from .oM_SolverSetup      import ensure_ampl_solvers
from .utils.oM_Utils      import log_time

# The output modules (oM_OutputData, oM_OutputData_duckdb) are imported lazily
# inside routine() rather than here. They pull in heavy plotting libraries
# (matplotlib, plotly, altair) that are not needed to import the package, and
# keeping them out of the import-time chain lets documentation tooling import the
# package without those libraries installed.

def routine(dir, case, solver, date, rawresults, plots, indlog, duckdbresults='True'):
    initial_time = time.time()

    # %% Model declaration
    oModel = ConcreteModel('el1xr_opt  - Optimisation Model')

    # Try to ensure HiGHS AMPL module is installed; do nothing if it already is.
    ensure_ampl_solvers(["highs"], quiet=True)
    print(f'- Using solver: {solver}\n')

    # reading and processing the data
    #
    print('- Initializing the model\n')
    model = data_processing(dir, case, date, oModel, indlog)
    log_time('- Total time for reading and processing the data:', initial_time, ind_log=indlog)
    start_time = time.time()
    # defining the variables
    model = create_variables(model, model, indlog)
    log_time('- Total time for defining the variables:', start_time, ind_log=indlog)
    start_time = time.time()
    # defining the investment (capacity-sizing) layer
    model = create_investment(model, model, indlog)
    log_time('- Total time for defining the investment layer:', start_time, ind_log=indlog)
    start_time = time.time()
    # defining the objective function
    model = create_objective_function(model, model, indlog)
    log_time('- Total time for defining the objective function:', start_time, ind_log=indlog)
    start_time = time.time()
    # defining components of the day-ahead objective function
    model = create_objective_function_components(model, model, indlog)
    log_time('- Total time for defining the ObjFunc components:', start_time, ind_log=indlog)
    start_time = time.time()
    # defining the constraints
    model = create_constraints(model, model, indlog)
    log_time('- Total time for defining the constraints:', start_time, ind_log=indlog)
    start_time = time.time()
    # defining green-hydrogen temporal matching and electricity PPA
    model = create_green_hydrogen(model, model, indlog)
    log_time('- Total time for defining the green-hydrogen layer:', start_time, ind_log=indlog)
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
