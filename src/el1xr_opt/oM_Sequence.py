# Developed by: Erik F. Alvarez

# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import csv
import os
import math
import time                                         # count clock time
import psutil                                       # access the number of CPUs
import altair            as alt
import pandas            as pd
import plotly.io         as pio
import plotly.graph_objs as go
from pyomo.core.kernel.parameter import parameter
from   pyomo.environ     import Set, Param, Var, Binary, UnitInterval, NonNegativeIntegers, PositiveIntegers, NonNegativeReals, Reals, Any, Constraint, ConcreteModel, Objective, minimize, Suffix, DataPortal
from   pyomo.opt         import SolverFactory
from   pyomo.dataportal  import DataPortal
from   collections       import defaultdict
from   colour            import Color

from .Modules.oM_InputData        import data_processing, create_variables
from .Modules.oM_ModelFormulation import create_objective_function, create_objective_function_components, create_constraints
from .Modules.oM_ProblemSolving   import solving_model
from .Modules.oM_OutputData       import saving_rawdata, saving_results

def oM_run(dir=None, case=None, solver=None, date=None, rawresults=None, plots=None):
    initial_time = time.time()

    # %% Model declaration
    oModel = ConcreteModel('el1xr_opt  - Version 1.0.4 - Sep 25, 2025')

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
