# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import time          # count clock time
from   pyomo.environ     import Constraint, Objective, minimize
from   collections       import defaultdict

def create_objective_function(model, optmodel):
    # this function declares constraints
    StartTime = time.time() # to compute elapsed time

    print('-- Declaring objective function')

    # tolerance to consider avoid division by 0
    pEpsilon = 1e-6

    # defining the objective function
    def eTotalSCost(optmodel):
        return optmodel.vTotalSCost
    optmodel.__setattr__('eTotalSCost', Objective(rule=eTotalSCost, sense=minimize, doc='Total system cost [MEUR]'))

    def eTotalTCost(optmodel):
        return optmodel.vTotalSCost == sum(optmodel.Par['pDiscountFactor'][idx[0]] * (optmodel.__getattribute__(f'vTotalEleMCost')[idx] + optmodel.__getattribute__(f'vTotalHydMCost')[idx] + optmodel.__getattribute__(f'vTotalEleGCost')[idx] + optmodel.__getattribute__(f'vTotalHydGCost')[idx] + optmodel.__getattribute__(f'vTotalECost')[idx] + optmodel.__getattribute__(f'vTotalEleCCost')[idx] + optmodel.__getattribute__(f'vTotalHydCCost')[idx] + optmodel.__getattribute__(f'vTotalEleRCost')[idx] + optmodel.__getattribute__(f'vTotalHydRCost')[idx]) for idx in model.psn) + sum(optmodel.__getattribute__(f'vTotalElePeakCost')[idx] for idx in model.ps)
    optmodel.__setattr__('eTotalTCost', Constraint(rule=eTotalTCost, doc='Total system cost [MEUR]'))

    print('--- Declaring the totals components of the ObjFunc:                    {} seconds'.format(round(time.time() - StartTime)))

    return model

def create_objective_function_components(model, optmodel):
    #
    StartTime = time.time() # to compute elapsed time
    # Market variable cost [M€]
    def eTotalEleMCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleMCost[p,sc,n] ==   optmodel.vTotalEleTradeCost[p,sc,n] - optmodel.vTotalEleTradeProfit[p,sc,n])
    optmodel.__setattr__('eTotalEleMCost', Constraint(optmodel.psn, rule=eTotalEleMCost, doc='Total electricity market cost [MEUR]'))

    def eTotalHydMCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydMCost[p,sc,n] ==   optmodel.vTotalHydTradeCost[p,sc,n] - optmodel.vTotalHydTradeProfit[p,sc,n])
    optmodel.__setattr__('eTotalHydMCost', Constraint(optmodel.psn, rule=eTotalHydMCost, doc='Total hydrogen market cost [MEUR]'))

    def eTotalEleTradeCost(optmodel, p,sc,n):
        return optmodel.vTotalEleTradeCost  [p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (((model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetelcertifikat'][er] * model.factor1 + model.Par['pEleRetpaslag'][er] * model.factor1) * (1+model.Par['pEleRetmoms'][er] * model.factor1) + model.Par['pEleRetnetavgift'][er] * model.factor1) * optmodel.vEleBuy [p,sc,n,er]) for er in model.er)
    optmodel.__setattr__('eTotalEleTradeCost', Constraint(optmodel.psn, rule=eTotalEleTradeCost, doc='Total electricity trade cost [MEUR]'))

    def eTotalEleTradeProfit(optmodel, p,sc,n):
        return optmodel.vTotalEleTradeProfit[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] *   (model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er]                                                                                                                                                                                                                 * optmodel.vEleSell[p,sc,n,er]) for er in model.er)
    optmodel.__setattr__('eTotalEleTradeProfit', Constraint(optmodel.psn, rule=eTotalEleTradeProfit, doc='Total electricity trade profit [MEUR]'))

    def eTotalHydTradeCost(optmodel, p,sc,n):
        return optmodel.vTotalHydTradeCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pVarEnergyCost'][hr][p,sc,n] * optmodel.vHydBuy[p,sc,n,hr]) for hr in model.hr)
    optmodel.__setattr__('eTotalHydTradeCost', Constraint(optmodel.psn, rule=eTotalHydTradeCost, doc='Total hydrogen trade cost [MEUR]'))

    def eTotalHydTradeProfit(optmodel, p,sc,n):
        return optmodel.vTotalHydTradeProfit[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pVarEnergyPrice'][hr][p,sc,n] * optmodel.vHydSell[p,sc,n,hr]) for hr in model.hr)
    optmodel.__setattr__('eTotalHydTradeProfit', Constraint(optmodel.psn, rule=eTotalHydTradeProfit, doc='Total hydrogen trade profit [MEUR]'))

    # Generation operation cost [M€]
    def eTotalEleGCost(optmodel, p,sc,n):
        return optmodel.vTotalEleGCost[p,sc,n] == (sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenLinearVarCost'  ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenConstantVarCost'][egt] *       optmodel.vEleGenCommitment     [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenStartUpCost'    ][egt] *       optmodel.vEleGenStartUp        [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenShutDownCost'   ][egt] *       optmodel.vEleGenShutDown       [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenOMVariableCost' ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ))
    optmodel.__setattr__('eTotalEleGCost', Constraint(optmodel.psn, rule=eTotalEleGCost, doc='Total electricity generation cost [MEUR]'))

    # Generation operation cost [M€]
    def eTotalHydGCost(optmodel, p,sc,n):
        return optmodel.vTotalHydGCost[p,sc,n] == (sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenLinearVarCost'  ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenConstantVarCost'][hgt] *       optmodel.vHydGenCommitment     [p,sc,n,hgt] for hgt in model.hgt) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenStartUpCost'    ][hgt] *       optmodel.vHydGenStartUp        [p,sc,n,hgt] for hgt in model.hgt) +
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenShutDownCost'   ][hgt] *       optmodel.vHydGenShutDown       [p,sc,n,hgt] for hgt in model.hgt) -
                                                   sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenOMVariableCost' ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ))
    optmodel.__setattr__('eTotalHydGCost', Constraint(optmodel.psn, rule=eTotalHydGCost, doc='Total hydrogen generation cost [MEUR]'))

    # Generation emission cost [M€]
    def eTotalECost(optmodel, p,sc,n):
        return optmodel.vTotalECost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * model.Par['pGenCO2EmissionCost'][egt] * optmodel.vEleTotalOutput[p,sc,n,egt] for egt in model.egt)
    optmodel.__setattr__('eTotalECost', Constraint(optmodel.psn, rule=eTotalECost, doc='Total emission cost [MEUR]'))

    # Consumption operation cost [M€]
    def eTotalEleCCost(optmodel, p,sc,n):
        return optmodel.vTotalEleCCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * model.Par['pEleGenLinearTerm'][egs] * optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs)
    optmodel.__setattr__('eTotalEleCCost', Constraint(optmodel.psn, rule=eTotalEleCCost, doc='Total consumption cost in electricity units [MEUR]'))

    def eTotalHydCCost(optmodel, p,sc,n):
        return optmodel.vTotalHydCCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * model.Par['pHydGenLinearTerm'][hgs] * optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs)
    optmodel.__setattr__('eTotalHydCCost', Constraint(optmodel.psn, rule=eTotalHydCCost, doc='Total consumption cost in hydrogen units [MEUR]'))

    # Reliability cost [M€]
    def eTotalEleRCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleRCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pParENSCost'] * optmodel.vENS[p,sc,n,ed]) for ed in model.ed))
    optmodel.__setattr__('eTotalEleRCost', Constraint(optmodel.psn, rule=eTotalEleRCost, doc='Total reliability cost in electricity consumers [MEUR]'))

    def eTotalHydRCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydRCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pParHNSCost'] * optmodel.vHNS[p,sc,n,hd]) for hd in model.hd))
    optmodel.__setattr__('eTotalHydRCost', Constraint(optmodel.psn, rule=eTotalHydRCost, doc='Total reliability cost in hydrogen consumers [MEUR]'))

    def eTotalElePeakCost(optmodel, p,sc):
        return (optmodel.vTotalElePeakCost[p,sc] == sum(model.Par['pEleRetTariff'][er] * model.factor1 * sum(optmodel.vElePeak[p,sc,m,er,peak] for peak in model.Peaks for m in model.moy) for er in model.er) / len(model.Peaks))
    optmodel.__setattr__('eTotalElePeakCost', Constraint(optmodel.ps, rule=eTotalElePeakCost, doc='Total electricity peak cost [MEUR]'))

    print('--- Declaring the ObjFunc components:                                  {} seconds'.format(round(time.time() - StartTime)))

    return model

