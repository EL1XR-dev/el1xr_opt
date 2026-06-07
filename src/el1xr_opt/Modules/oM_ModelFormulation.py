# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import time          # count clock time
from   pyomo.environ     import Constraint, Objective, minimize
from   collections       import defaultdict
from  .utils.oM_Utils    import log_time
from  .oM_HeatSector     import heat_electricity_load, heat_to_power_output

def create_objective_function(model, optmodel, indlog):
    # this function declares constraints
    StartTime = time.time() # to compute elapsed time

    print('-- Declaring objective function')

    # tolerance to consider avoid division by 0
    # pEpsilon = 1e-6

    # defining the objective function
    def eTotalSCost(optmodel):
        return optmodel.vTotalSCost
    optmodel.__setattr__('eTotalSCost', Objective(rule=eTotalSCost, sense=minimize, doc='Total system cost [kEUR]'))

    def eTotalTCost(optmodel):
        # vTotalICost is the investment cost from the capacity-sizing layer
        # (oM_Investment.create_investment); it is zero when there are no candidate
        # units. It is already period-weighted by pDiscountFactor there, so it is in
        # the same currency and on the same discounted footing as the operating
        # terms summed below.
        # the heat operating cost is already period-discounted (oM_HeatSector) and is
        # zero when the case has no heat sector.
        heat_cost = getattr(optmodel, 'HeatOperatingCost', 0.0)
        return (optmodel.vTotalSCost == optmodel.vTotalICost + heat_cost + sum(optmodel.Par['pDiscountFactor'][idx[0]] * (optmodel.vTotalCComponent[idx] - optmodel.vTotalRComponent[idx]) for idx in model.ps))
    optmodel.__setattr__('eTotalTCost', Constraint(rule=eTotalTCost, doc='Total system cost [kEUR]'))

    # Cost / revenue components of the objective, summed from a registry so a new
    # cost-bearing feature registers its term instead of editing these rules. The
    # registry is seeded with the built-in terms in their original order, so the
    # aggregation is identical to the previous hard-coded sum.
    from .oM_Features import seed_objective_registry, aggregate_terms
    seed_objective_registry(model)

    def eTotalCComponent(optmodel, p,sc):
        return optmodel.vTotalCComponent[p,sc] == aggregate_terms(model, optmodel, p, sc, model._cost_terms)
    optmodel.__setattr__('eTotalCComponent', Constraint(optmodel.ps, rule=eTotalCComponent, doc='Total cost components [kEUR]'))

    def eTotalRComponent(optmodel, p,sc):
        return optmodel.vTotalRComponent[p,sc] == aggregate_terms(model, optmodel, p, sc, model._revenue_terms)
    optmodel.__setattr__('eTotalRComponent', Constraint(optmodel.ps, rule=eTotalRComponent, doc='Total revenue components [kEUR]'))

    log_time('--- Declaring the totals components of the ObjFunc:', StartTime, ind_log=indlog)

    return model

