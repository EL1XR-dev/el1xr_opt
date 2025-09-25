import argparse
import datetime
import os

from .oM_Sequence import oM_run
from .oM_SolverSetup import ensure_ampl_solvers

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
    args = parser.parse_args()
    if args.dir is None:
        args.dir = default_DirName
    if args.case is None:
        args.case = default_CaseName
    if args.solver is None:
        args.solver = default_SolverName
    if args.date is None:
        args.date = default_date
    if args.rawresults is None:
        args.rawresults = default_rawresults
    if args.plots is None:
        args.plots = default_plots

    print('Arguments:')
    print(f' Case:        {args.case}')
    print(f' Dir:         {args.dir}')
    print(f' Solver:      {args.solver}')
    print(f' Date:        {args.date}')
    print(f' Raw Results: {args.rawresults}')
    print(f' Plots:       {args.plots}')
    for i in range(0, 117):
        print('-', end="")
    print('\n')

    model = oM_run(
        dir=args.dir,
        case=args.case,
        solver=args.solver,
        date=args.date,
        rawresults=args.rawresults,
        plots=args.plots
    )

    return model

if __name__ == "__main__":
    ensure_ampl_solvers()
    main()
