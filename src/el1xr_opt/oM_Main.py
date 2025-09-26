#%% libraries
import argparse
import datetime
import os
import time
# import pkg_resources
from .Modules.oM_Sequence import execution_sequence
from .Modules.oM_SolverSetup import ensure_ampl_solvers

print('\033[1;32mElectricity for Low-carbon Integration and eXchange of Resources (EL1XR) - Version 1.0.1 - Sep 25, 2025\033[0m')
print('\033[34m#### Academic research license - for non-commercial use only ####\033[0m \n')

parser = argparse.ArgumentParser(description='Introducing main parameters...')
parser.add_argument('--case',       type=str, default=None)
parser.add_argument('--dir',        type=str, default=None)
parser.add_argument('--solver',     type=str, default=None)
parser.add_argument('--date',       type=str, default=None)
parser.add_argument('--rawresults', type=str, default=None)
parser.add_argument('--plots',      type=str, default=None)

DIR    = os.path.dirname(__file__)
CASE   = 'Home1'
SOLVER = 'highs'  # 'gurobi'  # 'cbc'  # 'highs'
DATE   = datetime.datetime.now().replace(second=0, microsecond=0)
RAWR   = 'False'
PLOTS  = 'False'

def main():
    # Defining the initial time
    StartTime = time.time()
    # Parsing the arguments
    args = parser.parse_args()
    if args.dir is None:
        args.dir    = input('Input Dir    Name (Default {}): '.format(DIR))
        if args.dir == '':
            args.dir = DIR
    if args.case is None:
        args.case   = input('Input Case   Name (Default {}): '.format(CASE))
        if args.case == '':
            args.case = CASE
    if args.solver is None:
        args.solver = input('Input Solver Name (Default {}): '.format(SOLVER))
        if args.solver == '':
            args.solver = SOLVER
    if args.date is None:
        args.date = input('Date (YYYY-MM-DD) (Default {}): '.format(DATE))
        if args.date == '':
            args.date = DATE
    if args.rawresult is None:
        args.rawresult = input('Would you like to write all the results? (Default {}): '.format(RAWR))
        if args.rawresult == '':
            args.rawresult = RAWR
    if args.plots is None:
        args.plots = input('Would you like to write the plots? (Default {}): '.format(PLOTS))
        if args.plots == '':
            args.plots = PLOTS
    print(args.case)
    print(args.dir)
    print(args.solver)
    print(args.date)
    print(args.rawresults)
    print(args.plots)
    import sys
    print(sys.argv)
    print(args)
    model = execution_sequence(args.dir, args.case, args.solver, args.date, args.rawresult, args.plots)
    # Computing the elapsed time
    ElapsedTime = round(time.time() - StartTime)
    print('Total time                             ...  {} s'.format(ElapsedTime))
    # Final message
    print('End of the run                ************')
    print('\033[34m#### Academic research license - for non-commercial use only ####\033[0m')

    return model

if __name__ == '__main__':
    ensure_ampl_solvers()
    model = main()