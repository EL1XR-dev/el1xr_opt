from gurobipy import *

# Define the case name
CaseName = 'oM_Home1'

m = read(CaseName+'.lp')
m.printStats()
m.setParam('Method'   ,2)
m.setParam('Crossover',0)
m.setParam('OutputFlag', 1)
m.setParam('LogToConsole', 1)
m.setParam('NumericFocus', 3)
m.setParam('IISMethod', 0)
m.setParam('BarHomogeneous', 1)
# m.setParam('FeasRelaxS', 0)
# m.write('p2.lp')
# m=m.presolve()
# m.write('pp_PS.lp')
# m.feasRelaxS(2, False, False, True)
# m.optimize()
# m.printQuality()
# print(m.KappaExact)
m.computeIIS()
m.write(CaseName+'.ilp')

# Print out the IIS constraints and variables
print('\nThe following constraints and variables are in the IIS:')
for c in m.getConstrs():
    if c.IISConstr:
        print(f'\t{c.constrname}: {m.getRow(c)} {c.Sense} {c.RHS}')

for v in m.getVars():
    if v.IISLB:
        print(f'\t{v.varname} ≥ {v.LB}')
    if v.IISUB:
        print(f'\t{v.varname} ≤ {v.UB}')