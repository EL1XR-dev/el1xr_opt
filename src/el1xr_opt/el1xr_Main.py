# Developed by: Erik F. Alvarez

# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import argparse
import csv
import datetime
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

for i in range(0, 117):
    print('-', end="")

print('\nElectricity for Low-carbon Integration and eXchange of Resources (EL1XR) - Version 1.0.1 - Sep 25, 2025')
print('#### Non-commercial use only ####')

parser = argparse.ArgumentParser(description='Introducing main arguments...')
parser.add_argument('--dir',    type=str, default=None)
parser.add_argument('--case',   type=str, default=None)
parser.add_argument('--solver', type=str, default=None)
parser.add_argument('--date',   type=str, default=None)
parser.add_argument('--rawresults', type=str, default=None)
parser.add_argument('--plots', type=str, default=None)

default_DirName    = os.path.dirname(__file__)
default_CaseName   = 'Home1'                              # To select the case
default_SolverName = 'highs'
default_date       = datetime.datetime.now().replace(second=0, microsecond=0)
default_rawresults = 'False'
default_plots      = 'False'

def main():
    initial_time = time.time()
    args = parser.parse_args()

    # %% Model declaration
    oAEGIS = ConcreteModel('Electricity for Low-carbon Integration and eXchange of Resources (EL1XR) - Version 1.0.1 - Sep 25, 2025')

    if args.dir == "":
        args.dir = default_DirName
    elif args.dir is None:
        args.dir        = input('Input Dir         Name (Default {}): '.format(default_DirName))
        if args.dir == '':
            args.dir = default_DirName
    if args.case == "":
        args.case = default_CaseName
    elif args.case is None:
        args.case       = input('Input Case        Name (Default {}): '.format(default_CaseName))
        if args.case == '':
            args.case = default_CaseName
    if args.solver == "":
        args.solver = default_SolverName
    elif args.solver is None:
        args.solver     = input('Input Solver      Name (Default {}): '.format(default_SolverName))
        if args.solver == '':
            args.solver = default_SolverName
    if args.date == "":
        args.date = default_date
    elif args.date is None:
        args.date       = input('Input Date        Name (Default {}): '.format(default_date))
        if args.date == '':
            args.date = default_date
    if args.rawresults == "":
        args.rawresults = default_rawresults
    elif args.rawresults is None:
        args.rawresults = input('Input Raw Results Name (Default {}): '.format(default_rawresults))
        if args.rawresults == '':
            args.rawresults = default_rawresults
    if args.plots == "":
        args.plots = default_plots
    elif args.plots is None:
        args.plots      = input('Input Plots       Name (Default {}): '.format(default_plots))
        if args.plots == '':
            args.plots = default_plots
    for i in range(0, 117):
        print('-', end="")
    print('\n')
    print('Arguments:')
    print(args.case)
    print(args.dir)
    print(args.solver)
    print(args.rawresults)
    print(args.plots)
    for i in range(0, 117):
        print('-', end="")
    print('\n')

    # reading and processing the data
    #
    print('- Initializing the model\n')
    model = data_processing(args.dir, args.case, args.date, oAEGIS)
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
    model = solving_model( args.dir, args.case, args.solver, model, pWrittingLPFile)
    print('- Total time for solving the model:                                    {} seconds\n'.format(round(time.time() - start_time  )))
    start_time = time.time()
    # outputting the results
    # model = saving_rawdata(args.dir, args.case, args.solver, model, model)
    # print('- Total time for outputting the raw data:                              {} seconds\n'.format(round(time.time() - start_time  )))
    # start_time = time.time()
    # outputting the results
    model = saving_results(args.dir, args.case, args.date, model, model)
    print('- Total time for outputting the results:                               {} seconds\n'.format(round(time.time() - start_time  )))
    for i in range(0, 117):
        print('-', end="")
    print('\n')
    elapsed_time = round(time.time() - initial_time)
    print('Elapsed time: {} seconds'.format(elapsed_time))
    path_to_write_time = os.path.join(args.dir,args.case,"oM_Result_rExecutionTime_"+args.case+".txt")
    with open(path_to_write_time, 'w') as f:
         f.write(str(elapsed_time))
    for i in range(0, 117):
        print('-', end="")
    print('\n')

    return model


if __name__ == '__main__':
    model = main()