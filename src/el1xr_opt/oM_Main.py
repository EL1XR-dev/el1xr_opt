# ... existing imports ...
import argparse
import datetime as dt
import os

from .oM_Sequence import oM_run
from .oM_SolverSetup import ensure_ampl_solvers

# banner (keep as you have it)
for _ in range(117):
    print('-', end="")
print('\nElectricity for Low-carbon Integration and eXchange of Resources (EL1XR) - Version 1.0.1 - Sep 25, 2025')
print('#### Non-commercial use only ####')

def _parse_date(s: str | None):
    if not s:
        return dt.datetime.now().replace(second=0, microsecond=0)
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return dt.datetime.strptime(s, "%Y-%m-%d")

parser = argparse.ArgumentParser(description='Introducing main arguments...')
parser.add_argument('--dir', required=True,    type=str, help='Base directory containing the case folder')
parser.add_argument('--case', required=True,   type=str, default='Home1', help='Case name (subfolder under --dir)')
parser.add_argument('--solver', required=True, type=str, default='highs', help='Solver name (e.g., highs, cbc, gurobi)')
parser.add_argument('--date', required=True,   type=str, help='ISO date/datetime (YYYY-MM-DD or 2025-09-25T10:00)')
parser.add_argument('--rawresults', required=True, action='store_true', help='Save raw results')
parser.add_argument('--plots', required=True,      action='store_true', help='Generate plots')
parser.add_argument('--interactive', '-i', action='store_true', help='Prompt for inputs interactively')

_default_dir = os.path.dirname(__file__)  # package root (where Home1 lives)

def _ask(prompt, default):
    """Ask once, showing a default; return default if user hits Enter."""
    txt = input(f"{prompt} [{default}]: ").strip()
    return txt or default

def main():
    args = parser.parse_args()

    # Defaults if not provided
    dir_  = args.dir or _default_dir
    case  = args.case
    solv  = args.solver
    date_ = _parse_date(args.date)
    rawr  = args.rawresults
    plots = args.plots

    # Optional interactive prompts
    if args.interactive:
        print("\n-- Interactive mode -- Press Enter to accept the default in [brackets].\n")
        dir_  = _ask("Directory", dir_)
        case  = _ask("Case", case)
        solv  = _ask("Solver", solv)
        date_in = _ask("Date (YYYY-MM-DD or ISO datetime)", date_.isoformat(timespec="minutes"))
        date_ = _parse_date(date_in)
        rawr  = _ask("Save raw results? (True/False)", str(rawr)).lower() in ("1","t","true","y","yes")
        plots = _ask("Generate plots? (True/False)",    str(plots)).lower() in ("1","t","true","y","yes")
        print()

    print('Arguments:')
    print(f' Case:        {case}')
    print(f' Dir:         {dir_}')
    print(f' Solver:      {solv}')
    print(f' Date:        {date_}')
    print(f' Raw Results: {rawr}')
    print(f' Plots:       {plots}')
    for _ in range(117):
        print('-', end="")
    print('\n')

    model = oM_run(
        dir=dir_,
        case=case,
        solver=solv,
        date=date_,
        rawresults=rawr,
        plots=plots
    )
    return model

if __name__ == "__main__":
    ensure_ampl_solvers()
    main()
