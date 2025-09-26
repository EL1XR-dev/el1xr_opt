# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import time          # count clock time
import os
import psutil        # access the number of CPUs
from amplpy        import modules
from pyomo.environ import Var, Suffix, SolverFactory


def solving_model(DirName, CaseName, SolverName, optmodel, pWriteLP):
    # start time
    StartTime = time.time()

    # defining the path
    _path = os.path.join(DirName, CaseName)

    if pWriteLP == 1:
        # %% solving the problem
        optmodel.write(_path + '/oM_' + CaseName + '.lp', io_options={'symbolic_solver_labels': True})  # create lp-format file
        WritingLPTime = time.time() - StartTime
        StartTime = time.time()
        print('Writing LP file                       ... ', round(WritingLPTime), 's')

    SubSolverName = ''

    if SolverName == 'cplex':
        SubSolverName = 'cplex'
        SolverName = 'gams'

    # if SolverName == 'highs':
    #     SubSolverName = 'highs'
    #     SolverName = 'gams'

    if SolverName == 'highs':
        Solver = SolverFactory(SolverName + "nl", executable=modules.find(SolverName), solve_io="nl")
    else:
        Solver = SolverFactory(SolverName)  # select solver
    if SolverName == 'gurobi':
        Solver.options['LogFile'] = _path + '/oM_' + CaseName + '.log'
        # Solver.options['IISFile'      ] = _path+'/oH_'+CaseName+'.ilp'                   # should be uncommented to show results of IIS
        # Solver.options['Method'       ] = 2                                             # barrier method
        Solver.options['Method'] = 2  # barrier method
        Solver.options['MIPFocus'] = 1
        Solver.options['Presolve'] = 2
        Solver.options['RINS'] = 100
        Solver.options['Crossover'] = -1
        Solver.options['FeasibilityTol'] = 1e-9
        # Solver.options['BarConvTol'    ] = 1e-9
        # Solver.options['BarQCPConvTol' ] = 0.025
        # Solver.options['NumericFocus'  ] = 3
        Solver.options['MIPGap'] = 0.02
        Solver.options['Threads'] = int((psutil.cpu_count(logical=True) + psutil.cpu_count(logical=False)) / 2)
        Solver.options['TimeLimit'] = 3600
        Solver.options['IterationLimit'] = 1800000
    if SubSolverName == 'cplex':
        solver_options = {
            'file COPT / cplex.opt / ; put COPT putclose "EPGap 0.01" / "LPMethod 4" / "RINSHeur 100" / ; GAMS_MODEL.OptFile = 1 ;'
            'option SysOut  = off   ;',
            'option LP      = cplex ; option MIP     = cplex    ;',
            'option ResLim  = 36000 ; option IterLim = 36000000 ;',
            'option Threads = '+str(int((psutil.cpu_count(logical=True) + psutil.cpu_count(logical=False))/2))+' ;'
            }
    if SubSolverName == 'highs':
        solver_options = {
            'file COPT / highs.opt / ; put COPT putclose "mip_rel_gap = 0.01" / "presolve = on" /  ; gams_model.optfile = 1 ;'
            'option SysOut  = off   ;',
            'option LP      = highs ; option MIP     = highs    ;',
            'option ResLim  = 36000 ; option IterLim = 36000000 ;',
            'option Threads = ' + str(int((psutil.cpu_count(logical=True) + psutil.cpu_count(logical=False)) / 2)) + ' ;'
            }
    idx = 0
    for var in optmodel.component_data_objects(Var, active=False, descend_into=True):
        if not var.is_continuous():
            idx += 1
    if idx == 0:
        optmodel.dual = Suffix(direction=Suffix.IMPORT)
        optmodel.rc = Suffix(direction=Suffix.IMPORT)

    if SolverName == 'gams':
        SolverResults = Solver.solve(optmodel, tee=True, report_timing=True, symbolic_solver_labels=False, add_options=solver_options)
    else:
        SolverResults = Solver.solve(optmodel, tee=True, report_timing=True)
    print('Termination condition: ', SolverResults.solver.termination_condition)
    SolverResults.write()  # summary of the solver results

    # %% fix values of binary variables to get dual variables and solve it again
    print('# ============================================================================= #')
    print('# ============================================================================= #')
    idx = 0
    for var in optmodel.component_data_objects(Var, active=True, descend_into=True):
        if not var.is_continuous():
            # print("fixing: " + str(var))
            var.fixed = True  # fix the current value
            idx += 1
    print("Number of fixed variables: ", idx)
    print('# ============================================================================= #')
    print('# ============================================================================= #')
    if idx != 0:
        optmodel.del_component(optmodel.dual)
        optmodel.del_component(optmodel.rc)
        optmodel.dual = Suffix(direction=Suffix.IMPORT)
        optmodel.rc = Suffix(direction=Suffix.IMPORT)
        if SolverName == 'gams':
            SolverResults = Solver.solve(optmodel, tee=True, report_timing=True, symbolic_solver_labels=False, add_options=solver_options)
        else:
            SolverResults = Solver.solve(optmodel, tee=False, report_timing=True)
        SolverResults.write()  # summary of the solver results

    SolvingTime = time.time() - StartTime
    print('Solving                               ... ', round(SolvingTime), 's')

    print('Objective function value                  ', round(optmodel.eTotalSCost.expr(), 2), 'M€')

    return optmodel