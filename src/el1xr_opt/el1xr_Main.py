# Developed by: Erik F. Alvarez

# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import argparse
import datetime
import os
import psutil                                       # access the number of CPUs

from .Modules.oM_Sequence import routine

for i in range(0, 117):
    print('-', end="")

print('\nElectricity for Low-carbon Integration and eXchange of Resources (EL1XR)')
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

    # %% model call
    model = routine(args.dir, args.case, args.solver, args.date, args.rawresults, args.plots)

    return model


if __name__ == '__main__':
    model = main()