def create_constraints(model, optmodel):
    # this function declares constraints
    StartTime = time.time()  # to compute elapsed time

    print('-- Declaring constraints for the market')

    # incoming and outgoing lines (lin) (lout)
    lin   = defaultdict(list)
    lout  = defaultdict(list)
    for ni,nf,cc in model.ela:
        lin  [nf].append((ni,cc))
        lout [ni].append((nf,cc))

    hin   = defaultdict(list)
    hout  = defaultdict(list)
    for ni,nf,cc in model.hpa:
        hin  [nf].append((ni,cc))
        hout [ni].append((nf,cc))

    # nodes to generators (g2n)
    eg2n = defaultdict(list)
    for nd,eg in model.n2eg:
        eg2n[nd].append(eg)
    hg2n = defaultdict(list)
    for nd,hg in model.n2hg:
        hg2n[nd].append(hg)
    egt2n = defaultdict(list)
    for nd,egt in model.nd*model.egt:
        if (nd,egt) in model.n2eg:
            egt2n[nd].append(egt)
    hgt2n = defaultdict(list)
    for nd,hgt in model.nd*model.hgt:
        if (nd,hgt) in model.n2hg:
            hgt2n[nd].append(hgt)
    egs2n = defaultdict(list)
    for nd,egs in model.nd*model.egs:
        if (nd,egs) in model.n2eg:
            egs2n[nd].append(egs)
    hgs2n = defaultdict(list)
    for nd,hgs in model.nd*model.hgs:
        if (nd,hgs) in model.n2hg:
            hgs2n[nd].append(hgs)

    #%% Constraints
    # Maximum electricity buys
    def eEleRetMaxBuy(optmodel, p,sc,n,er):
        if model.Par['pEleRetMaxBuy'][er] > 0:
            return optmodel.vEleBuy[p,sc,n,er] <= model.Par['pEleRetMaxBuy'][er]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRetMaxBuy', Constraint(optmodel.psner, rule=eEleRetMaxBuy, doc='Maximum electricity buys [MWh]'))

    # Maximum electricity sells
    def eEleRetMaxSell(optmodel, p,sc,n,er):
        if model.Par['pEleRetMaxSell'][er] > 0:
            return optmodel.vEleSell[p,sc,n,er] <= model.Par['pEleRetMaxSell'][er]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRetMaxSell', Constraint(optmodel.psner, rule=eEleRetMaxSell, doc='Maximum electricity sells [MWh]'))

    print('--- Declaring the maximum electricity buys and sells:                  {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    #%% shifting demand constraints
    # electricity demand balance: ensure the total electricity consumed before and after the shift is the same within the shift time
    def eEleDemandShiftBalance(optmodel, p,sc,n,ed):
        if model.Par['pEleDemFlexible'][ed] == 1.0 and model.Par['pEleDemShiftedSteps'][ed]:
            if model.n.ord(n) % model.Par['pEleDemShiftedSteps'][ed] == 0:
                return sum(optmodel.vEleDemand[p,sc,n2,ed] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleDemShiftedSteps'][ed]:model.n.ord(n)])  == sum(model.Par['pVarMaxDemand'][ed][p,sc,n2] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleDemShiftedSteps'][ed]:model.n.ord(n)])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDemandShiftBalance', Constraint(optmodel.psned, rule=eEleDemandShiftBalance, doc='Electricity demand shift balance'))

    # electricity demand after shifting
    def eEleDemandShifted(optmodel, p,sc,n,ed):
        if model.Par['pEleDemFlexible'][ed] == 1.0 and model.Par['pEleDemShiftedSteps'][ed]:
            return optmodel.vEleDemand[p,sc,n,ed] == model.Par['pVarMaxDemand'][ed][p,sc,n] + optmodel.vEleDemFlex[p,sc,n,ed]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDemandShifted', Constraint(optmodel.psned, rule=eEleDemandShifted, doc='Electricity demand after shifting'))

    print('--- Declaring the electricity demand shift constraints:                 {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # electrical energy conservation or balance
    def eEleBalance(optmodel, p,sc,n,nd):
        if sum(1 for eg in eg2n[nd]) + sum(1 for egs in egs2n[nd]) + sum(1 for nf, cc in lout[nd]) + sum(1 for ni, cc in lin[nd]):
            return (sum(optmodel.vEleTotalOutput[p,sc,n,eg] for eg in model.eg  if (nd,eg) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs if (nd,egs) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,e2h] for e2h in model.e2h if (nd,e2h) in model.n2hg)
                  - sum(optmodel.vEleNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in lout[nd]) + sum(optmodel.vEleNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in lin[nd]) + sum(optmodel.vEleBuy[p,sc,n,er] - optmodel.vEleSell[p,sc,n,er] for er in model.er if (nd,er) in model.n2er) == sum(optmodel.vEleDemand[p,sc,n,ed] - optmodel.vENS[p,sc,n,ed] for ed in model.ed if (nd,ed) in model.n2ed))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleBalance', Constraint(optmodel.psnnd, rule=eEleBalance, doc='Electricity balance in the DA market'))

    # hydrogen energy conservation or balance
    def eHydBalance(optmodel, p,sc,n,nd):
        if sum(1 for hg in hg2n[nd]) + sum(1 for hgs in hgs2n[nd]) + sum(1 for nf, cc in hout[nd]) + sum(1 for ni, cc in hin[nd]):
            return (sum(optmodel.vHydTotalOutput[p,sc,n,hg] for hg in model.hg if (nd,hg) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs if (nd,hgs) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,h2e] for h2e in model.h2e if (nd,h2e) in model.n2g)
                  - sum(optmodel.vHydNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in hout[nd]) + sum(optmodel.vHydNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in hin[nd]) + sum(optmodel.vHydBuy[p,sc,n,hr] - optmodel.vHydSell[p,sc,n,hr] for hr in model.hr if (nd,hr) in model.n2hr) == sum(optmodel.vHydDemand[p,sc,n,hd] - optmodel.vHNS[p,sc,n,hd] for hd in model.hd if (nd,hd) in model.n2hd))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydBalance', Constraint(optmodel.psnnd, rule=eHydBalance, doc='Hydrogen balance in the DA market'))

    print('--- Declaring the energy balance:                                      {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Energy inflows of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the inflows data [p.u.]
    def eEleMaxInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMaxInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMaxInflows'][egs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMaxInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eEleMinInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMinStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMinInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMinInflows'][egs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMinInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eHydMaxInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMaxInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMaxInflows'][hgs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMaxInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eHydMinInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMinInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMinInflows'][hgs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMinInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    print('--- Declaring the energy inflows of ESS:                               {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # ESS energy inventory (only for load levels multiple of 1, 24, 168 h depending on the ESS storage type) [GWh]
    def eEleInventory(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] + model.Par['pEleMaxPower'][egs][p,sc,n] and (n,egs) in model.negs:
            if   model.n.ord(n) == model.Par['pEleCycleTimeStep'][egs]:
                return model.Par['pEleInitialInventory'][egs][p,sc,n]                                       + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vEleEnergyInflows[p,sc,n2,egs] - optmodel.vEleEnergyOutflows[p,sc,n2,egs] - (optmodel.vEleTotalOutput[p,sc,n2,egs] * (1/(model.Par['pEleGenEfficiency_discharge'][egs]))) + (model.Par['pEleGenEfficiency_charge'][egs]) * optmodel.vEleTotalCharge[p,sc,n2,egs]) for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleCycleTimeStep'][egs]:model.n.ord(n)]) == optmodel.vEleInventory[p,sc,n,egs] + optmodel.vEleSpillage[p,sc,n,egs]
            elif model.n.ord(n) >  model.Par['pEleCycleTimeStep'][egs]:
                return optmodel.vEleInventory[p,sc,model.n.prev(n,model.Par['pEleCycleTimeStep'][egs]),egs] + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vEleEnergyInflows[p,sc,n2,egs] - optmodel.vEleEnergyOutflows[p,sc,n2,egs] - (optmodel.vEleTotalOutput[p,sc,n2,egs] * (1/(model.Par['pEleGenEfficiency_discharge'][egs]))) + (model.Par['pEleGenEfficiency_charge'][egs]) * optmodel.vEleTotalCharge[p,sc,n2,egs]) for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleCycleTimeStep'][egs]:model.n.ord(n)]) == optmodel.vEleInventory[p,sc,n,egs] + optmodel.vEleSpillage[p,sc,n,egs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventory', Constraint(optmodel.psnegs, rule=eEleInventory, doc='Electricity ESS inventory balance [GWh]'))

    def eHydInventory(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.negs:
            if   model.n.ord(n) == model.Par['pHydCycleTimeStep'][hgs]:
                return model.Par['pHydInitialInventory'][hgs][p,sc,n]                                       + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in list(model.n2)[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            elif model.n.ord(n) >  model.Par['pHydCycleTimeStep'][hgs]:
                return optmodel.vHydInventory[p,sc,model.n.prev(n,model.Par['pHydCycleTimeStep'][hgs]),hgs] + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in list(model.n2)[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydInventory', Constraint(optmodel.psnhgs, rule=eHydInventory, doc='Hydrogen ESS inventory balance [KgH2h]'))

    print('--- Declaring the ESS energy inventory:                                {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Energy conversion from energy from electricity to hydrogen and vice versa [p.u.]
    def eAllEnergy2Hyd(optmodel, p,sc,n,e2h):
        if model.Par['pHydMaxPower'][e2h][p,sc,n] and e2h in model.e2h:
            return optmodel.vHydTotalOutput[p,sc,n,e2h] == optmodel.vEleTotalCharge[p,sc,n,e2h] / model.Par['pHydGenProductionFunction'][e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eAllEnergy2Hyd', Constraint(optmodel.psne2h, rule=eAllEnergy2Hyd, doc='energy conversion from different energy type to hydrogen [p.u.]'))

    def eAllEnergy2Ele(optmodel, p,sc,n,h2e):
        if model.Par['pEleMaxPower'][h2e][p,sc,n] and h2e in model.h2e:
            return optmodel.vEleTotalOutput[p,sc,n,h2e] == optmodel.vHydTotalCharge[p,sc,n,h2e] * model.Par['pEleGenProductionFunction'][h2e]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eAllEnergy2Ele', Constraint(optmodel.psnh2e, rule=eAllEnergy2Ele, doc='energy conversion from different energy type to electricity [p.u.]'))

    # ESS outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) must be satisfied [GWh]
    def eEleMaxOutflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMaxOutflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyOutflows[p,sc,n,egs] / model.Par['pEleMaxOutflows'][egs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxOutflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMaxOutflows2Commitment, doc='energy outflows to commitment [p.u.]'))

    def eEleMinOutflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMinOutflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyOutflows[p,sc,n,egs] / model.Par['pEleMinOutflows'][egs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinOutflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMinOutflows2Commitment, doc='energy outflows to commitment [p.u.]'))

    def eHydMaxOutflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMaxOutflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyOutflows[p,sc,n,hgs] / model.Par['pHydMaxOutflows'][hgs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxOutflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMaxOutflows2Commitment, doc='energy outflows to commitment [p.u.]'))

    def eHydMinOutflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinCharge'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMinOutflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyOutflows[p,sc,n,hgs] / model.Par['pHydMinOutflows'][hgs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinOutflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMinOutflows2Commitment, doc='energy outflows to commitment [p.u.]'))

    def eEleMaxEnergyOutflows(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] + model.Par['pEleMaxPower'][egs][p,sc,n] and (n,egs) in model.negso:
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMaxOutflows'][egs][p,sc,n2] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMaxEnergyOutflows, doc='electricity energy outflows of an ESS unit [GWh]'))

    def eEleMinEnergyOutflows(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] + model.Par['pEleMinPower'][egs][p,sc,n] and (n,egs) in model.negso:
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMinOutflows'][egs][p,sc,n2] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMinEnergyOutflows, doc='electricity energy outflows of an ESS unit [GWh]'))

    def eHydMaxEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMaxOutflows'][hgs][p,sc,n2] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMaxEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [tH2]'))

    def eHydMinEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinCharge'][hgs][p,sc,n] + model.Par['pHydMinPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMinOutflows'][hgs][p,sc,n2] for n2 in list(model.n2)[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMinEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [tH2]'))

    print('--- Declaring the ESS outflows:                                        {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Maximum and minimum output of the second block of a committed unit (all except the VRES and ESS units) [p.u.]
    def eEleMaxOutput2ndBlock(optmodel, p,sc,n,egt):
        if   model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs and n != model.n.last():
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] / model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] <= optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt] - optmodel.vEleGenShutDown[p,sc,model.n.next(n),egt]
        elif model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs and n == model.n.last():
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] / model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] <= optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxOutput2ndBlock', Constraint(optmodel.psnegt, rule=eEleMaxOutput2ndBlock, doc='max output of the second block of a committed unit [p.u.]'))

    def eEleMinOutput2ndBlock(optmodel, p,sc,n,egt):
        if model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs:
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] / model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinOutput2ndBlock', Constraint(optmodel.psnegt, rule=eEleMinOutput2ndBlock, doc='min output of the second block of a committed unit [p.u.]'))

    def eHydMaxOutput2ndBlock(optmodel, p,sc,n,hgt):
        if   model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs and n != model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] <= optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt] - optmodel.vHydGenShutDown[p,sc,model.n.next(n),hgt]
        elif model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs and n == model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] <= optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxOutput2ndBlock', Constraint(optmodel.psnhgt, rule=eHydMaxOutput2ndBlock, doc='max output of the second block of a committed unit [p.u.]'))

    def eHydMinOutput2ndBlock(optmodel, p,sc,n,hgt):
        if model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs:
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinOutput2ndBlock', Constraint(optmodel.psnhgt, rule=eHydMinOutput2ndBlock, doc='min output of the second block of a committed unit [p.u.]'))

    print('--- Declaring the maximum and minimum output of the second block:      {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Maximum and minimum output of the second block of an electricity ESS [p.u.]
    def eEleMaxESSOutput2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and n != model.n.last():
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] / model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        elif model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and n == model.n.last():
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] / model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSOutput2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSOutput2ndBlock, doc='max output of the second block of an ESS [p.u.]'))

    def eEleMinESSOutput2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n]:
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] / model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinESSOutput2ndBlock', Constraint(optmodel.psnegs, rule=eEleMinESSOutput2ndBlock, doc='min output of the second block of an ESS [p.u.]'))

    def eHydMaxESSOutput2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and n != model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] <= model.Par['pVarFixedAvailability'][hgs][p,sc,n]
        elif model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and n == model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] <= model.Par['pVarFixedAvailability'][hgs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxESSOutput2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMaxESSOutput2ndBlock, doc='max output of the second block of an ESS [p.u.]'))

    def eHydMinESSOutput2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n]:
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinESSOutput2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMinESSOutput2ndBlock, doc='min output of the second block of an ESS [p.u.]'))

    # Maximum and minimum charge of an ESS [p.u.]
    def eEleMaxESSCharge2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n] and model.Par['pEleGenNoOperatingReserve'][egs] == 0:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] / model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSCharge2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eEleMinESSCharge2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n] and model.Par['pEleGenNoOperatingReserve'][egs] == 0:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] / model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinESSCharge2ndBlock', Constraint(optmodel.psnegs, rule=eEleMinESSCharge2ndBlock, doc='min charge of an ESS [p.u.]'))

    def eE2HMaxCharge2ndBlock(optmodel, p,sc,n,e2h):
        if model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n]:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] / model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] <= optmodel.vHydGenCommitment[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eE2HMaxCharge2ndBlock', Constraint(optmodel.psne2h, rule=eE2HMaxCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eE2HMinCharge2ndBlock(optmodel, p,sc,n,e2h):
        if model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n]:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] / model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] >= optmodel.vHydGenCommitment[p,sc,n,e2h] - 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eE2HMinCharge2ndBlock', Constraint(optmodel.psne2h, rule=eE2HMinCharge2ndBlock, doc='min charge of an ESS [p.u.]'))

    def eHydMaxESSCharge2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            return optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n] <= model.Par['pVarFixedAvailability'][hgs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eMaxHydESSCharge2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMaxESSCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eHydMinESSCharge2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            return optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinESSCharge2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMinESSCharge2ndBlock, doc='min charge of an ESS [p.u.]'))

    print('--- Declaring the maximum and minimum charge of an ESS:                {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Incompatibility between charge and discharge of an electrical ESS [p.u.]
    def eEleChargingDecision(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] :
            return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pEleMaxCharge'][egs][p,sc,n]  <= optmodel.vEleStorOperat[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleChargingDecision', Constraint(optmodel.psnegs, rule=eEleChargingDecision, doc='charging decision [p.u.]'))

    def eEleDischargingDecision(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxPower'][egs][p,sc,n] :
            return optmodel.vEleTotalOutput[p,sc,n,egs] / model.Par['pEleMaxPower'][egs][p,sc,n]  <= 1.0 - optmodel.vEleStorOperat[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDischargingDecision', Constraint(optmodel.psnegs, rule=eEleDischargingDecision, doc='discharging decision [p.u.]'))

    # Incompatibility between charge and discharge of an H2 ESS [p.u.]
    def eHydChargingDecision(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxPower'][hgs][p,sc,n] :
            return optmodel.vHydTotalOutput[p,sc,n,hgs] / model.Par['pHydMaxPower'][hgs][p,sc,n]  <= optmodel.vHydStorOperat[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydChargingDecision', Constraint(optmodel.psnhgs, rule=eHydChargingDecision, doc='charging decision [p.u.]'))

    def eHydDischargingDecision(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] :
            return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMaxCharge'][hgs][p,sc,n]  <= 1.0 - optmodel.vHydStorOperat[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydDischargingDecision', Constraint(optmodel.psnhgs, rule=eHydDischargingDecision, doc='discharging decision [p.u.]'))

    print('--- Declaring the incompatibility between charge and discharge:        {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Total output of a committed unit (all except the VRES units) [GW]
    def eEleTotalOutput(optmodel, p,sc,n,egnr):
        if model.Par['pEleMaxPower'][egnr][p,sc,n]:
            if model.Par['pEleMinPower'][egnr][p,sc,n] == 0.0:
                return optmodel.vEleTotalOutput[p,sc,n,egnr]                                           ==                                                     optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr]
            elif model.Par['pEleMinPower'][egnr][p,sc,n] != 0.0 and egnr in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n] == model.Par['pVarFixedAvailability'][egnr][p,sc,n] + (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n])
            elif model.Par['pEleMinPower'][egnr][p,sc,n] != 0.0 and egnr not in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n] == optmodel.vEleGenCommitment[p,sc,n,egnr]          + (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalOutput', Constraint(optmodel.psnegnr, rule=eEleTotalOutput, doc='total output of a unit [GW]'))

    # Total output of an H2 producer unit [tH2]
    def eHydTotalOutput(optmodel, p,sc,n,hgt):
        if model.Par['pHydMaxPower'][hgt][p,sc,n]:
            if model.Par['pHydMinPower'][hgt][p,sc,n] == 0.0:
                return optmodel.vHydTotalOutput[p,sc,n,hgt]                                          ==                                                    optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]
            elif model.Par['pHydMinPower'][hgt][p,sc,n] != 0.0 and hgt in model.hgs:
                return optmodel.vHydTotalOutput[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n] == model.Par['pVarFixedAvailability'][hgs][p,sc,n] + (optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n])
            elif model.Par['pHydMinPower'][hgt][p,sc,n] != 0.0 and hgt not in model.hgs:
                return optmodel.vHydTotalOutput[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n] == optmodel.vHydGenCommitment[p,sc,n,hgt]          + (optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydTotalOutput', Constraint(optmodel.psnhgt, rule=eHydTotalOutput, doc='total output of an H2 producer unit [tH2]'))

    print('--- Declaring the total output of a committed unit:                    {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Total charge of an ESS [GW]
    def eEleTotalCharge(optmodel, p,sc,n,egs):
        if egs in model.egs:
            if model.Par['pEleMaxCharge'][egs][p,sc,n] and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
                if model.Par['pEleMinCharge'][egs][p,sc,n] == 0.0:
                    return optmodel.vEleTotalCharge[p,sc,n,egs]                                           ==                                                    optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
                else:
                    return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pEleMinCharge'][egs][p,sc,n] == model.Par['pVarFixedAvailability'][egs][p,sc,n] + (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] / model.Par['pEleMinCharge'][egs][p,sc,n])
            else:
                return Constraint.Skip
        elif egs in model.e2h:
            if model.Par['pHydMaxCharge'][egs][p,sc,n] and model.Par['pHydMaxCharge2ndBlock'][egs][p,sc,n]:
                if model.Par['pHydMinCharge'][egs][p,sc,n] == 0.0:
                    return optmodel.vEleTotalCharge[p,sc,n,egs]                                           ==                                           optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
                else:
                    return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pHydMinCharge'][egs][p,sc,n] == optmodel.vHydGenCommitment[p,sc,n,egs] + (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] / model.Par['pHydMinCharge'][egs][p,sc,n])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalCharge', Constraint(optmodel.psneh, rule=eEleTotalCharge, doc='total charge of an ESS unit [GW]'))

    print('--- Declaring the total charge of an ESS:                              {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Total charge of an H2 ESS unit [tH2]
    def eHydTotalCharge(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] and model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            if model.Par['pHydMinCharge'][hgs][p,sc,n] == 0.0:
                return optmodel.vHydTotalCharge[p,sc,n,hgs]                                           ==                                                    optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]
            else:
                return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n] == model.Par['pVarFixedAvailability'][hgs][p,sc,n] + (optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydTotalCharge', Constraint(optmodel.psnhgs, rule=eHydTotalCharge, doc='total charge of an H2 ESS unit [tH2]'))

    # Incompatibility between charge and outflows use of an ESS [p.u.]
    def eIncompatibilityEleChargeOutflows(optmodel, p,sc,n,egs):
        if (p,sc,egs) in model.psegso:
            if model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
                return (optmodel.vEleEnergyOutflows[p,sc,n,egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n] <= 1.0
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eIncompatibilityEleChargeOutflows', Constraint(optmodel.psnegs, rule=eIncompatibilityEleChargeOutflows, doc='incompatibility between charge and outflows use [p.u.]'))

    # def eIncompatibilityHydChargeOutflows(optmodel, p,sc,n, hs):
    #     if (p,sc,hs) in model.pseso:
    #         if model.Par['pMaxCharge2ndBlock'][hs][p,sc,n]:
    #             return (optmodel.vHydEnergyOutflows[p,sc,n,hs] + optmodel.vHydTotalCharge2ndBlock[p,sc,n,hs]) / model.Par['pHydMaxCharge2ndBlock'][hs][p,sc,n] <= 1.0
    #         else:
    #             return Constraint.Skip
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eIncompatibilityHydChargeOutflows', Constraint(optmodel.psnhgs, rule=eIncompatibilityHydChargeOutflows, doc='incompatibility between charge and outflows use [p.u.]'))

    print('--- Declaring the incompatibility between charge and outflows use:     {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Logical relation between commitment, startup and shutdown status of a committed unit (all except the VRES units) [p.u.]
    def eEleCommitmentStartupShutdown(optmodel, p,sc,n,egt):
        if (model.Par['pEleMinPower'][egt][p,sc,n] or model.Par['pEleGenConstantTerm'][egt] or model.Par['pOptIndBinGenMinTime'] == 1) and egt not in model.egs:
            if n == model.n.first():
                return optmodel.vEleGenCommitment[p,sc,n,egt] - model.Par['pEleInitialUC'][p,sc,egt]                 == optmodel.vEleGenStartUp[p,sc,n,egt] - optmodel.vEleGenShutDown[p,sc,n,egt]
            else:
                return optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenCommitment[p,sc,model.n.prev(n),egt] == optmodel.vEleGenStartUp[p,sc,n,egt] - optmodel.vEleGenShutDown[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleCommitmentStartupShutdown', Constraint(optmodel.psnegt, rule=eEleCommitmentStartupShutdown, doc='Electricity relation among commitment startup and shutdown'))

    def eHydCommitmentStartupShutdown(optmodel, p,sc,n,hgt):
        if (model.Par['pHydMinPower'][hgt][p,sc,n] or model.Par['pHydGenConstantTerm'][hgt] or model.Par['pOptIndBinGenMinTime'] == 1) and hgt not in model.hgs:
            if n == model.n.first():
                return optmodel.vHydGenCommitment[p,sc,n,hgt] - model.Par['pHydInitialUC'][p,sc,hgt]                 == optmodel.vHydGenStartUp[p,sc,n,hgt] - optmodel.vHydGenShutDown[p,sc,n,hgt]
            else:
                return optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenCommitment[p,sc,model.n.prev(n),hgt] == optmodel.vHydGenStartUp[p,sc,n,hgt] - optmodel.vHydGenShutDown[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydCommitmentStartupShutdown', Constraint(optmodel.psnhgt, rule=eHydCommitmentStartupShutdown, doc='Hydrogen relation among commitment startup and shutdown'))

    print('--- Declaring the logical relation in the unit commitment:             {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Maximum ramp up and ramp down for the second block of a non-renewable (thermal, hydro) unit [p.u.]
    def eEleMaxRampUpOutput(optmodel, p,sc,n,egt):
        if model.Par['pEleGenRampUp'][egt] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleGenRampUp'][egt] < model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n]:
            if n == model.n.first():
                return (- max(model.Par['pEleSystemOutput'] - model.Par['pEleMinPower'][egt][p,sc,n],0.0) + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egt]                      + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpOutput', Constraint(optmodel.psnegt, rule=eEleMaxRampUpOutput, doc='maximum ramp up   [p.u.]'))

    def eEleMaxRampDwOutput(optmodel, p,sc,n,egt):
        if model.Par['pEleGenRampDown'][egt] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleGenRampDw'][egt] < model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n]:
            if n == model.n.first():
                return (- max(model.Par['pEleSystemOutput'] - model.Par['pEleMinPower'][egt][p,sc,n],0.0) + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egt] >= - model.Par['pEleInitialUC'][p,sc,egt]                 + optmodel.vEleGenShutDown[p,sc,n,egt]
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egt]                      + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egt] >= - optmodel.vEleGenCommitment[p,sc,model.n.prev(n),egt] + optmodel.vEleGenShutDown[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwOutput', Constraint(optmodel.psnegt, rule=eEleMaxRampDwOutput, doc='maximum ramp down [p.u.]'))

    print('--- Declaring the maximum ramp up and ramp down:                       {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Maximum ramp down and ramp up for the charge of an ESS [p.u.]
    def eEleMaxRampUpCharge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampUp'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                               optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] >= - 1.0
            else:
                return (- optmodel.vEleTotalCharge2ndBlock[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpCharge', Constraint(optmodel.psnegs, rule=eEleMaxRampUpCharge, doc='maximum ramp up   charge [p.u.]'))

    def eEleMaxRampDwCharge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampDown'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                             + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] <=   1.0
            else:
                return (- optmodel.vEleTotalCharge2ndBlock[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwCharge', Constraint(optmodel.psnegs, rule=eEleMaxRampDwCharge, doc='maximum ramp down charge [p.u.]'))

    def eEleMaxRampUpDischarge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampUp'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                               optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] <=   1.0
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpDischarge', Constraint(optmodel.psnegs, rule=eEleMaxRampUpDischarge, doc='maximum ramp up   discharge [p.u.]'))

    def eEleMaxRampDwDischarge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampDown'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                               optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] >= - 1.0
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwDischarge', Constraint(optmodel.psnegs, rule=eEleMaxRampDwDischarge, doc='maximum ramp down discharge [p.u.]'))

    print('--- Declaring the maximum ramp down and ramp up for the charge:        {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # maximum ramp up and ramp down for the charge of an H2 producer [p.u.]
    def eHydMaxRampUpOutput(optmodel, p,sc,n,hgt):
        if model.Par['pHydGenRampUp'][hgt] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                               optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgt] <=   optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
            else:
                return (- optmodel.vHydTotalOutput2ndBlock[p,sc,model.n.prev(n),hgt] + optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgt] <=   optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampUpOutput', Constraint(optmodel.psnhgt, rule=eHydMaxRampUpOutput, doc='maximum ramp up   output [p.u.]'))

    def eHydMaxRampDwOutput(optmodel, p,sc,n,hgt):
        if model.Par['pHydGenRampDown'][hgt] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                               optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgt] >= - model.Par['pHydInitialUC'][p,sc,hgt]                 + optmodel.vHydGenShutDown[p,sc,n,hgt]
            else:
                return (- optmodel.vHydTotalOutput2ndBlock[p,sc,model.n.prev(n),hgt] + optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgt] >= - optmodel.vHydGenCommitment[p,sc,model.n.prev(n),hgt] + optmodel.vHydGenShutDown[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampDwOutput', Constraint(optmodel.psnhgt, rule=eHydMaxRampDwOutput, doc='maximum ramp down output [p.u.]'))

    print('--- Declaring the maximum ramp up and ramp down for the H2 output:     {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # maximum ramp up and ramp down for the charge of an H2 ESS [p.u.]
    def eHydMaxRampUpCharge(optmodel, p,sc,n,hgs):
        if model.Par['pHydGenRampUp'][hgs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                               optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgs] >= - 1.0
            else:
                return (- optmodel.vHydTotalCharge2ndBlock[p,sc,model.n.prev(n),hgs] + optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampUpCharge', Constraint(optmodel.psnhgs, rule=eHydMaxRampUpCharge, doc='maximum ramp up   charge [p.u.]'))

    def eHydMaxRampDwCharge(optmodel, p,sc,n,hgs):
        if model.Par['pHydGenRampDown'][hgs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                               optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgs] <=   1.0
            else:
                return (- optmodel.vHydTotalCharge2ndBlock[p,sc,model.n.prev(n),hgs] + optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampDwCharge', Constraint(optmodel.psnhgs, rule=eHydMaxRampDwCharge, doc='maximum ramp down charge [p.u.]'))

    print('--- Declaring the maximum ramp up and ramp down for the H2 charge:     {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # maximum ramp up and ramp down for the outflows of an H2 ESS [p.u.]
    def eHydMaxRampUpOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydGenRampUp'][hgs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                          optmodel.vHydEnergyOutflows[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgs] <=   1.0
            else:
                return (- optmodel.vHydEnergyOutflows[p,sc,model.n.prev(n),hgs] + optmodel.vHydEnergyOutflows[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampUpOutflows', Constraint(optmodel.psnhgs, rule=eHydMaxRampUpOutflows, doc='maximum ramp up   outflows [p.u.]'))

    def eHydMaxRampDwOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydGenRampDown'][hgs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
            if n == model.n.first():
                return (                                                          optmodel.vHydEnergyOutflows[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgs] >= - 1.0
            else:
                return (- optmodel.vHydEnergyOutflows[p,sc,model.n.prev(n),hgs] + optmodel.vHydEnergyOutflows[p,sc,n,hgs]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampDown'][hgs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampDwOutflows', Constraint(optmodel.psnhgs, rule=eHydMaxRampDwOutflows, doc='maximum ramp down outflows [p.u.]'))

    print('--- Declaring the maximum ramp up and ramp down for the H2 outflows:   {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    # Minimum up time and down time of thermal unit [h]
    def eEleMinUpTime(optmodel, p,sc,n,egt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and (model.Par['pEleMinPower'][egt][p,sc,n] or model.Par['pEleGenConstantTerm'][egt]) and egt not in model.egs and model.n.ord(n) > (model.Par['pEleGenUpTime'][egt] - model.Par['pEleGenUpTimeZero'][egt]):
            return sum(optmodel.vEleGenStartUp[ p,sc,n2,egt] for n2 in list(model.n2)[int(max(model.n.ord(n)-model.Par['pEleGenUpTime'  ][egt], max(0,min(model.n.ord(n),(model.Par['pEleGenUpTime'  ][egt] - model.Par['pEleGenUpTimeZero'  ][egt])*(  model.Par['pEleInitialUC'][p,sc,egt]))))):model.n.ord(n)]) <=     optmodel.vEleGenCommitment[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinUpTime', Constraint(optmodel.psnegt, rule=eEleMinUpTime, doc='minimum up   time [h]'))

    def eEleMinDownTime(optmodel, p,sc,n,egt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and (model.Par['pEleMinPower'][egt][p,sc,n] or model.Par['pEleGenConstantTerm'][egt]) and egt not in model.egs and model.n.ord(n) > (model.Par['pEleGenDownTime'][egt] - model.Par['pEleGenDownTimeZero'][egt]):
            return sum(optmodel.vEleGenShutDown[p,sc,n2,egt] for n2 in list(model.n2)[int(max(model.n.ord(n)-model.Par['pEleGenDownTime'][egt], max(0,min(model.n.ord(n),(model.Par['pEleGenDownTime'][egt] - model.Par['pEleGenDownTimeZero'][egt])*(1-model.Par['pEleInitialUC'][p,sc,egt]))))):model.n.ord(n)]) <= 1 - optmodel.vEleGenCommitment[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinDownTime', Constraint(optmodel.psnegt, rule=eEleMinDownTime, doc='minimum down time [h]'))

    # Minimum up time and down time of an electrolyzer [h]
    def eHydMinUpTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenUpTime'][hgt] > 1 and model.n.ord(n) > (model.Par['pHydGenUpTime'][hgt] - model.Par['pHydGenUpTimeZero'][hgt]):
            return sum(optmodel.vHydGenStartUp[p,sc,n2,hgt] for n2 in list(model.n2)[int(max(model.n.ord(n)-model.Par['pHydGenUpTime'   ][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenUpTime'  ][hgt] - model.Par['pHydGenUpTimeZero'  ][hgt])*(  model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <=     optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinUpTime', Constraint(optmodel.psnhgt, rule=eHydMinUpTime, doc='minimum up   time [h]'))

    def eHydMinDownTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenDownTime'][hgt] > 1 and model.n.ord(n) > (model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt]):
            return sum(optmodel.vHydGenShutDown[p,sc,n2,hgt] for n2 in list(model.n2)[int(max(model.n.ord(n)-model.Par['pHydGenDownTime'][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt])*(1-model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <= 1 - optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinDownTime', Constraint(optmodel.psnhgt, rule=eHydMinDownTime, doc='minimum down time [h]'))

    print('--- Declaring the minimum up and down time:                            {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    def eEleMinEnergyStartUp(optmodel, p,sc,n,egs):
        if model.Par['pVarStartUp'][egs][p,sc,n] and egs in model.egv:
            if n != model.n.first() and model.Par['pVarStartUp'][egs][p,sc,model.n.prev(n)] < model.Par['pVarStartUp'][egs][p,sc,n]:
                return optmodel.vEleInventory[p,sc,model.n.prev(n),egs] >= 0.8 * model.Par['pEleMaxStorage'][egs][p,sc,n]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinEnergyStartUp', Constraint(optmodel.psnegs, rule=eEleMinEnergyStartUp, doc='minimum energy start up'))

    def eEleTotalMaxChargeConditioned(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] == 0.0 and model.Par['pEleGenFixedAvailability'][egs]:
            return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalMaxChargeConditioned', Constraint(optmodel.psneh, rule=eEleTotalMaxChargeConditioned, doc='total charge of an ESS unit [GW]'))

    print('--- Declaring the minimum energy start up and total max charge:        {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    def eElePeakHourValue(optmodel, p,sc,n,er,m,peak):
        if model.Par['pEleRetTariff'][er] and (n,m) in model.n2m:
            if peak == model.Peaks.first():
                return optmodel.vElePeak[p,sc,m,er,peak] >= optmodel.vEleBuy[p,sc,n,er]
            else:
                return optmodel.vElePeak[p,sc,m,er,peak] >= optmodel.vEleBuy[p,sc,n,er] - 1e2 * sum(optmodel.vElePeakHourInd[p,sc,n,er,peak2] for peak2 in model.Peaks if peak2 < peak)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourValue', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourValue, doc='peak hour selection'))

    def eElePeakHourInd_C1(optmodel, p,sc,n,er,m,peak):
        if model.Par['pEleRetTariff'][er] and (n,m) in model.n2m:
            return optmodel.vElePeak[p,sc,m,er,peak] >= optmodel.vEleBuy[p,sc,n,er] - 1e2 * (1 - optmodel.vElePeakHourInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C1', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C1, doc='peak hour indicator'))

    def eElePeakHourInd_C2(optmodel, p,sc,n,er,m,peak):
        if model.Par['pEleRetTariff'][er] and (n,m) in model.n2m:
            return optmodel.vElePeak[p,sc,m,er,peak] <= optmodel.vEleBuy[p,sc,n,er] + 1e2 * (1 - optmodel.vElePeakHourInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C2', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C2, doc='peak hour indicator'))

    def eElePeakNumberMonths(optmodel, m,peak):
        if sum(model.Par['pEleRetTariff'][er] for er in model.er) > 0:
            return sum(optmodel.vElePeakHourInd[p,sc,n,er,peak] for p,sc,n,er in model.psner if model.Par['pEleRetTariff'][er] and (n,m) in model.n2m) == 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakNumberMonths', Constraint(optmodel.moy, optmodel.Peaks, rule=eElePeakNumberMonths, doc='peak number of months'))

    print('--- Declaring the peak hour selection:                                 {} seconds'.format(round(time.time() - StartTime)))
    StartTime = time.time() # to compute elapsed time

    def eKirchhoff2ndLaw(optmodel, p,sc,n,ni,nf,cc):
        if model.Par[('pOptIndBinSingleNode')] == 0 and model.Par['pEleNetInitialPeriod'][ni,nf,cc] <= model.Par['pParEconomicBaseYear'] and model.Par['pEleNetFinalPeriod'][ni,nf,cc] >= model.Par['pParEconomicBaseYear'] and (ni,nf,cc) in model.elea:
            return optmodel.vEleNetFlow[p,sc,n,ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] - (optmodel.vEleNetTheta[p,sc,n,ni] - optmodel.vEleNetTheta[p,sc,n,nf]) / model.Par['pEleNetReactance'][ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] * 0.1 == 0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eKirchhoff2ndLaw', Constraint(optmodel.psnela, rule=eKirchhoff2ndLaw, doc='Kirchhoff 1st Law'))

    print('--- Declaring the Kirchhoff 2nd Law:                                   {} seconds'.format(round(time.time() - StartTime)))

    return model