def create_objective_function_components(model, optmodel, indlog):
    #
    StartTime = time.time() # to compute elapsed time

    #%% Total electricity grid usage cost [M€]
    def eEleNetGridUsageCost(optmodel, p,sc):
        return optmodel.vTotalEleNCost[p,sc] == optmodel.vTotalElePeakCost[p,sc] + optmodel.vTotalEleNetUseVarCost[p,sc] + optmodel.vTotalEleNetUseFixCost[p,sc]
    optmodel.__setattr__('eNetGridUsageCost', Constraint(optmodel.ps, rule=eEleNetGridUsageCost, doc='Total electricity grid usage cost [kEUR]'))

    # Total electricity peak costs
    def eTotalElePeakCost(optmodel, p,sc):
        if model.Par['pParNumberPowerPeaks'] == 0:
            return (optmodel.vTotalElePeakCost[p,sc] == sum(model.Par['pEleRetPowerTariff'][er] * model.factor1 * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
        else:
            return (optmodel.vTotalElePeakCost[p,sc] == sum(model.Par['pEleRetPowerTariff'][er] * model.factor1 * sum(optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] for peak in model.Peaks for m in model.moy) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er) / len(model.Peaks))
    optmodel.__setattr__('eTotalElePeakCost', Constraint(optmodel.ps, rule=eTotalElePeakCost, doc='Total electricity peak cost [kEUR]'))

    # Total electricity net usage costs
    def eTotalEleNetUseVarCost(optmodel, p,sc):
        return (optmodel.vTotalEleNetUseVarCost[p,sc] == sum(sum(model.Par['pEleRetOverforingsavgift'][er] * model.factor1 * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eTotalEleNetUseVarCost', Constraint(optmodel.ps, rule=eTotalEleNetUseVarCost, doc='Total electricity net usage cost [kEUR]'))

    # Total electricity capacity tariff costs
    def eTotalEleNetUseFixCost(optmodel, p,sc):
        return (optmodel.vTotalEleNetUseFixCost[p,sc] == sum(model.Par['pEleRetFastavgift'][er] * model.factor1 * sum(1 for m in model.moy) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eTotalEleNetUseFixCost', Constraint(optmodel.ps, rule=eTotalEleNetUseFixCost, doc='Total electricity capacity tariff cost [kEUR]'))

    #%% Total electricity market costs
    def eEleMarketCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleMCost[p,sc,n] == optmodel.vTotalEleMrkDACost[p,sc,n] + optmodel.vTotalEleMrkPPACost[p,sc,n])
    optmodel.__setattr__('eEleMarketCost', Constraint(optmodel.psn, rule=eEleMarketCost, doc='Total electricity market costs [kEUR]'))

    def eEleMarketDayAheadCost(optmodel, p,sc,n):
        return optmodel.vTotalEleMrkDACost[p,sc,n] == sum((model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetPaslag'][er]) * (optmodel.vEleBuy[p,sc,n,er]) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
    optmodel.__setattr__('eEleMarketDayAheadCost', Constraint(optmodel.psn, rule=eEleMarketDayAheadCost, doc='Total electricity trade cost [kEUR]'))

    #%% Total electricity market revenues
    def eEleMarketRevenue(optmodel, p,sc,n):
        return (optmodel.vTotalEleMRev[p,sc,n] == optmodel.vTotalEleMrkDARev[p,sc,n] + optmodel.vTotalEleMrkPPARev[p,sc,n] + optmodel.vTotalEleMrkFrqRev[p,sc,n])
    optmodel.__setattr__('eEleMarketRevenue', Constraint(optmodel.psn, rule=eEleMarketRevenue, doc='Total electricity market revenues [kEUR]'))

    def eEleMarketDayAheadRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleMrkDARev[p,sc,n] == sum(model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] * (optmodel.vEleSell[p,sc,n,er]) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
    optmodel.__setattr__('eEleMarketDayAheadRevenue', Constraint(optmodel.psn, rule=eEleMarketDayAheadRevenue, doc='Total electricity market day-ahead revenues [kEUR]'))

    def eEleMarketFrequencyRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleMrkFrqRev[p,sc,n] == optmodel.vTotalEleFCRDUpRev[p,sc,n] + optmodel.vTotalEleFCRDDwRev[p,sc,n] + optmodel.vTotalEleFCRNRev[p,sc,n]
    optmodel.__setattr__('eEleMarketFrequencyRevenue', Constraint(optmodel.psn, rule=eEleMarketFrequencyRevenue, doc='Total electricity market frequency revenues [kEUR]'))

    def eEleMarketFCRDUpRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleFCRDUpRev[p,sc,n] == sum((model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] * model.factor1 * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egnr]) for egnr in model.egnr)
    optmodel.__setattr__('eEleMarketFCRDUpRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRDUpRevenue, doc='Total electricity market FCR-D upwards revenues [kEUR]'))

    def eEleMarketFCRDDwRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleFCRDDwRev[p,sc,n] == sum((model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] * model.factor1 * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egnr]) for egnr in model.egnr)
    optmodel.__setattr__('eEleMarketFCRDDwRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRDDwRevenue, doc='Total electricity market FCR-D downwards revenues [kEUR]'))

    def eEleMarketFCRNRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleFCRNRev[p,sc,n] == sum(((model.Par['pOperatingReservePrice_FCRN_Up'][p,sc,n] + model.Par['pOperatingReservePrice_FCRN_Down'][p,sc,n]) / 2 * model.factor1 * optmodel.vEleFreqContReserveNorBid[p,sc,n,egnr]) for egnr in model.egnr)
    optmodel.__setattr__('eEleMarketFCRNRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRNRevenue, doc='Total electricity market FCR-N revenues [kEUR]'))

    #%% Total hydrogen market costs
    def eHydMarketCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydMCost[p,sc,n] == optmodel.vTotalHydMrkPPACost[p,sc,n])
    optmodel.__setattr__('eHydMarketCost', Constraint(optmodel.psn, rule=eHydMarketCost, doc='Total hydrogen market costs [kEUR]'))

    def eHydMarketDayAheadCost(optmodel, p,sc,n):
        return optmodel.vTotalHydMrkPPACost[p,sc,n] == sum(model.Par['pVarEnergyCost'][hr][p,sc,n] * optmodel.vHydBuy[p,sc,n,hr] for hr in model.hr)
    optmodel.__setattr__('eTotalHydTradeCost', Constraint(optmodel.psn, rule=eHydMarketDayAheadCost, doc='Total hydrogen trade cost [kEUR]'))

    #%% Total hydrogen market revenues
    def eHydMarketRevenue(optmodel, p,sc,n):
        return (optmodel.vTotalHydMRev[p,sc,n] == optmodel.vTotalHydMrkPPARev[p,sc,n])
    optmodel.__setattr__('eHydMarketRevenue', Constraint(optmodel.psn, rule=eHydMarketRevenue, doc='Total hydrogen market revenues [kEUR]'))

    def eHydMarketDayAheadRevenue(optmodel, p,sc,n):
        return optmodel.vTotalHydMrkPPARev[p,sc,n] == sum(model.Par['pVarEnergyPrice'][hr][p,sc,n] * optmodel.vHydSell[p,sc,n,hr] for hr in model.hr)
    optmodel.__setattr__('eHydMarketDayAheadRevenue', Constraint(optmodel.psn, rule=eHydMarketDayAheadRevenue, doc='Total hydrogen market day-ahead revenues [kEUR]'))

    #%% Total electricity taxes costs
    def eEleTaxCost(optmodel, p,sc):
        return (optmodel.vTotalEleXCost[p,sc] == optmodel.vTotalEleEnergyTaxCost[p,sc])
    optmodel.__setattr__('eEleTaxCost', Constraint(optmodel.ps, rule=eEleTaxCost, doc='Total electricity taxes costs [kEUR]'))

    # VAT on electricity taxes costs
    def eEleTaxEnergyCost(optmodel, p,sc):
        return (optmodel.vTotalEleEnergyTaxCost[p,sc] == sum(model.Par['pEleRetEnergyTax'][er] * model.factor1 * sum(optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eEleTaxEnergyCost', Constraint(optmodel.ps, rule=eEleTaxEnergyCost, doc='Total electricity taxes costs [kEUR]'))

    def eEleTaxRevenue(optmodel, p,sc):
        return (optmodel.vTotalEleXRev[p,sc] == optmodel.vTotalEleISRev[p,sc])
    optmodel.__setattr__('eEleTaxRevenue', Constraint(optmodel.ps, rule=eEleTaxRevenue, doc='Total electricity taxes revenues [kEUR]'))

    # Incentives on electricity taxes revenues
    def eEleTaxISRevenue(optmodel, p,sc):
        return (optmodel.vTotalEleISRev[p,sc] == sum(model.Par['pEleRetIncentive'][er] * model.factor1 * sum(optmodel.vEleExport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) for er in model.er))
    optmodel.__setattr__('eEleTaxISRevenue', Constraint(optmodel.ps, rule=eEleTaxISRevenue, doc='Total electricity taxes revenues [kEUR]'))

    #%% Total electricity operation and maintenance costs
    def eEleOpMaintCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleOCost[p,sc,n] == sum(optmodel.__getattribute__(f'vTotal{eng}GCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}ECost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}CCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}RCost')[p,sc,n] for eng in ['Ele']))
    optmodel.__setattr__('eEleOpMaintCost', Constraint(optmodel.psn, rule=eEleOpMaintCost, doc='Total electricity operation and maintenance costs [kEUR]'))

    # Electricity generation operation cost [M€]
    def eTotalEleGCost(optmodel, p,sc,n):
        return optmodel.vTotalEleGCost[p,sc,n] == (sum(model.Par['pEleGenLinearVarCost'  ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ) +
                                                   sum(model.Par['pEleGenConstantVarCost'][egt] *       optmodel.vEleGenCommitment     [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pEleGenStartUpCost'    ][egt] *       optmodel.vEleGenStartUp        [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pEleGenShutDownCost'   ][egt] *       optmodel.vEleGenShutDown       [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pEleGenOMVariableCost' ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ))
    optmodel.__setattr__('eTotalEleGCost', Constraint(optmodel.psn, rule=eTotalEleGCost, doc='Total electricity generation cost [kEUR]'))

    # Electricity generation emission cost [M€]
    def eTotalEleECost(optmodel, p,sc,n):
        return optmodel.vTotalEleECost[p,sc,n] == sum(model.Par['pGenCO2EmissionCost'][egt] * optmodel.vEleTotalOutput[p,sc,n,egt] for egt in model.egt)
    optmodel.__setattr__('eTotalECost', Constraint(optmodel.psn, rule=eTotalEleECost, doc='Total emission cost [kEUR]'))

    # Electricity consumption operation cost [M€]
    def eTotalEleCCost(optmodel, p,sc,n):
        return optmodel.vTotalEleCCost[p,sc,n] == sum(model.Par['pEleGenLinearTerm'][egs] * optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs)
    optmodel.__setattr__('eTotalEleCCost', Constraint(optmodel.psn, rule=eTotalEleCCost, doc='Total consumption cost in electricity units [kEUR]'))

    # Electricity storage degradation cost [M€]
    def eTotalEleDCost(optmodel, p,sc,d):
        return optmodel.vTotalEleDCost[p,sc,d] == sum(model.Par['pEleGenDoDC1'][egs] * optmodel.vEleInventoryDoDS1Day[p,sc,d,egs] + model.Par['pEleGenDoDC2'][egs] * optmodel.vEleInventoryDoDS2Day[p,sc,d,egs] + model.Par['pEleGenDoDC3'][egs] * optmodel.vEleInventoryDoDS3Day[p,sc,d,egs] for egs in model.egs)
    optmodel.__setattr__('eTotalEleDCost', Constraint(optmodel.psd, rule=eTotalEleDCost, doc='Total degradation cost in electricity storage units [kEUR]'))

    # Electricity reliability cost [M€]
    def eTotalEleRCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleRCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pParENSCost'] * optmodel.vENS[p,sc,n,ed]) for ed in model.ed))
    optmodel.__setattr__('eTotalEleRCost', Constraint(optmodel.psn, rule=eTotalEleRCost, doc='Total reliability cost in electricity consumers [kEUR]'))

    #%% Total hydrogen operation and maintenance costs
    def eHydOpMaintCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydOCost[p,sc,n] == sum(optmodel.__getattribute__(f'vTotal{eng}GCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}CCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}RCost')[p,sc,n] for eng in ['Hyd']))
    optmodel.__setattr__('eHydOpMaintCost', Constraint(optmodel.psn, rule=eHydOpMaintCost, doc='Total hydrogen operation and maintenance costs [kEUR]'))

    # Hydrogen generation operation cost [M€]
    def eTotalHydGCost(optmodel, p,sc,n):
        return optmodel.vTotalHydGCost[p,sc,n] == (sum(model.Par['pHydGenLinearVarCost'  ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ) +
                                                   sum(model.Par['pHydGenConstantVarCost'][hgt] *       optmodel.vHydGenCommitment     [p,sc,n,hgt] for hgt in model.hgt) +
                                                   sum(model.Par['pHydGenStartUpCost'    ][hgt] *       optmodel.vHydGenStartUp        [p,sc,n,hgt] for hgt in model.hgt) +
                                                   sum(model.Par['pHydGenShutDownCost'   ][hgt] *       optmodel.vHydGenShutDown       [p,sc,n,hgt] for hgt in model.hgt) -
                                                   sum(model.Par['pHydGenOMVariableCost' ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ))
    optmodel.__setattr__('eTotalHydGCost', Constraint(optmodel.psn, rule=eTotalHydGCost, doc='Total hydrogen generation cost [kEUR]'))

    # Hydrogen consumption operation cost [M€]
    def eTotalHydCCost(optmodel, p,sc,n):
        return optmodel.vTotalHydCCost[p,sc,n] == sum(model.Par['pHydGenLinearTerm'][hgs] * optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs)
    optmodel.__setattr__('eTotalHydCCost', Constraint(optmodel.psn, rule=eTotalHydCCost, doc='Total consumption cost in hydrogen units [kEUR]'))

    # Hydrogen reliability cost [M€]
    def eTotalHydRCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydRCost[p,sc,n] == sum(model.Par['pDuration'][p,sc,n] * (model.Par['pParHNSCost'] * optmodel.vHNS[p,sc,n,hd]) for hd in model.hd))
    optmodel.__setattr__('eTotalHydRCost', Constraint(optmodel.psn, rule=eTotalHydRCost, doc='Total reliability cost in hydrogen consumers [kEUR]'))

    log_time('--- Declaring the ObjFunc components:', StartTime, ind_log=indlog)

    return model

def create_constraints(model, optmodel, indlog):
    # this function declares constraints
    StartTime = time.time()  # to compute elapsed time

    # balance formulation gate: the main model is built with the nodal balance.
    # Selecting the arc/asset (block-angular) form is recognised but not yet wired
    # in-core, so it fails clearly here instead of silently building a nodal model.
    from .oM_Features import require_balance_mode_implemented
    require_balance_mode_implemented(model)

    # Materialise the ordered load-level list once. Several constraint rules slice
    # it by position (using model.n.ord(n)); rebuilding the list on every rule
    # call made constraint construction scale quadratically with the number of
    # load levels. Building it once here keeps the slicing identical but removes
    # that per-call cost.
    n2_list = list(model.n2)

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
    eg2r = defaultdict(list)
    for er,eg in model.r2eg:
        eg2r[er].append(eg)
    hg2r = defaultdict(list)
    for hr,hg in model.r2hg:
        hg2r[hr].append(hg)
    egs2r = defaultdict(list)
    for er,egs in model.r2eg:
        if (er,egs) in model.r2eg:
            egs2r[er].append(egs)
    hgs2r = defaultdict(list)
    for hr,hgs in model.r2hg:
        if (hr,hgs) in model.r2hg:
            hgs2r[hr].append(hgs)
    egt2n = defaultdict(list)
    for nd,egt in model.nd*model.egt:
        if (nd,egt) in model.n2eg:
            egt2n[nd].append(egt)
    hgt2n = defaultdict(list)
    for nd,hgt in model.nd*model.hgt:
        if (nd,hgt) in model.n2hg:
            hgt2n[nd].append(hgt)
    eg2n = defaultdict(list)
    for nd,eg in model.nd*model.eg:
        if (nd,eg) in model.n2eg:
            eg2n[nd].append(eg)
    hg2n = defaultdict(list)
    for nd,hg in model.nd*model.hg:
        if (nd,hg) in model.n2hg:
            hg2n[nd].append(hg)
    egs2n = defaultdict(list)
    for nd,egs in model.nd*model.egs:
        if (nd,egs) in model.n2eg:
            egs2n[nd].append(egs)
    hgs2n = defaultdict(list)
    for nd,hgs in model.nd*model.hgs:
        if (nd,hgs) in model.n2hg:
            hgs2n[nd].append(hgs)

    #%% Constraints
    # Energy-community sharing terms enter the retail balance like buy/sell but
    # internal to the community; the term is absent unless the community layer is
    # on, so existing cases build an identical constraint.
    community_on = bool(model.Par.get('pOptIndBinCommunity', 0))

    def eEleRetNodeBalance(optmodel, p,sc,n,er):
        nd = model.Par['pEleRetNode'][er]
        if sum(1 for eg in eg2n[nd]) + sum(1 for egs in egs2n[nd]) + sum(1 for nf, cc in lout[nd]) + sum(1 for ni, cc in lin[nd]):
            share = (optmodel.vEleShareIn[p,sc,n,er] - optmodel.vEleShareOut[p,sc,n,er]) if community_on else 0.0
            return (sum(optmodel.vEleTotalOutput[p,sc,n,egr] for egr in model.egr  if (er,egr) in model.r2eg) + sum(optmodel.vEleGenCommitment[p,sc,n,egt] * model.Par['pEleMinPower'][egt][p,sc,n] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] for egt in model.egt if (er,egt) in model.r2eg) + sum(optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg)
                    - sum(optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg) - sum(optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] for e2h in model.e2h if (er,e2h) in model.r2hg)
                    + optmodel.vEleBuy[p,sc,n,er] - optmodel.vEleSell[p,sc,n,er] + share == sum(optmodel.vEleDemand[p,sc,n,ed] - optmodel.vENS[p,sc,n,ed] for ed in model.ed if (er,ed) in model.r2ed))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRetNodeBalance', Constraint(optmodel.psner, rule=eEleRetNodeBalance, doc='Electricity balance in nodes [kWh]'))

    # Maximum electricity buys
    def eEleRetMaxBuy(optmodel, p,sc,n,er):
        if model.Par['pEleRetMaxBuy'][er] > 0:
            return optmodel.vEleBuy[p,sc,n,er] <= model.Par['pEleRetMaxBuy'][er]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRetMaxBuy', Constraint(optmodel.psner, rule=eEleRetMaxBuy, doc='Maximum electricity buys [kWh]'))

    # def eEleBuyComposition(optmodel, p,sc,n,er):
    #     if model.Par['pEleRetMaxBuy'][er] > 0:
    #         return optmodel.vEleBuy[p,sc,n,er] == sum(optmodel.vEleDemand[p,sc,n,ed] for ed in model.ed if (er,ed) in model.r2ed) + sum(optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg)
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleBuyComposition', Constraint(optmodel.psner, rule=eEleBuyComposition, doc='Electricity buy composition [kWh]'))

    # Maximum electricity sells
    def eEleRetMaxSell(optmodel, p,sc,n,er):
        if model.Par['pEleRetMaxSell'][er] > 0:
            return optmodel.vEleSell[p,sc,n,er] <= model.Par['pEleRetMaxSell'][er]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRetMaxSell', Constraint(optmodel.psner, rule=eEleRetMaxSell, doc='Maximum electricity sells [kWh]'))

    # def eEleSellComposition(optmodel, p,sc,n,er):
    #     if model.Par['pEleRetMaxSell'][er] > 0:
    #         return optmodel.vEleSell[p,sc,n,er] == sum(optmodel.vEleTotalOutput[p,sc,n,egt] for egt in model.egt if (er,egt) in model.r2eg) + sum(optmodel.vEleTotalOutput[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg) + sum(optmodel.vEleTotalOutput[p,sc,n,egr] for egr in model.egr if (er,egr) in model.r2eg)
    #         # return optmodel.vEleSell[p,sc,n,er] == sum(optmodel.vEleTotalOutput[p,sc,n,egt] for egt in model.egt if (er,egt) in model.r2eg) + sum(optmodel.vEleTotalOutput[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg)
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleSellComposition', Constraint(optmodel.psner, rule=eEleSellComposition, doc='Electricity sell composition [kWh]'))

    # print if the max buy or sell is greater than 0
    if len(optmodel.eEleRetMaxBuy) > 0 or len(optmodel.eEleRetMaxSell) > 0:
        log_time('--- Declaring the maximum electricity buys and sells:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Maximum hydrogen buys
    def eHydRetMaxBuy(optmodel, p,sc,n,hr):
        if model.Par['pHydRetMaxBuy'][hr] > 0:
            return optmodel.vHydBuy[p,sc,n,hr] <= model.Par['pHydRetMaxBuy'][hr]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydRetMaxBuy', Constraint(optmodel.psnhr, rule=eHydRetMaxBuy, doc='Maximum hydrogen buys [kgH2]'))

    def eHydBuyComposition(optmodel, p,sc,n,hr):
        if model.Par['pHydRetMaxBuy'][hr] > 0:
            return optmodel.vHydBuy[p,sc,n,hr] == sum(optmodel.vHydImport[p,sc,n,nd] for nd in model.nd if (nd,hr) in model.n2hr)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydBuyComposition', Constraint(optmodel.psnhr, rule=eHydBuyComposition, doc='Hydrogen buy composition [kgH2]'))

    # Maximum hydrogen sells
    def eHydRetMaxSell(optmodel, p,sc,n,hr):
        if model.Par['pHydRetMaxSell'][hr] > 0:
            return optmodel.vHydSell[p,sc,n,hr] <= model.Par['pHydRetMaxSell'][hr]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydRetMaxSell', Constraint(optmodel.psnhr, rule=eHydRetMaxSell, doc='Maximum hydrogen sells [kgH2]'))

    def eHydSellComposition(optmodel, p,sc,n,hr):
        if model.Par['pHydRetMaxSell'][hr] > 0:
            return optmodel.vHydSell[p,sc,n,hr] == sum(optmodel.vHydExport[p,sc,n,nd] for nd in model.nd if (nd,hr) in model.n2hr)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydSellComposition', Constraint(optmodel.psnhr, rule=eHydSellComposition, doc='Hydrogen sell composition [kgH2]'))

    # print if the max buy or sell is greater than 0
    if len(optmodel.eHydRetMaxBuy) > 0 or len(optmodel.eHydRetMaxSell) > 0:
        log_time('--- Declaring the maximum hydrogen buys and sells:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    #%% shifting demand constraints
    # electricity demand balance: ensure the total electricity consumed before and after the shift is the same within the shift time
    def eEleDemandShiftBalance(optmodel, p,sc,n,ed):
        if model.Par['pEleDemFlexible'][ed] == 1.0 and model.Par['pEleDemShiftedSteps'][ed]:
            if model.n.ord(n) % model.Par['pEleDemShiftedSteps'][ed] == 0:
                return sum(optmodel.vEleDemand[p,sc,n2,ed] for n2 in n2_list[model.n.ord(n) - model.Par['pEleDemShiftedSteps'][ed]:model.n.ord(n)])  == sum(model.Par['pVarMaxDemand'][ed][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pEleDemShiftedSteps'][ed]:model.n.ord(n)])
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

    # print the constraints object len is greater than 0
    if len(optmodel.eEleDemandShiftBalance) > 0 or len(optmodel.eEleDemandShifted) > 0:
        log_time('--- Declaring the electricity demand shift constraints:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # electrical energy conservation or balance
    # heat-sector coupling at the node: heat pumps draw electricity (a load) and
    # heat-to-power units inject electricity. Both are 0 when there is no heat case.
    _htp = set(getattr(model, "htp", []) or [])
    _htp_at = defaultdict(list)
    for (_nd, _g) in getattr(model, "n2htg", []):
        if _g in _htp:
            _htp_at[_nd].append(_g)
    _htw_at = defaultdict(list)
    for (_nd, _w) in getattr(model, "n2htw", []):
        _htw_at[_nd].append(_w)

    def eEleBalance(optmodel, p,sc,n,nd):
        if sum(1 for eg in eg2n[nd]) + sum(1 for egs in egs2n[nd]) + sum(1 for nf, cc in lout[nd]) + sum(1 for ni, cc in lin[nd]):
            return (sum(optmodel.vEleTotalOutput[p,sc,n,eg] for eg in model.eg  if (nd,eg) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs if (nd,egs) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,e2h] for e2h in model.e2h if (nd,e2h) in model.n2hg)
                  - sum(optmodel.vEleNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in lout[nd]) + sum(optmodel.vEleNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in lin[nd]) + optmodel.vEleImport[p,sc,n,nd] - optmodel.vEleExport[p,sc,n,nd]
                  + heat_to_power_output(optmodel, _htw_at[nd], p, sc, n) - heat_electricity_load(optmodel, _htp_at[nd], p, sc, n)
                  == sum(optmodel.vEleDemand[p,sc,n,ed] - optmodel.vENS[p,sc,n,ed] for ed in model.ed if (nd,ed) in model.n2ed))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleBalance', Constraint(optmodel.psnnd, rule=eEleBalance, doc='Electricity balance in the DA market'))

    # hydrogen energy conservation or balance
    def eHydBalance(optmodel, p,sc,n,nd):
        if sum(1 for hg in hg2n[nd]) + sum(1 for hgs in hgs2n[nd]) + sum(1 for nf, cc in hout[nd]) + sum(1 for ni, cc in hin[nd]):
            return (sum(optmodel.vHydTotalOutput[p,sc,n,hg] for hg in model.hg if (nd,hg) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs if (nd,hgs) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,h2e] for h2e in model.h2e if (nd,h2e) in model.n2g)
                  - sum(optmodel.vHydNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in hout[nd]) + sum(optmodel.vHydNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in hin[nd]) + optmodel.vHydImport[p,sc,n,nd] - optmodel.vHydExport[p,sc,n,nd] == sum(optmodel.vHydDemand[p,sc,n,hd] - optmodel.vHNS[p,sc,n,hd] for hd in model.hd if (nd,hd) in model.n2hd))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydBalance', Constraint(optmodel.psnnd, rule=eHydBalance, doc='Hydrogen balance in the DA market'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleBalance) > 0 or len(optmodel.eHydBalance) > 0:
        log_time('--- Declaring the energy balance constraints:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    #%%% Operating Reserves
    # FCR-D required
    def eEleFreqContReserveDisUpward(optmodel, p,sc,n):
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0):
            return sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) <= model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveDisUpward', Constraint(optmodel.psn, rule=eEleFreqContReserveDisUpward, doc='Frequency containment reserve - upward'))

    def eEleFreqContReserveDisDownward(optmodel, p,sc,n):
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0):
            return sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) <= model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveDisDownward', Constraint(optmodel.psn, rule=eEleFreqContReserveDisDownward, doc='Frequency containment reserve - downward'))

    def eEleFreqContReserveNor(optmodel, p,sc,n):
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRN'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRN'][egs] == 0):
            return sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRN'][egt] == 0) + sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRN'][egs] == 0) <= (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] + model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n]) / 2
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveNor', Constraint(optmodel.psn, rule=eEleFreqContReserveNor, doc='Frequency containment reserve - normal'))

    # The relation between the upward and downward bids and the provision of FCR-D reserves from an electric generator is defined as follows:
    def eEleRelationFreqDisUpBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egt] == 0:
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egt] == optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisUpBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqDisUpBid2Gen, doc='Relation FCR-D upward bid to generation'))

    def eEleRelationFreqDisDownBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egt] == 0:
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egt] == optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisDownBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqDisDownBid2Gen, doc='Relation FCR-D downward bid to generation'))

    def eEleRelationFreqNorUpBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egt] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] <= optmodel.vEleFreqContReserveNorUpGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorUpBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqNorUpBid2Gen, doc='Relation FCR-N upward bid to generation'))

    def eEleRelationFreqNorDownBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egt] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] <= optmodel.vEleFreqContReserveNorDownGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorDownBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqNorDownBid2Gen, doc='Relation FCR-N downward bid to generation'))

    # The relation between the upward and downward bids and the provision of FCR-D reserves from an electric storage system is defined as follows:
    def eEleRelationFreqDisUpBid2Stor(optmodel, p,sc,n,egs):
        if model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0:
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs] == optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisUpBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqDisUpBid2Stor, doc='Relation FCR-D upward bid to storage'))

    def eEleRelationFreqDisDownBid2Stor(optmodel, p,sc,n,egs):
        if model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0:
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs] == optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisDownBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqDisDownBid2Stor, doc='Relation FCR-D downward bid to storage'))

    def eEleRelationFreqNorUpBid2Stor(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] == optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorUpBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqNorUpBid2Stor, doc='Relation FCR-N upward bid to storage'))

    def eEleRelationFreqNorDownBid2Stor(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorDownBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqNorDownBid2Stor, doc='Relation FCR-N downward bid to storage'))

    # symmetrical FCR-N provision from an electric ESS
    def eEleSymmFreqNorStor2Ch(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleSymmFreqNorStor2Ch', Constraint(optmodel.psnegs, rule=eEleSymmFreqNorStor2Ch, doc='Symmetrical FCR-N charge provision from storage'))

    def eEleSymmFreqNorStor2Dis(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleSymmFreqNorStor2Dis', Constraint(optmodel.psnegs, rule=eEleSymmFreqNorStor2Dis, doc='Symmetrical FCR-N discharge provision from storage'))

    # The tight headroom bounds for FCR-D provision from an electric ESS is defined as follows:
    def eEleFreqUpDischargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if  model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n] - optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]
            else:
                return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxCharge'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpDischargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqUpDischargeHeadroom, doc='FCR-D and FCR-N upward discharge headroom'))

    def eEleFreqUpChargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] <= optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqUpChargeHeadroom, doc='FCR-D and FCR-N upward charge headroom'))

    def eEleFreqDownDischargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] <= optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]
            else:
                return optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] <= model.Par['pEleMaxCharge'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownDischargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqDownDischargeHeadroom, doc='FCR-D downward discharge headroom'))

    def eEleFreqDownChargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs] <= model.Par['pEleMaxCharge'][egs][p,sc,n] - optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqDownChargeHeadroom, doc='FCR-D downward charge headroom'))

    def eEleFreqUpChargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            return (optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeBound', Constraint(optmodel.psnegs, rule=eEleFreqUpChargeBound, doc='FCR-D and FCR-N upward charge bound'))

    def eEleFreqUpDischargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return (optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
            else:
                return (optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpDischargeBound', Constraint(optmodel.psnegs, rule=eEleFreqUpDischargeBound, doc='FCR-D upward discharge bound'))

    def eEleFreqDownChargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            return (optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeBound', Constraint(optmodel.psnegs, rule=eEleFreqDownChargeBound, doc='FCR-D downward charge bound'))

    def eEleFreqDownDischargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] >= 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return (optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
            else:
                return (optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownDischargeBound', Constraint(optmodel.psnegs, rule=eEleFreqDownDischargeBound, doc='FCR-D and FCR-N downward discharge bound'))

    def eEleInflowsCharge(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxInflows'][egs][p,sc,n] and model.Par['pEleGenNoFCRD'][egs] == 0 and model.Par['pEleGenNoDayAhead'][egs] == 1:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMaxInflows'][egs][p,sc,n] <= optmodel.vEleStorCharge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInflowsCharge', Constraint(optmodel.psnegs, rule=eEleInflowsCharge, doc='Energy inflows to charge bound'))

    def eEleStorageEnduranceUp(optmodel, p,sc,n,egs):
        if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and model.Par['pEleMaxStorage'][egs][p,sc,n] and n != model.n.first():
            return optmodel.vEleInventory[p,sc,n,egs] >= (1/model.Par['pEleGenEfficiency_discharge'][egs]) * ((model.Par['pEleGenEnduranceFCRD'][egs]/60) * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,model.n.prev(n,1),egs] + (model.Par['pEleGenEnduranceFCRN'][egs]/60) * optmodel.vEleFreqContReserveNorBid[p,sc,model.n.prev(n,1),egs])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageEnduranceUp', Constraint(optmodel.psnegs, rule=eEleStorageEnduranceUp, doc='Storage endurance for FCR-D and FCR-N upward'))

    def eEleStorageEnduranceDown(optmodel, p,sc,n,egs):
        if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and model.Par['pEleMaxStorage'][egs][p,sc,n] and n != model.n.first():
            return model.Par['pEleMaxStorage'][egs][p,sc,n] - optmodel.vEleInventory[p,sc,n,egs] >= model.Par['pEleGenEfficiency_charge'][egs] * ((model.Par['pEleGenEnduranceFCRD'][egs]/60) * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,model.n.prev(n,1),egs] + (model.Par['pEleGenEnduranceFCRN'][egs]/60) * optmodel.vEleFreqContReserveNorBid[p,sc,model.n.prev(n,1),egs])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageEnduranceDown', Constraint(optmodel.psnegs, rule=eEleStorageEnduranceDown, doc='Storage endurance for FCR-D and FCR-N downward'))

    # print if the constraints object len is greater than 0
    if (len(optmodel.eEleFreqContReserveDisUpward) > 0 or len(optmodel.eEleFreqContReserveDisDownward) > 0 or
        len(optmodel.eEleRelationFreqDisUpBid2Gen) > 0 or len(optmodel.eEleRelationFreqDisDownBid2Gen) > 0 or
        len(optmodel.eEleRelationFreqDisUpBid2Stor) > 0 or len(optmodel.eEleRelationFreqDisDownBid2Stor) > 0 or
        len(optmodel.eEleFreqUpDischargeHeadroom) > 0 or len(optmodel.eEleFreqUpChargeHeadroom) > 0 or
        len(optmodel.eEleFreqDownDischargeHeadroom) > 0 or len(optmodel.eEleFreqDownChargeHeadroom) > 0 or
        len(optmodel.eEleFreqUpChargeBound) > 0 or len(optmodel.eEleFreqUpDischargeBound) > 0 or
        len(optmodel.eEleFreqDownChargeBound) > 0 or len(optmodel.eEleFreqDownDischargeBound) > 0):
        log_time('--- Declaring the frequency containment reserve (FCR-D and FCR-N) constraints:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Energy inflows of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the inflows data [p.u.]
    def eEleMaxInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMaxInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMaxInflows'][egs][p,sc,n] <= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMaxInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eEleMinInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMinStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMinInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMinInflows'][egs][p,sc,n] >= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMinInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eHydMaxInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMaxInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMaxInflows'][hgs][p,sc,n] <= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMaxInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    def eHydMinInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMinInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMinInflows'][hgs][p,sc,n] >= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMinInflows2Commitment, doc='energy inflows to commitment [p.u.]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxInflows2Commitment) > 0 or len(optmodel.eEleMinInflows2Commitment) > 0 or len(optmodel.eHydMaxInflows2Commitment) > 0 or len(optmodel.eHydMinInflows2Commitment) > 0:
        log_time('--- Declaring the energy inflows of ESS:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # ESS energy inventory (only for load levels multiple of 1, 24, 168 h depending on the ESS storage type) [GWh]
    def eEleInventory(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] + model.Par['pEleMaxPower'][egs][p,sc,n] and (n,egs) in model.negs:
            if   model.n.ord(n) == model.Par['pEleCycleTimeStep'][egs]:
                return model.Par['pEleInitialInventory'][egs][p,sc,n]                                       + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vEleEnergyInflows[p,sc,n2,egs] - optmodel.vEleEnergyOutflows[p,sc,n2,egs] - (optmodel.vEleTotalOutput[p,sc,n2,egs] * (1/(model.Par['pEleGenEfficiency_discharge'][egs]))) + (model.Par['pEleGenEfficiency_charge'][egs]) * optmodel.vEleTotalCharge[p,sc,n2,egs]) for n2 in n2_list[model.n.ord(n) - model.Par['pEleCycleTimeStep'][egs]:model.n.ord(n)]) == optmodel.vEleInventory[p,sc,n,egs] + optmodel.vEleSpillage[p,sc,n,egs]
            elif model.n.ord(n) >  model.Par['pEleCycleTimeStep'][egs]:
                return optmodel.vEleInventory[p,sc,model.n.prev(n,model.Par['pEleCycleTimeStep'][egs]),egs] + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vEleEnergyInflows[p,sc,n2,egs] - optmodel.vEleEnergyOutflows[p,sc,n2,egs] - (optmodel.vEleTotalOutput[p,sc,n2,egs] * (1/(model.Par['pEleGenEfficiency_discharge'][egs]))) + (model.Par['pEleGenEfficiency_charge'][egs]) * optmodel.vEleTotalCharge[p,sc,n2,egs]) for n2 in n2_list[model.n.ord(n) - model.Par['pEleCycleTimeStep'][egs]:model.n.ord(n)]) == optmodel.vEleInventory[p,sc,n,egs] + optmodel.vEleSpillage[p,sc,n,egs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventory', Constraint(optmodel.psnegs, rule=eEleInventory, doc='Electricity ESS inventory balance [GWh]'))

    def eHydInventory(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.negs:
            if   model.n.ord(n) == model.Par['pHydCycleTimeStep'][hgs]:
                return model.Par['pHydInitialInventory'][hgs][p,sc,n]                                       + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in n2_list[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            elif model.n.ord(n) >  model.Par['pHydCycleTimeStep'][hgs]:
                return optmodel.vHydInventory[p,sc,model.n.prev(n,model.Par['pHydCycleTimeStep'][hgs]),hgs] + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in n2_list[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydInventory', Constraint(optmodel.psnhgs, rule=eHydInventory, doc='Hydrogen ESS inventory balance [KgH2h]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleInventory) > 0 or len(optmodel.eHydInventory) > 0:
        log_time('--- Declaring the ESS energy inventory:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # ESS SoC Min per Day [kWh]
    def eEleInventoryMinDay(optmodel, p,sc,d,n,egs):
        if   model.n.ord(n) >  model.Par['pEleCycleTimeStep'][egs] and (model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs] == 1):
             return optmodel.vEleInventoryMinDay[p,sc,d,egs] <= optmodel.vEleInventory[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryMinDay', Constraint(optmodel.psdnegs, rule=eEleInventoryMinDay, doc='ESS inventory Min Day [kWh]'))

    # ESS SoC Max per Day [kWh]
    def eEleInventoryMaxDay(optmodel, p,sc,d,n,egs):
        if   model.n.ord(n) >  model.Par['pEleCycleTimeStep'][egs] and (model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs] == 1):
             return optmodel.vEleInventoryMaxDay[p,sc,d,egs] >= optmodel.vEleInventory[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryMaxDay', Constraint(optmodel.psdnegs, rule=eEleInventoryMaxDay, doc='ESS inventory Max Day [kWh]'))

    # ESS DoD per Day [kWh]
    def eEleInventoryDoD(optmodel, p,sc,d,egs):
        if model.Par['pEleGenMaximumStorage'][egs] > 0 and (model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs]) == 1:
            return optmodel.vEleInventoryDoDDay[p,sc,d,egs] == optmodel.vEleInventoryMaxDay[p,sc,d,egs] - optmodel.vEleInventoryMinDay[p,sc,d,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryDoD', Constraint(optmodel.psdegs, rule=eEleInventoryDoD, doc='ESS Depth of Discharge (DoD) [kWh]'))

    #Total ESS DoD per Day (Segments) and [kWh]
    def eEleInventoryDoDSegments(optmodel, p,sc,d,egs):
        if model.Par['pEleGenMaximumStorage'][egs] > 0 and (model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs]) == 1:
            return optmodel.vEleInventoryDoDDay[p,sc,d,egs] == optmodel.vEleInventoryDoDS1Day[p,sc,d,egs] + optmodel.vEleInventoryDoDS2Day[p,sc,d,egs] + optmodel.vEleInventoryDoDS3Day[p,sc,d,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryDoDSegments', Constraint(optmodel.psdegs, rule=eEleInventoryDoDSegments, doc='Total ESS Depth of Discharge (DoD) per Segment [kWh]'))

    def eEleInventoryDoDS1Upper(optmodel, p, sc, d, egs):
        if model.Par['pEleGenMaximumStorage'][egs] > 0 and model.Par['pEleGenDoDS1'][egs] > 0 and model.Par['pEleGenDoDS1'][egs] < 1 and model.Par['pEleGenDoDC1'][egs] > 0:
            return optmodel.vEleInventoryDoDS1Day[p, sc, d, egs] <= model.Par['pEleGenDoDS1'][egs] * model.Par['pEleGenMaximumStorage'][egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryDoDS1Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS1Upper, doc='ESS Depth of Discharge (DoD) per Segment 1 Up [kWh]'))

    def eEleInventoryDoDS2Upper(optmodel, p, sc, d, egs):
        if model.Par['pEleGenMaximumStorage'][egs] > 0 and model.Par['pEleGenDoDS2'][egs] > 0 and model.Par['pEleGenDoDS2'][egs] < 1 and model.Par['pEleGenDoDC2'][egs] > 0:
            return optmodel.vEleInventoryDoDS2Day[p, sc, d, egs] <= model.Par['pEleGenDoDS2'][egs] * model.Par['pEleGenMaximumStorage'][egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryDoDS2Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS2Upper, doc='ESS Depth of Discharge (DoD) per Segment 2 Upper [kWh]'))

    def eEleInventoryDoDS3Upper(optmodel, p, sc, d, egs):
        if model.Par['pEleGenMaximumStorage'][egs] > 0 and model.Par['pEleGenDoDS3'][egs] > 0 and model.Par['pEleGenDoDS3'][egs] < 1 and model.Par['pEleGenDoDC3'][egs] > 0:
            # b2 = model.Par['pEleGenDoDS2'][egs]
            # b3 = model.Par['pEleGenDoDS3'][egs]
            return optmodel.vEleInventoryDoDS3Day[p, sc, d, egs] <= optmodel.vEleInventoryDoDDay[p, sc, d, egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleInventoryDoDS3Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS3Upper, doc='ESS Depth of Discharge (DoD) per Segment 3 Upper [kWh]'))

    # #Total ESS DoD per Day (Segment 1) and [kWh]
    # def eEleInventoryDoDS1Upper(optmodel, p,sc,d,egs):
    #     if model.Par['pEleGenMaximumStorage'][egs] > 0:
    #         return optmodel.vEleInventoryDoDS1Day[p,sc,d,egs] <= (model.Par['pEleGenDoDS1'][egs] * model.factor1) * model.Par['pEleGenMaximumStorage'][egs]
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleInventoryDoDS1Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS1Upper, doc='ESS Depth of Discharge (DoD) per Segment 1 Up [kWh]'))
    #
    # # def eEleInventoryDoDS1Lower(optmodel, p,sc,d,egs):
    # #     if model.Par['pGenMaximumStorage'][egs] > 0:
    # #         return optmodel.vEleInventoryDoDS1Day[p,sc,d,egs] >= 0
    # #     else:
    # #         return Constraint.Skip
    # # optmodel.__setattr__('eEleInventoryDoDS1Lower', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS1Lower, doc='ESS Depth of Discharge (DoD) per Segment 1 Lower [kWh]'))
    #
    # #Total ESS DoD per Day (Segment 2) and [kWh]
    # def eEleInventoryDoDS2Upper(optmodel, p,sc,d,egs):
    #     if model.Par['pEleGenMaximumStorage'][egs] > 0:
    #         return optmodel.vEleInventoryDoDS2Day[p,sc,d,egs] <= (model.Par['pEleGenDoDS2'][egs] * model.factor1) * model.Par['pEleGenMaximumStorage'][egs]
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleInventoryDoDS2Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS2Upper, doc='ESS Depth of Discharge (DoD) per Segment 2 Upper [kWh]'))
    #
    # # def eEleInventoryDoDS2Lower(optmodel, p,sc,d,egs):
    # #     if model.Par['pGenMaximumStorage'][egs] > 0:
    # #         return optmodel.vEleInventoryDoDS2Day[p,sc,d,egs] >= 0
    # #     else:
    # #         return Constraint.Skip
    # # optmodel.__setattr__('eEleInventoryDoDS2Lower', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS2Lower, doc='ESS Depth of Discharge (DoD) per Segment 2 Lower [kWh]'))
    #
    # #Total ESS DoD per Day (Segment 3) and [kWh]
    # def eEleInventoryDoDS3Upper(optmodel, p,sc,d,egs):
    #     if model.Par['pEleGenMaximumStorage'][egs] > 0:
    #         return optmodel.vEleInventoryDoDS3Day[p,sc,d,egs] <= (model.Par['pEleGenDoDS3'][egs] * model.factor1) * model.Par['pEleGenMaximumStorage'][egs]
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleInventoryDoDS3Upper', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS3Upper, doc='ESS Depth of Discharge (DoD) per Segment 3 Upper [kWh]'))
    #
    # # def eEleInventoryDoDS3Lower(optmodel, p,sc,d,egs):
    # #     if model.Par['pGenMaximumStorage'][egs] > 0:
    # #         return optmodel.vEleInventoryDoDS3Day[p,sc,d,egs] >= 0
    # #     else:
    # #         return Constraint.Skip
    # # optmodel.__setattr__('eEleInventoryDoDS3Lower', Constraint(optmodel.psdegs, rule=eEleInventoryDoDS3Lower, doc='ESS Depth of Discharge (DoD) per Segment 3 Lower [kWh]'))

    # print if the constraints object len is greater than 0
    if (len(optmodel.eEleInventoryMinDay) > 0 or len(optmodel.eEleInventoryMaxDay) > 0 or len(optmodel.eEleInventoryDoD) > 0 or len(optmodel.eEleInventoryDoDSegments) > 0 or len(optmodel.eEleInventoryDoDS1Upper) > 0 or len(optmodel.eEleInventoryDoDS2Upper) > 0 or len(optmodel.eEleInventoryDoDS3Upper) > 0):
        log_time('--- Declaring the ESS SoC Min/Max and DoD per Day constraints:', StartTime, ind_log=indlog)
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
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMaxOutflows'][egs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMaxEnergyOutflows, doc='electricity energy outflows of an ESS unit [GWh]'))

    def eEleMinEnergyOutflows(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] + model.Par['pEleMinPower'][egs][p,sc,n] and (n,egs) in model.negso:
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMinOutflows'][egs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMinEnergyOutflows, doc='electricity energy outflows of an ESS unit [GWh]'))

    def eHydMaxEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMaxOutflows'][hgs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMaxEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [tH2]'))

    def eHydMinEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinCharge'][hgs][p,sc,n] + model.Par['pHydMinPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMinOutflows'][hgs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMinEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [tH2]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxOutflows2Commitment) > 0 or len(optmodel.eEleMinOutflows2Commitment) > 0 or len(optmodel.eHydMaxOutflows2Commitment) > 0 or len(optmodel.eHydMinOutflows2Commitment) > 0 or len(optmodel.eEleMaxEnergyOutflows) > 0 or len(optmodel.eEleMinEnergyOutflows) > 0 or len(optmodel.eHydMaxEnergyOutflows) > 0 or len(optmodel.eHydMinEnergyOutflows) > 0:
        log_time('--- Declaring the ESS outflows:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Maximum and minimum output of the second block of a committed unit (all except the VRES and ESS units) [p.u.]
    def eEleMaxOutput2ndBlock(optmodel, p,sc,n,egt):
        if   model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs and n != model.n.last() and model.Par['pEleGenNoFCRD'][egt] == 0:
            return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] <= optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt] - optmodel.vEleGenShutDown[p,sc,model.n.next(n),egt]
        elif model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs and n == model.n.last():
            return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] <= optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxOutput2ndBlock', Constraint(optmodel.psnegt, rule=eEleMaxOutput2ndBlock, doc='max output of the second block of a committed unit [p.u.]'))

    def eEleMinOutput2ndBlock(optmodel, p,sc,n,egt):
        if model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n] and egt not in model.egs and model.Par['pEleGenNoFCRD'][egt] == 0:
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] - optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt] >= 0.0
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

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxOutput2ndBlock) > 0 or len(optmodel.eEleMinOutput2ndBlock) > 0 or len(optmodel.eHydMaxOutput2ndBlock) > 0 or len(optmodel.eHydMinOutput2ndBlock) > 0:
        log_time('--- Declaring the maximum and minimum output of the second block:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Maximum and minimum output of the second block of an electricity ESS [p.u.]
    def eEleMaxESSOutput2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
            # return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= 1.0
            if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and (model.Par['pEleGenNoDayAhead'][egs] == 1 or model.Par['pEleGenNoDayAhead'][egs] == 0):
                return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= 1.0
            else:
                return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= optmodel.vEleStorDischarge[p,sc,n,egs]
        elif model.Par['pEleMaxPower'][egs][p,sc,n] <= 1e-5 and model.Par['pEleGenNoDayAhead'][egs] == 0 and (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0):
            return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSOutput2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSOutput2ndBlock, doc='max output of the second block of an ESS [p.u.]'))

    def eEleMinESSOutput2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMinPower'][egs][p,sc,n]:
            # return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]) / model.Par['pEleMinPower'][egs][p,sc,n] >= 0.0
            if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and (model.Par['pEleGenNoDayAhead'][egs] == 1 or model.Par['pEleGenNoDayAhead'][egs] == 0):
                return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] - optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]) / model.Par['pEleMinPower'][egs][p,sc,n] >= 0.0
            else:
                return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] - optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]) / model.Par['pEleMinPower'][egs][p,sc,n] >= optmodel.vEleStorDischarge[p,sc,n,egs]
        elif model.Par['pEleMinPower'][egs][p,sc,n] == 0.0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
            return optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] - optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinESSOutput2ndBlock', Constraint(optmodel.psnegs, rule=eEleMinESSOutput2ndBlock, doc='min output of the second block of an ESS [p.u.]'))

    def eHydMaxESSOutput2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n]:
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] <= optmodel.vHydStorCharge[p,sc,n,hgs]
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
        if model.Par['pEleMaxCharge'][egs][p,sc,n]:
            # return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= 1.0
            if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and (model.Par['pEleGenNoDayAhead'][egs] == 1 or model.Par['pEleGenNoDayAhead'][egs] == 0):
                return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= 1.0
            else:
                return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= optmodel.vEleStorCharge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSCharge2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eEleMinESSCharge2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n]:
            # return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]) / model.Par['pEleMinCharge'][egs][p,sc,n] >= 0.0
            if  (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and (model.Par['pEleGenNoDayAhead'][egs] == 1 or model.Par['pEleGenNoDayAhead'][egs] == 0):
                return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] - optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]) / model.Par['pEleMinCharge'][egs][p,sc,n] >= 0.0
            else:
                return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] - optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]) / model.Par['pEleMinCharge'][egs][p,sc,n] >= optmodel.vEleStorCharge[p,sc,n,egs]
        elif model.Par['pEleMinCharge'][egs][p,sc,n] == 0.0:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] - optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] >= 0.0
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
            return optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n] <= optmodel.vHydStorDischarge[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eMaxHydESSCharge2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMaxESSCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eHydMinESSCharge2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            return optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n] >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinESSCharge2ndBlock', Constraint(optmodel.psnhgs, rule=eHydMinESSCharge2ndBlock, doc='min charge of an ESS [p.u.]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxESSOutput2ndBlock) > 0 or len(optmodel.eEleMinESSOutput2ndBlock) > 0 or len(optmodel.eHydMaxESSOutput2ndBlock) > 0 or len(optmodel.eHydMinESSOutput2ndBlock) > 0 or len(optmodel.eEleMaxESSCharge2ndBlock) > 0 or len(optmodel.eEleMinESSCharge2ndBlock) > 0 or len(optmodel.eE2HMaxCharge2ndBlock) > 0 or len(optmodel.eE2HMinCharge2ndBlock) > 0 or len(optmodel.eMaxHydESSCharge2ndBlock) > 0 or len(optmodel.eHydMinESSCharge2ndBlock) > 0:
        log_time('--- Declaring the maximum and minimum charge of an ESS:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Incompatibility between charge and discharge of an electrical ESS [p.u.]
    def eEleChargingDecision(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] :
            return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pEleMaxCharge'][egs][p,sc,n]  <= optmodel.vEleStorCharge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleChargingDecision', Constraint(optmodel.psnegs, rule=eEleChargingDecision, doc='charging decision [p.u.]'))

    def eEleDischargingDecision(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxPower'][egs][p,sc,n] :
            return optmodel.vEleTotalOutput[p,sc,n,egs] / model.Par['pEleMaxPower'][egs][p,sc,n]  <= optmodel.vEleStorDischarge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDischargingDecision', Constraint(optmodel.psnegs, rule=eEleDischargingDecision, doc='discharging decision [p.u.]'))

    def eEleStorageMode(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] + model.Par['pEleMaxPower'][egs][p,sc,n]:
            return optmodel.vEleStorCharge[p,sc,n,egs] + optmodel.vEleStorDischarge[p,sc,n,egs] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageMode', Constraint(optmodel.psnegs, rule=eEleStorageMode, doc='storage mode [p.u.]'))

    # Incompatibility between charge and discharge of an H2 ESS [p.u.]
    def eHydChargingDecision(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxPower'][hgs][p,sc,n] :
            return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMaxPower'][hgs][p,sc,n]  <= optmodel.vHydStorCharge[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydChargingDecision', Constraint(optmodel.psnhgs, rule=eHydChargingDecision, doc='charging decision [p.u.]'))

    def eHydDischargingDecision(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] :
            return optmodel.vHydTotalOutput[p,sc,n,hgs] / model.Par['pHydMaxCharge'][hgs][p,sc,n]  <= optmodel.vHydStorDischarge[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydDischargingDecision', Constraint(optmodel.psnhgs, rule=eHydDischargingDecision, doc='discharging decision [p.u.]'))

    def eHydStorageMode(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n]:
            return optmodel.vHydStorCharge[p,sc,n,hgs] + optmodel.vHydStorDischarge[p,sc,n,hgs] <= model.Par['pVarFixedAvailability'][hgs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydStorageMode', Constraint(optmodel.psnhgs, rule=eHydStorageMode, doc='storage mode [p.u.]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleChargingDecision) > 0 or len(optmodel.eEleDischargingDecision) > 0 or len(optmodel.eEleStorageMode) > 0 or len(optmodel.eHydChargingDecision) > 0 or len(optmodel.eHydDischargingDecision) > 0 or len(optmodel.eHydStorageMode) > 0:
        log_time('--- Declaring the incompatibility between charge and discharge:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Total output of a committed unit (all except the VRES units) [GW]
    def eEleTotalOutput(optmodel, p,sc,n,egnr):
        if model.Par['pEleMaxPower'][egnr][p,sc,n]:
            if  egnr in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr]                                           ==                                             optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egnr]
            elif model.Par['pEleMinPower'][egnr][p,sc,n] == 0.0 and egnr not in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr]                                           ==                                             optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egnr]
            elif model.Par['pEleMinPower'][egnr][p,sc,n] != 0.0 and egnr not in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n] == optmodel.vEleGenCommitment[p,sc,n,egnr] + ((optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egnr]) / model.Par['pEleMinPower'][egnr][p,sc,n])
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
                return optmodel.vHydTotalOutput[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n] == optmodel.vHydStorDischarge[p,sc,n,hgt] + (optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n])
            elif model.Par['pHydMinPower'][hgt][p,sc,n] != 0.0 and hgt not in model.hgs:
                return optmodel.vHydTotalOutput[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n] == optmodel.vHydGenCommitment[p,sc,n,hgt]          + (optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMinPower'][hgt][p,sc,n])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydTotalOutput', Constraint(optmodel.psnhgt, rule=eHydTotalOutput, doc='total output of an H2 producer unit [tH2]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleTotalOutput) > 0 or len(optmodel.eHydTotalOutput) > 0:
        log_time('--- Declaring the total output of a committed unit:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Total charge of an ESS [GW]
    def eEleTotalCharge(optmodel, p,sc,n,egs):
        if egs in model.egs:
            if model.Par['pEleMaxCharge'][egs][p,sc,n] and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
                return optmodel.vEleTotalCharge[p,sc,n,egs]                                           ==                                         optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] - model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
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

    # Total charge of an H2 ESS unit [tH2]
    def eHydTotalCharge(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] and model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            if model.Par['pHydMinCharge'][hgs][p,sc,n] == 0.0:
                return optmodel.vHydTotalCharge[p,sc,n,hgs]                                           ==                                                    optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]
            else:
                return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n] == optmodel.vHydStorCharge[p,sc,n,hgs] + (optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydTotalCharge', Constraint(optmodel.psnhgs, rule=eHydTotalCharge, doc='total charge of an H2 ESS unit [tH2]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleTotalCharge) > 0:
        log_time('--- Declaring the total charge of an H2 ESS unit:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # # Incompatibility between charge and outflows use of an ESS [p.u.]
    # def eIncompatibilityEleChargeOutflows(optmodel, p,sc,n,egs):
    #     if (p,sc,egs) in model.psegso:
    #         if model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
    #             return (optmodel.vEleEnergyOutflows[p,sc,n,egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= 1.0
    #         else:
    #             return Constraint.Skip
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eIncompatibilityEleChargeOutflows', Constraint(optmodel.psnegs, rule=eIncompatibilityEleChargeOutflows, doc='incompatibility between charge and outflows use [p.u.]'))
    #
    # # def eIncompatibilityHydChargeOutflows(optmodel, p,sc,n, hs):
    # #     if (p,sc,hs) in model.pseso:
    # #         if model.Par['pMaxCharge2ndBlock'][hs][p,sc,n]:
    # #             return (optmodel.vHydEnergyOutflows[p,sc,n,hs] + optmodel.vHydTotalCharge2ndBlock[p,sc,n,hs]) / model.Par['pHydMaxCharge2ndBlock'][hs][p,sc,n] <= 1.0
    # #         else:
    # #             return Constraint.Skip
    # #     else:
    # #         return Constraint.Skip
    # # optmodel.__setattr__('eIncompatibilityHydChargeOutflows', Constraint(optmodel.psnhgs, rule=eIncompatibilityHydChargeOutflows, doc='incompatibility between charge and outflows use [p.u.]'))
    #
    # # print if the constraints object len is greater than 0
    # if len(optmodel.eIncompatibilityEleChargeOutflows) > 0: # or len(optmodel.eIncompatibilityHydChargeOutflows) > 0:
    #     log_time('--- Declaring the incompatibility between charge and outflows use:', StartTime, ind_log=indlog)
    #     StartTime = time.time() # to compute elapsed time

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

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleCommitmentStartupShutdown) > 0 or len(optmodel.eHydCommitmentStartupShutdown) > 0:
        log_time('--- Declaring the logical relation in the unit commitment:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Maximum ramp up and ramp down for the second block of a non-renewable (thermal, hydro) unit [p.u.]
    def eEleMaxRampUpOutput(optmodel, p,sc,n,egt):
        if model.Par['pEleGenRampUp'][egt] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleGenRampUp'][egt] < model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n]:
            if n == model.n.first():
                return (- max(model.Par['pEleSystemOutput'] - model.Par['pEleMinPower'][egt][p,sc,n],0.0)                                               + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egt] - optmodel.vEleFreqContReserveDisDownGen[p,sc,model.n.prev(n),egt] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpOutput', Constraint(optmodel.psnegt, rule=eEleMaxRampUpOutput, doc='maximum ramp up   [p.u.]'))

    def eEleMaxRampDwOutput(optmodel, p,sc,n,egt):
        if model.Par['pEleGenRampDown'][egt] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleGenRampDw'][egt] < model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n]:
            if n == model.n.first():
                return (- max(model.Par['pEleSystemOutput'] - model.Par['pEleMinPower'][egt][p,sc,n],0.0)                                             + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egt] >= - model.Par['pEleInitialUC'][p,sc,egt]                 + optmodel.vEleGenShutDown[p,sc,n,egt]
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egt] - optmodel.vEleFreqContReserveDisUpGen[p,sc,model.n.prev(n),egt] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egt] >= - optmodel.vEleGenCommitment[p,sc,model.n.prev(n),egt] + optmodel.vEleGenShutDown[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwOutput', Constraint(optmodel.psnegt, rule=eEleMaxRampDwOutput, doc='maximum ramp down [p.u.]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxRampUpOutput) > 0 or len(optmodel.eEleMaxRampDwOutput) > 0:
        log_time('--- Declaring the maximum ramp up and ramp down for the second block:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Maximum ramp down and ramp up for the charge of an ESS [p.u.]
    def eEleMaxRampUpCharge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampUp'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                                                                                                  optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] >= - 1.0
            else:
                return (- optmodel.vEleTotalCharge2ndBlock[p,sc,model.n.prev(n),egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpCharge', Constraint(optmodel.psnegs, rule=eEleMaxRampUpCharge, doc='maximum ramp up   charge [p.u.]'))

    def eEleMaxRampDwCharge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampDown'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxCharge2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                                                                                              + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] <=   1.0
            else:
                return (- optmodel.vEleTotalCharge2ndBlock[p,sc,model.n.prev(n),egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwCharge', Constraint(optmodel.psnegs, rule=eEleMaxRampDwCharge, doc='maximum ramp down charge [p.u.]'))

    def eEleMaxRampUpDischarge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampUp'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                                                                                                  optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] <=   1.0
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egs] <=   1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpDischarge', Constraint(optmodel.psnegs, rule=eEleMaxRampUpDischarge, doc='maximum ramp up   discharge [p.u.]'))

    def eEleMaxRampDwDischarge(optmodel, p,sc,n,egs):
        if model.Par['pEleGenRampDown'][egs] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n]:
            if n == model.n.first():
                return (                                                                                                                                optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] >= - 1.0
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egs] - optmodel.vEleFreqContReserveDisUpDis[p,sc,model.n.prev(n),egs] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egs] >= - 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampDwDischarge', Constraint(optmodel.psnegs, rule=eEleMaxRampDwDischarge, doc='maximum ramp down discharge [p.u.]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMaxRampUpCharge) > 0 or len(optmodel.eEleMaxRampDwCharge) > 0 or len(optmodel.eEleMaxRampUpDischarge) > 0 or len(optmodel.eEleMaxRampDwDischarge) > 0:
        log_time('--- Declaring the maximum ramp down and ramp up for the charge:', StartTime, ind_log=indlog)
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

    # print if the constraints object len is greater than 0
    if len(optmodel.eHydMaxRampUpOutput) > 0 or len(optmodel.eHydMaxRampDwOutput) > 0:
        log_time('--- Declaring the maximum ramp up and ramp down for the H2 output:', StartTime, ind_log=indlog)
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

    # print if the constraints object len is greater than 0
    if len(optmodel.eHydMaxRampUpCharge) > 0 or len(optmodel.eHydMaxRampDwCharge) > 0:
        log_time('--- Declaring the maximum ramp up and ramp down for the H2 charge:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # # maximum ramp up and ramp down for the outflows of an H2 ESS [p.u.]
    # def eEleMaxRampUpOutflows(optmodel, p,sc,n,egs):
    #     if model.Par['pEleGenOutflowsRampUp'][egs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
    #         if n == model.n.first():
    #             return (                                                          optmodel.vEleEnergyOutflows[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenOutflowsRampUp'][egs] <=   1.0
    #         else:
    #             return (- optmodel.vEleEnergyOutflows[p,sc,model.n.prev(n),egs] + optmodel.vEleEnergyOutflows[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenOutflowsRampUp'][egs] <=   1.0
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleMaxRampUpOutflows', Constraint(optmodel.psnegs, rule=eEleMaxRampUpOutflows, doc='maximum ramp up   outflows [p.u.]'))
    #
    # def eEleMaxRampDwOutflows(optmodel, p,sc,n,egs):
    #     if model.Par['pEleGenOutflowsRampDown'][egs] > 0 and model.Par['pOptIndBinGenRamps'] == 1:
    #         if n == model.n.first():
    #             return (                                                          optmodel.vEleEnergyOutflows[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenOutflowsRampDown'][egs] >= - 1.0
    #         else:
    #             return (- optmodel.vEleEnergyOutflows[p,sc,model.n.prev(n),egs] + optmodel.vEleEnergyOutflows[p,sc,n,egs]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenOutflowsRampDown'][egs] >= - 1.0
    #     else:
    #         return Constraint.Skip
    # optmodel.__setattr__('eEleMaxRampDwOutflows', Constraint(optmodel.psnegs, rule=eEleMaxRampDwOutflows, doc='maximum ramp down outflows [p.u.]'))
    #
    # # print if the constraints object len is greater than 0
    # if len(optmodel.eEleMaxRampUpOutflows) > 0 or len(optmodel.eEleMaxRampDwOutflows) > 0:
    #     log_time('--- Declaring the maximum ramp up and ramp down for the Electricity outflows:', StartTime, ind_log=indlog)
    #     StartTime = time.time() # to compute elapsed time

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

    # print if the constraints object len is greater than 0
    if len(optmodel.eHydMaxRampUpOutflows) > 0 or len(optmodel.eHydMaxRampDwOutflows) > 0:
        log_time('--- Declaring the maximum ramp up and ramp down for the H2 outflows:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # Minimum up time and down time of thermal unit [h]
    def eEleMinUpTime(optmodel, p,sc,n,egt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and (model.Par['pEleMinPower'][egt][p,sc,n] or model.Par['pEleGenConstantTerm'][egt]) and egt not in model.egs and model.n.ord(n) > (model.Par['pEleGenUpTime'][egt] - model.Par['pEleGenUpTimeZero'][egt]):
            return sum(optmodel.vEleGenStartUp[ p,sc,n2,egt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pEleGenUpTime'  ][egt], max(0,min(model.n.ord(n),(model.Par['pEleGenUpTime'  ][egt] - model.Par['pEleGenUpTimeZero'  ][egt])*(  model.Par['pEleInitialUC'][p,sc,egt]))))):model.n.ord(n)]) <=     optmodel.vEleGenCommitment[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinUpTime', Constraint(optmodel.psnegt, rule=eEleMinUpTime, doc='minimum up   time [h]'))

    def eEleMinDownTime(optmodel, p,sc,n,egt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and (model.Par['pEleMinPower'][egt][p,sc,n] or model.Par['pEleGenConstantTerm'][egt]) and egt not in model.egs and model.n.ord(n) > (model.Par['pEleGenDownTime'][egt] - model.Par['pEleGenDownTimeZero'][egt]):
            return sum(optmodel.vEleGenShutDown[p,sc,n2,egt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pEleGenDownTime'][egt], max(0,min(model.n.ord(n),(model.Par['pEleGenDownTime'][egt] - model.Par['pEleGenDownTimeZero'][egt])*(1-model.Par['pEleInitialUC'][p,sc,egt]))))):model.n.ord(n)]) <= 1 - optmodel.vEleGenCommitment[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinDownTime', Constraint(optmodel.psnegt, rule=eEleMinDownTime, doc='minimum down time [h]'))

    # Minimum up time and down time of an electrolyzer [h]
    def eHydMinUpTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenUpTime'][hgt] > 1 and model.n.ord(n) > (model.Par['pHydGenUpTime'][hgt] - model.Par['pHydGenUpTimeZero'][hgt]):
            return sum(optmodel.vHydGenStartUp[p,sc,n2,hgt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pHydGenUpTime'   ][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenUpTime'  ][hgt] - model.Par['pHydGenUpTimeZero'  ][hgt])*(  model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <=     optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinUpTime', Constraint(optmodel.psnhgt, rule=eHydMinUpTime, doc='minimum up   time [h]'))

    def eHydMinDownTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenDownTime'][hgt] > 1 and model.n.ord(n) > (model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt]):
            return sum(optmodel.vHydGenShutDown[p,sc,n2,hgt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pHydGenDownTime'][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt])*(1-model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <= 1 - optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinDownTime', Constraint(optmodel.psnhgt, rule=eHydMinDownTime, doc='minimum down time [h]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMinUpTime) > 0 or len(optmodel.eEleMinDownTime) > 0 or len(optmodel.eHydMinUpTime) > 0 or len(optmodel.eHydMinDownTime) > 0:
        log_time('--- Declaring the minimum up and down time:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    def eEleMinEnergyStartUp(optmodel, p,sc,n,egs):
        if model.Par['pVarFixedAvailability'][egs][p,sc,n] and egs in model.egv and model.Par['pEleGenMinSoCDepart'][egs] > 0.0:
            if n != model.n.first() and model.Par['pVarFixedAvailability'][egs][p,sc,model.n.prev(n)] > model.Par['pVarFixedAvailability'][egs][p,sc,n]:
                return optmodel.vEleInventory[p,sc,model.n.prev(n),egs] >= model.Par['pEleGenMinSoCDepart'][egs] * model.factor1
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinEnergyStartUp', Constraint(optmodel.psnegs, rule=eEleMinEnergyStartUp, doc='minimum energy start up'))

    def eEleTotalMaxChargeConditioned(optmodel, p,sc,n,egs):
        # This is an ESS-only condition; electrolysers (e2h) also appear in eh but
        # are not storage, so skip them.
        if egs in model.egs and model.Par['pEleMinCharge'][egs][p,sc,n] == 0.0 and model.Par['pEleGenFixedAvailability'][egs]:
            return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalMaxChargeConditioned', Constraint(optmodel.psneh, rule=eEleTotalMaxChargeConditioned, doc='total charge of an ESS unit [GW]'))

    # print if the constraints object len is greater than 0
    # if len(optmodel.eEleMinEnergyStartUp) > 0 or len(optmodel.eEleTotalMaxChargeConditioned) > 0:
    if len(optmodel.eEleTotalMaxChargeConditioned) > 0:
        log_time('--- Declaring the minimum energy start up and total max charge:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    def eElePeakHourValue(optmodel, p,sc,n,er,m,peak):
        # Check applicability
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            if peak == optmodel.Peaks.first():
                return optmodel.vEleDemPeakGlobal[p, sc, m, er, peak] >= adjusted_buy
            else:
                return optmodel.vEleDemPeakGlobal[p, sc, m, er, peak] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * sum(optmodel.vElePeakGlobalInd[p,sc,n,er,peak2] for peak2 in optmodel.Peaks if peak2 < peak)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourValue', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourValue, doc='peak hour selection'))

    def eElePeakHourInd_C1(optmodel, p,sc,n,er,m,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakGlobalInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C1', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C1, doc='peak hour indicator'))

    def eElePeakHourInd_C2(optmodel, p,sc,n,er,m,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 1.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] <= adjusted_buy + model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakGlobalInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C2', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C2, doc='peak hour indicator'))

    def eElePeakNumberMonths(optmodel, m,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and sum(model.Par['pEleRetPowerTariff'][er] for er in model.er if model.Par['pEleRetTariffType'][er] == 'Hourly') > 0:
            return sum(optmodel.vElePeakGlobalInd[p,sc,n,er,peak] for p,sc,n,er in model.psner if model.Par['pEleRetPowerTariff'][er] and (n,m) in model.n2m) == 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakNumberMonths', Constraint(optmodel.moy, optmodel.Peaks, rule=eElePeakNumberMonths, doc='peak number of months'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eElePeakHourValue) > 0 or len(optmodel.eElePeakHourInd_C1) > 0 or len(optmodel.eElePeakHourInd_C2) > 0 or len(optmodel.eElePeakNumberMonths) > 0:
        log_time('--- Declaring the peak hour selection (all peaks - month):', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    ####################################################################################################################
    ####################################################################################################################

    # daily peak selection (with night discount) for pEleRetPowerTariff = Daily
    def eEleDailyPeakValue(optmodel, p,sc,d,n,er):
        # Check applicability
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (n,d) in optmodel.n2d:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 0.5 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 2.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 5.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            return optmodel.vEleDemPeakDay[p, sc, d, er] >= adjusted_buy
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDailyPeakValue', Constraint(optmodel.psdner, rule=eEleDailyPeakValue, doc='daily peak hour selection'))

    # restrict to only one daily peak per day
    def eEleDailyPeakNumber(optmodel, p,sc,d,er):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily':
            return sum(optmodel.vElePeakDayInd[p,sc,d,n,er] for n in model.n if (n,d) in optmodel.n2d) == 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDailyPeakNumber', Constraint(optmodel.psder, rule=eEleDailyPeakNumber, doc='daily peak number'))

    # link the indicator with the daily peak value
    def eEleDailyPeakInd_C1(optmodel, p,sc,d,n,er):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (n,d) in optmodel.n2d:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 0.5 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 2.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 5.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            return optmodel.vEleDemPeakDay[p,sc,d,er] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakDayInd[p,sc,d,n,er])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDailyPeakInd_C1', Constraint(optmodel.psdner, rule=eEleDailyPeakInd_C1, doc='daily peak hour indicator'))

    def eEleDailyPeakInd_C2(optmodel, p,sc,d,n,er):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (n,d) in optmodel.n2d:
            # Determine hour of day using ordinal of time index n
            hour = optmodel.n.ord(n) % 24
            # Apply night discount (22:00–06:00)
            buy_factor = 0.5 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 1.0
            sum_factor = 2.0 if (hour >= model.Par['pEleRetStartNightTime'][er] or hour <= model.Par['pEleRetEndNightTime'][er]) else 5.0
            # Adjusted electric buy variable
            if  sum(model.Par['pVarMaxDemand'][ed][p,sc,n] for ed in model.ed if (er,ed) in model.r2ed) > 0:
                adjusted_buy = buy_factor * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
            else:
                adjusted_buy = buy_factor * (optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] + sum_factor)
            # Peak-hour logic
            return optmodel.vEleDemPeakDay[p,sc,d,er] <= adjusted_buy + model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakDayInd[p,sc,d,n,er])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDailyPeakInd_C2', Constraint(optmodel.psdner, rule=eEleDailyPeakInd_C2, doc='daily peak hour indicator'))

    # Identify top peaks among daily peaks
    def eEleGlobalPeakValue(optmodel, p,sc,m,d,er,peak):
        # Check applicability
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (p,sc,d,er) in optmodel.psder:
            # Peak-hour logic
            if peak == optmodel.Peaks.first():
                return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] >= optmodel.vEleDemPeakDay[p,sc,d,er]
            else:
                return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] >= optmodel.vEleDemPeakDay[p,sc,d,er] - model.Par['pEleRetMaximumEnergySell'][er] * sum(optmodel.vElePeakMonthInd[p,sc,d,er,peak2] for peak2 in optmodel.Peaks if peak2 < peak)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleGlobalPeakValue', Constraint(optmodel.psmd, optmodel.er, optmodel.Peaks, rule=eEleGlobalPeakValue, doc='global peak hour selection from daily peaks'))

    # constraint that ensures only daily peak is selected per peak slot
    def eElePeakGlobalInd_C1(optmodel, p,sc,m,d,er,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (p,sc,d,er) in optmodel.psder:
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] >= optmodel.vEleDemPeakDay[p,sc,d,er] - model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakMonthInd[p,sc,d,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakGlobalInd_C1', Constraint(optmodel.psmd, optmodel.er, optmodel.Peaks, rule=eElePeakGlobalInd_C1, doc='global peak hour indicator from daily peaks'))

    def eElePeakGlobalInd_C2(optmodel, p,sc,d,er,m,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (p,sc,d,er) in optmodel.psder:
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] <= optmodel.vEleDemPeakDay[p,sc,d,er] + model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakMonthInd[p,sc,d,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakGlobalInd_C2', Constraint(optmodel.psd, optmodel.er, optmodel.moy, optmodel.Peaks, rule=eElePeakGlobalInd_C2, doc='global peak hour indicator from daily peaks'))

    def eElePeakNumberDays(optmodel, m,er,peak):
        if model.Par['pParNumberPowerPeaks'] > 0 and sum(model.Par['pEleRetPowerTariff'][er] for er in model.er if model.Par['pEleRetTariffType'][er] == 'Daily') > 0:
            return sum(optmodel.vElePeakMonthInd[p,sc,d,er,peak] for p,sc,d in model.psd if model.Par['pEleRetPowerTariff'][er] and (d,m) in model.d2m) == 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakNumberDays', Constraint(optmodel.moy, optmodel.er, optmodel.Peaks, rule=eElePeakNumberDays, doc='peaks from days'))

    # Each day used by at most one peak (prevents double-counting)
    # def eEleMonthDayAtMostOnePeak_rule(optmodel, p, sc, d, er, mth):
    #     if (d, mth) in model.d2m and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily':
    #         return sum(optmodel.vElePeakMonthInd[p, sc, d, er, peak] for peak in model.Peaks) <= 1
    #     else:
    #         return Constraint.Skip
    # optmodel.eEleMonthDayAtMostOnePeak = Constraint(model.psd, model.er, model.moy, rule=eEleMonthDayAtMostOnePeak_rule)

    # vGlobal[1] ≥ vGlobal[2] ≥ ... ≥ vGlobal[K]
    def eEleMonthPeakOrder_rule(optmodel, p, sc, mth, er, peak):
        # skip last peak
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and peak != model.Peaks.last():
            next_peak = model.Peaks.next(peak)
            return optmodel.vEleDemPeakGlobal[p, sc, mth, er, peak] >= optmodel.vEleDemPeakGlobal[p, sc, mth, er, next_peak]
        else:
            return Constraint.Skip
    optmodel.eEleMonthPeakOrder = Constraint(model.psm, model.er, model.Peaks, rule=eEleMonthPeakOrder_rule)

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleDailyPeakValue) > 0 or len(optmodel.eEleDailyPeakNumber) > 0 or len(optmodel.eEleDailyPeakInd_C1) > 0 or len(optmodel.eEleDailyPeakInd_C2) > 0 or len(optmodel.eEleGlobalPeakValue) > 0 or len(optmodel.eElePeakGlobalInd_C1) > 0 or len(optmodel.eElePeakGlobalInd_C2) > 0 or len(optmodel.eElePeakNumberDays) > 0:
        log_time('--- Declaring the peak hour selection (daily peaks - month):', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    def eKirchhoff2ndLaw(optmodel, p,sc,n,ni,nf,cc):
        if model.Par[('pOptIndBinSingleNode')] == 0 and model.Par['pEleNetInitialPeriod'][ni,nf,cc] <= model.Par['pParEconomicBaseYear'] and model.Par['pEleNetFinalPeriod'][ni,nf,cc] >= model.Par['pParEconomicBaseYear'] and (ni,nf,cc) in model.elea:
            return optmodel.vEleNetFlow[p,sc,n,ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] - (optmodel.vEleNetTheta[p,sc,n,ni] - optmodel.vEleNetTheta[p,sc,n,nf]) / model.Par['pEleNetReactance'][ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] * 0.1 == 0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eKirchhoff2ndLaw', Constraint(optmodel.psnela, rule=eKirchhoff2ndLaw, doc='Kirchhoff 1st Law'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eKirchhoff2ndLaw) > 0:
        log_time('--- Declaring the Kirchhoff 2nd Law:', StartTime, ind_log=indlog)

    return model