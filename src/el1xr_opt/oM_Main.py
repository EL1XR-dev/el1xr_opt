import argparse

from .oM_Sequence import oM_run

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
