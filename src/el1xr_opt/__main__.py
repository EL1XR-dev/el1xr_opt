# el1xr_opt/__main__.py
import argparse
import datetime
import os

from .oM_Main import main
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

if __name__ == "__main__":
    ensure_ampl_solvers()
    main(parser)
