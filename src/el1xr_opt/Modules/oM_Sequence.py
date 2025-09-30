# Developed by: Erik F. Alvarez

# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import os
import time                                         # count clock time
from   pyomo.environ     import ConcreteModel
from   collections       import defaultdict

from .oM_InputData        import data_processing, create_variables
from .oM_ModelFormulation import create_objective_function, create_objective_function_components, create_constraints
from .oM_ProblemSolving   import solving_model
from .oM_OutputData       import saving_results
from .oM_SolverSetup      import ensure_ampl_solvers

def routine(dir, case, solver, date, rawresults, plots):
    initial_time = time.time()

    # %% Model declaration
    oModel = ConcreteModel('el1xr_opt  - Optimisation Model')

    # Try to ensure HiGHS AMPL module is installed; do nothing if it already is.
    ensure_ampl_solvers(["highs"], quiet=True)
    print(f'- Using solver: {solver}\n')

    # reading and processing the data
    #
    print('- Initializing the model\n')
    model = data_processing(dir, case, date, oModel)
    print('- Total time for reading and processing the data:                      {} seconds\n'.format(round(time.time() - initial_time)))
    start_time = time.time()
    # defining the variables
    model = create_variables(model, model)
    print('- Total time for defining the variables:                               {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # defining the objective function
    model = create_objective_function(model, model)
    print('- Total time for defining the objective function:                      {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # defining components of the day-ahead objective function
    model = create_objective_function_components(model, model)
    print('- Total time for defining the objective function:                      {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # defining the constraints
    model = create_constraints(model, model)
    print('- Total time for defining the constraints:                             {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # solving the model
    pWrittingLPFile = 0
    model = solving_model(dir, case, solver, model, pWrittingLPFile)
    print('- Total time for solving the model:                                    {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # outputting the results
    # model = saving_rawdata(dir, case, solver, model, model)
    # print('- Total time for outputting the raw data:                              {} seconds\n'.format(round(time.time() - start_time  )))
    # start_time = time.time()
    # outputting the results
    model = saving_results(dir, case, date, model, model)
    print('- Total time for outputting the results:                               {} seconds\n'.format(round(time.time() - start_time  )))
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
