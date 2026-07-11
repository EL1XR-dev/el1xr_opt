# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import os            # env-gated model options
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
    optmodel.__setattr__('eTotalSCost', Objective(rule=eTotalSCost, sense=minimize, doc='Total system cost [money]'))

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
    optmodel.__setattr__('eTotalTCost', Constraint(rule=eTotalTCost, doc='Total system cost [money]'))

    # Cost / revenue components of the objective, summed from a registry so a new
    # cost-bearing feature registers its term instead of editing these rules. The
    # registry is seeded with the built-in terms in their original order, so the
    # aggregation is identical to the previous hard-coded sum.
    from .oM_Features import seed_objective_registry, aggregate_terms
    seed_objective_registry(model)

    def eTotalCComponent(optmodel, p,sc):
        return optmodel.vTotalCComponent[p,sc] == aggregate_terms(model, optmodel, p, sc, model._cost_terms)
    optmodel.__setattr__('eTotalCComponent', Constraint(optmodel.ps, rule=eTotalCComponent, doc='Total cost components [money]'))

    def eTotalRComponent(optmodel, p,sc):
        return optmodel.vTotalRComponent[p,sc] == aggregate_terms(model, optmodel, p, sc, model._revenue_terms)
    optmodel.__setattr__('eTotalRComponent', Constraint(optmodel.ps, rule=eTotalRComponent, doc='Total revenue components [money]'))

    log_time('--- Declaring the totals components of the ObjFunc:', StartTime, ind_log=indlog)

    return model

def create_objective_function_components(model, optmodel, indlog):
    #
    StartTime = time.time() # to compute elapsed time

    #%% Total electricity grid usage cost [M€]
    def eEleNetGridUsageCost(optmodel, p,sc):
        return optmodel.vTotalEleNCost[p,sc] == optmodel.vTotalElePeakCost[p,sc] + optmodel.vTotalEleNetUseVarCost[p,sc] + optmodel.vTotalEleNetUseFixCost[p,sc]
    optmodel.__setattr__('eNetGridUsageCost', Constraint(optmodel.ps, rule=eEleNetGridUsageCost, doc='Total electricity grid usage cost [money]'))

    # Total electricity peak costs
    def eTotalElePeakCost(optmodel, p,sc):
        if model.Par['pParNumberPowerPeaks'] == 0:
            return (optmodel.vTotalElePeakCost[p,sc] == sum(model.Par['pEleRetPowerTariff'][er] * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
        N = len(model.Peaks)
        def _ret_billed_peaks(er):
            # mean of the N highest hourly imports per month, summed over months
            if model.Par['pOptIndPeakThresholdLP'] == 1 and model.Par['pEleRetTariffType'][er] == 'Hourly':
                # CVaR/threshold form: sum_m [ t_m + (1/N) sum_{n in m} s_n ]
                return (sum(optmodel.vElePeakThreshold[p,sc,m,er] for m in model.moy)
                        + sum(optmodel.vElePeakSlack[p,sc,n,er] for n in model.n) / N)
            # legacy big-M selection form: (1/N) sum_{m,peak} ranked peak values
            return sum(optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] for peak in model.Peaks for m in model.moy) / N
        # N2T hogbelastningsavgift (second demand charge), folded into the peak-cost component:
        # pEleRetHighLoadTariff x sum_m highest-hoglasttid-hour. Zero unless the case carries the tariff.
        _hl = 'pEleRetHighLoadTariff' in model.Par
        def _ret_highload(er):
            if _hl and model.Par['pEleRetHighLoadTariff'][er]:
                return sum(optmodel.vEleHighLoadPeak[p,sc,m,er] for m in model.moy)
            return 0.0
        return (optmodel.vTotalElePeakCost[p,sc] == sum(
            (model.Par['pEleRetPowerTariff'][er] / model.factor1 * _ret_billed_peaks(er)
             + (model.Par['pEleRetHighLoadTariff'][er] / model.factor1 * _ret_highload(er) if _hl else 0.0))
            * (1 + model.Par['pEleRetMoms'][er])
            for er in model.er))
    optmodel.__setattr__('eTotalElePeakCost', Constraint(optmodel.ps, rule=eTotalElePeakCost, doc='Total electricity peak cost [money]'))

    # Total electricity net usage costs
    def eTotalEleNetUseVarCost(optmodel, p,sc):
        # volumetric grid fee per imported kWh: weight the per-level import power by
        # pDuration so it counts energy, matching the duration-weighted "psn" market
        # terms. Without it the charge undercounts by the time-step factor when
        # pParTimeStep > 1 (C15a).
        # N2T time-of-use transfer: hoglasttid rate (pEleRetOverforingHigh) on masked hours,
        # ovrig-tid rate (pEleRetOverforingsavgift) otherwise. Flat (ovrig-tid only) if the case
        # carries no hoglasttid rate column.
        _tou = 'pEleRetOverforingHigh' in model.Par
        def _ovf_rate(er, p, sc, n):
            base = model.Par['pEleRetOverforingsavgift'][er]
            if _tou and model.Par['pEleRetOverforingHigh'][er]:
                return base + (model.Par['pEleRetOverforingHigh'][er] - base) * model.Par['pEleHighLoadHour'][p,sc,n]
            return base
        return (optmodel.vTotalEleNetUseVarCost[p,sc] == sum(sum(_ovf_rate(er,p,sc,n) / model.factor1 * model.Par['pDuration'][p,sc,n] * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eTotalEleNetUseVarCost', Constraint(optmodel.ps, rule=eTotalEleNetUseVarCost, doc='Total electricity net usage cost [money]'))

    # Total electricity capacity tariff costs
    def eTotalEleNetUseFixCost(optmodel, p,sc):
        return (optmodel.vTotalEleNetUseFixCost[p,sc] == sum(model.Par['pEleRetFastavgift'][er] * sum(1 for m in model.moy) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eTotalEleNetUseFixCost', Constraint(optmodel.ps, rule=eTotalEleNetUseFixCost, doc='Total electricity capacity tariff cost [money]'))

    # Reserve delivery/settlement option (design note 2026-07-04): when ON, the day-ahead
    # energy legs settle the BASELINE position (vEleBuyBase/vEleSellBase) and the activated
    # reserve energy settles explicitly at the day-ahead price (vTotalEleActRev/Cost), tied
    # together by the delivery identity below, which forces activation across the meter.
    # When OFF (default) everything reduces to the original formulation.
    _delivery_on = int(model.Par.get('pOptIndReserveDeliverySettlement', 0)) == 1

    # site-level kappa-weighted activated reserve energy (upward delivered / downward absorbed);
    # bids of units that may not provide a product are fixed to zero in oM_InputData, so
    # unfiltered sums over the provider classes are exact.
    def _act_up(optmodel, p,sc,n):
        prov = list(model.egt) + list(model.egs) + list(model.e2h) + list(model.h2e)
        return sum(model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,g]
                 + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorBid[p,sc,n,g] for g in prov)

    def _act_dn(optmodel, p,sc,n):
        prov = list(model.egt) + list(model.egs) + list(model.e2h) + list(model.h2e)
        return sum(model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,g]
                 + model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorBid[p,sc,n,g] for g in prov)

    #%% Total electricity market costs
    def eEleMarketCost(optmodel, p,sc,n):
        if _delivery_on:
            return (optmodel.vTotalEleMCost[p,sc,n] == optmodel.vTotalEleMrkDACost[p,sc,n] + optmodel.vTotalEleMrkPPACost[p,sc,n] + optmodel.vTotalEleActCost[p,sc,n])
        return (optmodel.vTotalEleMCost[p,sc,n] == optmodel.vTotalEleMrkDACost[p,sc,n] + optmodel.vTotalEleMrkPPACost[p,sc,n])
    optmodel.__setattr__('eEleMarketCost', Constraint(optmodel.psn, rule=eEleMarketCost, doc='Total electricity market costs [money]'))

    def eEleMarketDayAheadCost(optmodel, p,sc,n):
        if _delivery_on:
            # full retail buy price (spot + paslag) on the BASELINE buy position. Keeping the
            # markup on the baseline (not the metered) leg makes a simultaneous baseline
            # buy+sell (a wash position) cost the markup, so the delivery identity cannot be
            # satisfied by free wash trades and activation must genuinely move the position.
            return optmodel.vTotalEleMrkDACost[p,sc,n] == sum((model.Par['pVarEnergyCost'][er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetPaslag'][er] / model.factor1) * optmodel.vEleBuyBase[p,sc,n,er] * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
        return optmodel.vTotalEleMrkDACost[p,sc,n] == sum((model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetPaslag'][er] / model.factor1) * (optmodel.vEleBuy[p,sc,n,er]) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
    optmodel.__setattr__('eEleMarketDayAheadCost', Constraint(optmodel.psn, rule=eEleMarketDayAheadCost, doc='Total electricity trade cost [money]'))

    #%% Total electricity market revenues
    def eEleMarketRevenue(optmodel, p,sc,n):
        if _delivery_on:
            return (optmodel.vTotalEleMRev[p,sc,n] == optmodel.vTotalEleMrkDARev[p,sc,n] + optmodel.vTotalEleMrkPPARev[p,sc,n] + optmodel.vTotalEleMrkFrqRev[p,sc,n] + optmodel.vTotalEleActRev[p,sc,n])
        return (optmodel.vTotalEleMRev[p,sc,n] == optmodel.vTotalEleMrkDARev[p,sc,n] + optmodel.vTotalEleMrkPPARev[p,sc,n] + optmodel.vTotalEleMrkFrqRev[p,sc,n])
    optmodel.__setattr__('eEleMarketRevenue', Constraint(optmodel.psn, rule=eEleMarketRevenue, doc='Total electricity market revenues [money]'))

    def eEleMarketDayAheadRevenue(optmodel, p,sc,n):
        if _delivery_on:
            return optmodel.vTotalEleMrkDARev[p,sc,n] == sum(model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] * (optmodel.vEleSellBase[p,sc,n,er]) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
        return optmodel.vTotalEleMrkDARev[p,sc,n] == sum(model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] * (optmodel.vEleSell[p,sc,n,er]) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er)
    optmodel.__setattr__('eEleMarketDayAheadRevenue', Constraint(optmodel.psn, rule=eEleMarketDayAheadRevenue, doc='Total electricity market day-ahead revenues [money]'))

    if _delivery_on:
        # activation-energy settlement at the day-ahead proxy (retailer-averaged price;
        # exact for the single-retailer case, documented caveat for multi-retailer).
        _n_er = max(len(model.er), 1)

        def eEleActUpRevenue(optmodel, p,sc,n):
            _p_sell = sum(model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] * (1 + model.Par['pEleRetMoms'][er]) for er in model.er) / _n_er
            return optmodel.vTotalEleActRev[p,sc,n] == _p_sell * _act_up(optmodel, p,sc,n)
        optmodel.__setattr__('eEleActUpRevenue', Constraint(optmodel.psn, rule=eEleActUpRevenue, doc='Upward reserve activation energy settled at the DA price [money]'))

        def eEleActDownCost(optmodel, p,sc,n):
            _p_buy = sum(model.Par['pVarEnergyCost'][er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] * (1 + model.Par['pEleRetMoms'][er]) for er in model.er) / _n_er
            return optmodel.vTotalEleActCost[p,sc,n] == _p_buy * _act_dn(optmodel, p,sc,n)
        optmodel.__setattr__('eEleActDownCost', Constraint(optmodel.psn, rule=eEleActDownCost, doc='Downward reserve activation energy settled at the DA price [money]'))

        # Delivery identity: the metered exchange equals the baseline position shifted by the
        # net activated reserve energy of the whole site, so a held bid's activation must
        # cross the meter (internal re-routing, e.g. absorbing own curtailed wind, does not
        # count as delivery). With no bids this collapses to metered == baseline.
        def eEleActivationDelivery(optmodel, p,sc,n):
            return sum(optmodel.vEleBuy[p,sc,n,er] - optmodel.vEleSell[p,sc,n,er] for er in model.er) == \
                   sum(optmodel.vEleBuyBase[p,sc,n,er] - optmodel.vEleSellBase[p,sc,n,er] for er in model.er) \
                   + _act_dn(optmodel, p,sc,n) - _act_up(optmodel, p,sc,n)
        optmodel.__setattr__('eEleActivationDelivery', Constraint(optmodel.psn, rule=eEleActivationDelivery, doc='Metered exchange = baseline position + net activated reserve energy [kW]'))

    def eEleMarketFrequencyRevenue(optmodel, p,sc,n):
        return optmodel.vTotalEleMrkFrqRev[p,sc,n] == optmodel.vTotalEleFCRDUpRev[p,sc,n] + optmodel.vTotalEleFCRDDwRev[p,sc,n] + optmodel.vTotalEleFCRNRev[p,sc,n]
    optmodel.__setattr__('eEleMarketFrequencyRevenue', Constraint(optmodel.psn, rule=eEleMarketFrequencyRevenue, doc='Total electricity market frequency revenues [money]'))

    def eEleMarketFCRDUpRevenue(optmodel, p,sc,n):
        # the FCR price is already factor1-scaled at read (oM_InputData), like the
        # day-ahead energy price, so it must NOT be multiplied by factor1 again here
        # (that squared it on the unit knob; latent at factor1=1) -- C16.
        # Pay revenue only over the backed FCR providers (egt / egs / e2h), the same sets
        # the caps and bid-provision relations cover. Summing over all of egnr would also
        # pay a non-RES unit that is neither thermal nor storage -- it has a bid variable
        # but no cap, no provision and is never fixed, so its bid would be free and the
        # paid revenue would make the objective unbounded (C17).
        return optmodel.vTotalEleFCRDUpRev[p,sc,n] == sum((model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egt]) for egt in model.egt) + sum((model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs]) for egs in model.egs) + sum((model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,e2h]) for e2h in model.e2h) + sum((model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e]) for h2e in model.h2e if model.Par['pEleGenNoFCRD'][h2e] == 0)
    optmodel.__setattr__('eEleMarketFCRDUpRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRDUpRevenue, doc='Total electricity market FCR-D upwards revenues [money]'))

    def eEleMarketFCRDDwRevenue(optmodel, p,sc,n):
        # backed providers only (egt / egs / e2h), as in eEleMarketFCRDUpRevenue (C17)
        return optmodel.vTotalEleFCRDDwRev[p,sc,n] == sum((model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egt]) for egt in model.egt) + sum((model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs]) for egs in model.egs) + sum((model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,e2h]) for e2h in model.e2h) + sum((model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,h2e]) for h2e in model.h2e if model.Par['pEleGenNoFCRD'][h2e] == 0)
    optmodel.__setattr__('eEleMarketFCRDDwRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRDDwRevenue, doc='Total electricity market FCR-D downwards revenues [money]'))

    def eEleMarketFCRNRevenue(optmodel, p,sc,n):
        # backed providers only (egt / egs / e2h), as in eEleMarketFCRDUpRevenue (C17)
        return optmodel.vTotalEleFCRNRev[p,sc,n] == sum(((model.Par['pOperatingReservePrice_FCRN_Up'][p,sc,n] + model.Par['pOperatingReservePrice_FCRN_Down'][p,sc,n]) / 2 * optmodel.vEleFreqContReserveNorBid[p,sc,n,egt]) for egt in model.egt) + sum(((model.Par['pOperatingReservePrice_FCRN_Up'][p,sc,n] + model.Par['pOperatingReservePrice_FCRN_Down'][p,sc,n]) / 2 * optmodel.vEleFreqContReserveNorBid[p,sc,n,egs]) for egs in model.egs) + sum(((model.Par['pOperatingReservePrice_FCRN_Up'][p,sc,n] + model.Par['pOperatingReservePrice_FCRN_Down'][p,sc,n]) / 2 * optmodel.vEleFreqContReserveNorBid[p,sc,n,e2h]) for e2h in model.e2h) + sum(((model.Par['pOperatingReservePrice_FCRN_Up'][p,sc,n] + model.Par['pOperatingReservePrice_FCRN_Down'][p,sc,n]) / 2 * optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e]) for h2e in model.h2e if model.Par['pEleGenNoFCRN'][h2e] == 0)
    optmodel.__setattr__('eEleMarketFCRNRevenue', Constraint(optmodel.psn, rule=eEleMarketFCRNRevenue, doc='Total electricity market FCR-N revenues [money]'))

    #%% Total hydrogen market costs
    def eHydMarketCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydMCost[p,sc,n] == optmodel.vTotalHydMrkPPACost[p,sc,n])
    optmodel.__setattr__('eHydMarketCost', Constraint(optmodel.psn, rule=eHydMarketCost, doc='Total hydrogen market costs [money]'))

    # Audit C44: this rule defines the hydrogen day-ahead BUY cost. The constraint attribute
    # is named to match its rule and the electricity analogue eEleMarketDayAheadCost (it was
    # mis-registered as 'eTotalHydTradeCost'). The destination variable vTotalHydMrkPPACost
    # holds this day-ahead trade cost -- the "PPA" in its name is historical (a separate
    # hydrogen PPA term was never split out); the variable rename is deferred to avoid
    # touching the objective registry and result-table column names.
    def eHydMarketDayAheadCost(optmodel, p,sc,n):
        return optmodel.vTotalHydMrkPPACost[p,sc,n] == sum(model.Par['pVarEnergyCost'][hr][p,sc,n] * optmodel.vHydBuy[p,sc,n,hr] for hr in model.hr)
    optmodel.__setattr__('eHydMarketDayAheadCost', Constraint(optmodel.psn, rule=eHydMarketDayAheadCost, doc='Total hydrogen trade cost [money]'))

    #%% Total hydrogen market revenues
    def eHydMarketRevenue(optmodel, p,sc,n):
        return (optmodel.vTotalHydMRev[p,sc,n] == optmodel.vTotalHydMrkPPARev[p,sc,n])
    optmodel.__setattr__('eHydMarketRevenue', Constraint(optmodel.psn, rule=eHydMarketRevenue, doc='Total hydrogen market revenues [money]'))

    def eHydMarketDayAheadRevenue(optmodel, p,sc,n):
        return optmodel.vTotalHydMrkPPARev[p,sc,n] == sum(model.Par['pVarEnergyPrice'][hr][p,sc,n] * optmodel.vHydSell[p,sc,n,hr] for hr in model.hr)
    optmodel.__setattr__('eHydMarketDayAheadRevenue', Constraint(optmodel.psn, rule=eHydMarketDayAheadRevenue, doc='Total hydrogen market day-ahead revenues [money]'))

    #%% Total electricity taxes costs
    def eEleTaxCost(optmodel, p,sc):
        return (optmodel.vTotalEleXCost[p,sc] == optmodel.vTotalEleEnergyTaxCost[p,sc])
    optmodel.__setattr__('eEleTaxCost', Constraint(optmodel.ps, rule=eEleTaxCost, doc='Total electricity taxes costs [money]'))

    # VAT on electricity taxes costs
    def eEleTaxEnergyCost(optmodel, p,sc):
        return (optmodel.vTotalEleEnergyTaxCost[p,sc] == sum(model.Par['pEleRetEnergyTax'][er] / model.factor1 * sum(model.Par['pDuration'][p,sc,n] * optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) * (1 + model.Par['pEleRetMoms'][er]) for er in model.er))
    optmodel.__setattr__('eEleTaxEnergyCost', Constraint(optmodel.ps, rule=eEleTaxEnergyCost, doc='Total electricity taxes costs [money]'))

    def eEleTaxRevenue(optmodel, p,sc):
        return (optmodel.vTotalEleXRev[p,sc] == optmodel.vTotalEleISRev[p,sc])
    optmodel.__setattr__('eEleTaxRevenue', Constraint(optmodel.ps, rule=eEleTaxRevenue, doc='Total electricity taxes revenues [money]'))

    # Incentives on electricity taxes revenues
    def eEleTaxISRevenue(optmodel, p,sc):
        return (optmodel.vTotalEleISRev[p,sc] == sum(model.Par['pEleRetIncentive'][er] / model.factor1 * sum(model.Par['pDuration'][p,sc,n] * optmodel.vEleExport[p, sc, n, model.Par['pEleRetNode'][er]] for n in model.n) for er in model.er))
    optmodel.__setattr__('eEleTaxISRevenue', Constraint(optmodel.ps, rule=eEleTaxISRevenue, doc='Total electricity taxes revenues [money]'))

    #%% Total electricity operation and maintenance costs
    def eEleOpMaintCost(optmodel, p,sc,n):
        return (optmodel.vTotalEleOCost[p,sc,n] == sum(optmodel.__getattribute__(f'vTotal{eng}GCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}ECost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}CCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}RCost')[p,sc,n] for eng in ['Ele']))
    optmodel.__setattr__('eEleOpMaintCost', Constraint(optmodel.psn, rule=eEleOpMaintCost, doc='Total electricity operation and maintenance costs [money]'))

    # Electricity generation operation cost [M€]
    def eTotalEleGCost(optmodel, p,sc,n):
        # No-load (ConstantVarCost) is a money/h cost while committed, so it stays here and
        # is correctly duration-weighted by the psn aggregation. The per-event start-up /
        # shut-down costs were moved to eTotalEleSUCost (a ps term) so they are NOT
        # duration-weighted -- a start at a k-hour level is one start, not k (C15b).
        return optmodel.vTotalEleGCost[p,sc,n] == (sum(model.Par['pEleGenLinearVarCost'  ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ) +
                                                   sum(model.Par['pEleGenConstantVarCost'][egt] *       optmodel.vEleGenCommitment     [p,sc,n,egt] for egt in model.egt) +
                                                   sum(model.Par['pEleGenOMVariableCost' ][eg ] *       optmodel.vEleTotalOutput       [p,sc,n,eg ] for eg  in model.eg ) +
                                                   # M3: battery cycle-ageing throughput cost -- a stack-wear PRICE per kWh DISCHARGED. It
                                                   # captures the sub-daily FCR micro-cycling that the daily depth-of-discharge segment cost
                                                   # (vTotalEleDCost) does not see -- the daily DoD only counts the day's max-min swing, so
                                                   # FCR's within-day cycling is otherwise free. Per-kWh cost from the DoD/cycle-life curve
                                                   # (Ghanaee et al. 2026) and grid-battery replacement capex; default 0 so other cases are unchanged.
                                                   sum(model.Par['pEleGenDegradationCost'][egs] *       optmodel.vEleTotalOutput       [p,sc,n,egs] for egs in model.egs) +
                                                   # M3b: rate-dependent battery wear -- an EXTRA per-kWh degradation cost on the high-power
                                                   # 2nd discharge block (vEleTotalOutput2ndBlock), the convex, increasing-marginal analogue of
                                                   # the electrolyser's M2 load surcharge. Captures faster capacity fade at high C-rate /
                                                   # aggressive FCR activation that the flat throughput price (M3) misses. A 2-piece convex
                                                   # piecewise-linear wear cost that stays LP/MILP. Default 0 (param pre-loaded) so cases are unchanged.
                                                   sum(model.Par['pEleGenDegradationCost2ndBlock'][egs] * optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] for egs in model.egs))
    optmodel.__setattr__('eTotalEleGCost', Constraint(optmodel.psn, rule=eTotalEleGCost, doc='Total electricity generation cost [money]'))

    # Electricity start-up / shut-down cost [M€] -- per-event, summed over the load
    # levels WITHOUT pDuration (registered as a 'ps' objective term) so a start at a
    # k-hour level costs one start-up, not k (C15b).
    def eTotalEleSUCost(optmodel, p,sc):
        return optmodel.vTotalEleSUCost[p,sc] == sum(sum(model.Par['pEleGenStartUpCost' ][egt] * optmodel.vEleGenStartUp [p,sc,n,egt] +
                                                         model.Par['pEleGenShutDownCost'][egt] * optmodel.vEleGenShutDown[p,sc,n,egt] for egt in model.egt) for n in model.n)
    optmodel.__setattr__('eTotalEleSUCost', Constraint(optmodel.ps, rule=eTotalEleSUCost, doc='Total electricity start-up/shut-down cost [money]'))

    # Electricity generation emission cost [M€]
    def eTotalEleECost(optmodel, p,sc,n):
        return optmodel.vTotalEleECost[p,sc,n] == sum(model.Par['pGenCO2EmissionCost'][egt] * optmodel.vEleTotalOutput[p,sc,n,egt] for egt in model.egt)
    optmodel.__setattr__('eTotalECost', Constraint(optmodel.psn, rule=eTotalEleECost, doc='Total emission cost [money]'))

    # Electricity consumption operation cost [M€]
    def eTotalEleCCost(optmodel, p,sc,n):
        return optmodel.vTotalEleCCost[p,sc,n] == sum(model.Par['pEleGenLinearTerm'][egs] * optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs)
    optmodel.__setattr__('eTotalEleCCost', Constraint(optmodel.psn, rule=eTotalEleCCost, doc='Total consumption cost in electricity units [money]'))

    # Electricity storage degradation cost [M€]
    def eTotalEleDCost(optmodel, p,sc,d):
        return optmodel.vTotalEleDCost[p,sc,d] == sum(model.Par['pEleGenDoDC1'][egs] * optmodel.vEleInventoryDoDS1Day[p,sc,d,egs] + model.Par['pEleGenDoDC2'][egs] * optmodel.vEleInventoryDoDS2Day[p,sc,d,egs] + model.Par['pEleGenDoDC3'][egs] * optmodel.vEleInventoryDoDS3Day[p,sc,d,egs] for egs in model.egs)
    optmodel.__setattr__('eTotalEleDCost', Constraint(optmodel.psd, rule=eTotalEleDCost, doc='Total degradation cost in electricity storage units [money]'))

    # Electricity reliability cost [M€]
    def eTotalEleRCost(optmodel, p,sc,n):
        # Energy not served is a power per load level, like the other O&M sub-terms
        # (generation / emission / consumption). The duration weighting is applied once
        # by the psn objective aggregation of vTotalEleOCost (oM_Features.aggregate_terms),
        # so it must NOT be applied here too -- doing so weighted ENS by pDuration**2
        # while its siblings were weighted by pDuration once. See docs/model_audit.md.
        return (optmodel.vTotalEleRCost[p,sc,n] == sum(model.Par['pParENSCost'] * optmodel.vENS[p,sc,n,ed] for ed in model.ed))
    optmodel.__setattr__('eTotalEleRCost', Constraint(optmodel.psn, rule=eTotalEleRCost, doc='Total reliability cost in electricity consumers [money]'))

    #%% Total hydrogen operation and maintenance costs
    def eHydOpMaintCost(optmodel, p,sc,n):
        return (optmodel.vTotalHydOCost[p,sc,n] == sum(optmodel.__getattribute__(f'vTotal{eng}GCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}CCost')[p,sc,n] + optmodel.__getattribute__(f'vTotal{eng}RCost')[p,sc,n] for eng in ['Hyd']))
    optmodel.__setattr__('eHydOpMaintCost', Constraint(optmodel.psn, rule=eHydOpMaintCost, doc='Total hydrogen operation and maintenance costs [money]'))

    # Hydrogen generation operation cost [M€]
    def eTotalHydGCost(optmodel, p,sc,n):
        # As on the electricity side (C15b): no-load stays here (duration-weighted money/h);
        # the per-event start-up / shut-down costs moved to eTotalHydSUCost (a ps term).
        return optmodel.vTotalHydGCost[p,sc,n] == (sum(model.Par['pHydGenLinearVarCost'  ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ) +
                                                   sum(model.Par['pHydGenConstantVarCost'][hgt] *       optmodel.vHydGenCommitment     [p,sc,n,hgt] for hgt in model.hgt) +
                                                   sum(model.Par['pHydGenOMVariableCost' ][hg ] *       optmodel.vHydTotalOutput       [p,sc,n,hg ] for hg  in model.hg ) +
                                                   # Degradation (audit Phase B / B2): stack-wear cost per kWh of PRODUCTIVE electricity
                                                   # (input minus the standby draw, which makes no hydrogen) -- the real cost of flexible
                                                   # operation, amortising stack replacement over throughput. Zero for non-electrolysers.
                                                   sum(model.Par['pHydGenDegradationCost'][e2h] * (optmodel.vEleTotalCharge[p,sc,n,e2h] - model.Par['pHydGenStandByPower'][e2h] * optmodel.vHydGenStandBy[p,sc,n,e2h]) for e2h in model.e2h) +
                                                   # M2: load-dependent degradation surcharge -- an EXTRA stack-wear cost on the high-load
                                                   # (2nd-block) consumption, a piecewise-linear stand-in for the current-density-dependent
                                                   # voltage rise (the stack degrades faster at higher load, so flexing up for FCR-down and
                                                   # running hard costs more than throughput alone implies). Zero by default (audit M2).
                                                   sum(model.Par['pHydGenDegradationCost2ndBlock'][e2h] * optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] for e2h in model.e2h) +
                                                   # M2b: cycling-degradation cost on |delta productive consumption| (the FCR-modulation stress
                                                   # the throughput term misses); active only when a unit carries RampDegradationCost > 0.
                                                   (sum(model.Par['pHydGenRampDegradationCost'][e2h] * optmodel.vHydGenRampAbs[p,sc,n,e2h] for e2h in model.e2h) if getattr(model, '_ramp_deg_active', False) and n != model.n.first() else 0) -
                                                   # Byproduct valorisation CREDIT (O2 to aquaculture + waste heat to district heating, per the
                                                   # HiWhyV valley) per kgH2 produced -- a revenue, so SUBTRACTED from the generation cost.
                                                   # Zero by default (pHydGenByproductCredit defaults to 0), so other cases are unchanged.
                                                   sum(model.Par['pHydGenByproductCredit'][e2h] * optmodel.vHydTotalOutput[p,sc,n,e2h] for e2h in model.e2h))
    optmodel.__setattr__('eTotalHydGCost', Constraint(optmodel.psn, rule=eTotalHydGCost, doc='Total hydrogen generation cost [money]'))

    # M2b: linearise |delta productive consumption| for the electrolyser cycling-degradation cost.
    # productive consumption = vEleTotalCharge - StandByPower * vHydGenStandBy; vHydGenRampAbs >=
    # |prod[n] - prod[n-1]| via the two one-sided constraints. Built only when active.
    if getattr(model, '_ramp_deg_active', False):
        def _prod(optmodel, p, sc, n, e2h):
            return optmodel.vEleTotalCharge[p,sc,n,e2h] - model.Par['pHydGenStandByPower'][e2h] * optmodel.vHydGenStandBy[p,sc,n,e2h]
        def eHydRampDegradationUp(optmodel, p, sc, n, e2h):
            if n == model.n.first():
                return Constraint.Skip
            return optmodel.vHydGenRampAbs[p,sc,n,e2h] >= _prod(optmodel,p,sc,n,e2h) - _prod(optmodel,p,sc,model.n.prev(n),e2h)
        optmodel.__setattr__('eHydRampDegradationUp', Constraint(optmodel.psne2h, rule=eHydRampDegradationUp, doc='electrolyser cycling: ramp-abs >= +delta consumption [kW]'))
        def eHydRampDegradationDn(optmodel, p, sc, n, e2h):
            if n == model.n.first():
                return Constraint.Skip
            return optmodel.vHydGenRampAbs[p,sc,n,e2h] >= _prod(optmodel,p,sc,model.n.prev(n),e2h) - _prod(optmodel,p,sc,n,e2h)
        optmodel.__setattr__('eHydRampDegradationDn', Constraint(optmodel.psne2h, rule=eHydRampDegradationDn, doc='electrolyser cycling: ramp-abs >= -delta consumption [kW]'))

    # Hydrogen start-up / shut-down cost [M€] -- per-event, summed over the load levels
    # WITHOUT pDuration (a 'ps' objective term). The e2h start-up and shut-down terms cover an
    # electrolyser outside hgt (an electrolyser with ConstantTerm 0 is not in hgt; B2), so its
    # cold-start and shut-down costs are still billed -- previously only the start-up was, which
    # under-counted the cost of cycling such a unit.
    def eTotalHydSUCost(optmodel, p,sc):
        return optmodel.vTotalHydSUCost[p,sc] == sum(sum(model.Par['pHydGenStartUpCost' ][hgt] * optmodel.vHydGenStartUp [p,sc,n,hgt] for hgt in model.hgt) +
                                                     sum(model.Par['pHydGenStartUpCost' ][e2h] * optmodel.vHydGenStartUp [p,sc,n,e2h] for e2h in model.e2h if e2h not in model.hgt) +
                                                     sum(model.Par['pHydGenShutDownCost'][hgt] * optmodel.vHydGenShutDown[p,sc,n,hgt] for hgt in model.hgt) +
                                                     sum(model.Par['pHydGenShutDownCost'][e2h] * optmodel.vHydGenShutDown[p,sc,n,e2h] for e2h in model.e2h if e2h not in model.hgt) for n in model.n)
    optmodel.__setattr__('eTotalHydSUCost', Constraint(optmodel.ps, rule=eTotalHydSUCost, doc='Total hydrogen start-up/shut-down cost [money]'))

    # Hydrogen consumption operation cost [M€]
    def eTotalHydCCost(optmodel, p,sc,n):
        return optmodel.vTotalHydCCost[p,sc,n] == sum(model.Par['pHydGenLinearTerm'][hgs] * optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs)
    optmodel.__setattr__('eTotalHydCCost', Constraint(optmodel.psn, rule=eTotalHydCCost, doc='Total consumption cost in hydrogen units [money]'))

    # Hydrogen reliability cost [M€], net of per-demand sale revenue.
    def eTotalHydRCost(optmodel, p,sc,n):
        # Hydrogen not served: same fix as the electricity reliability cost above --
        # the psn aggregation supplies the single duration weight. See docs/model_audit.md.
        # Per-demand price (pHydDemPrice, default 0): the served quantity
        # (vHydDemand - vHNS) earns the demand's own price as REVENUE, so different
        # consumer sectors can be sold hydrogen at different prices. With price 0 this
        # reduces to the original not-served penalty (existing cases unchanged).
        return (optmodel.vTotalHydRCost[p,sc,n] == sum(
            model.Par['pParHNSCost'] * optmodel.vHNS[p,sc,n,hd]
            - model.Par['pHydDemPrice'][hd] * (optmodel.vHydDemand[p,sc,n,hd] - optmodel.vHNS[p,sc,n,hd])
            for hd in model.hd))
    optmodel.__setattr__('eTotalHydRCost', Constraint(optmodel.psn, rule=eTotalHydRCost, doc='Total reliability cost in hydrogen consumers [money]'))

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
    # Demand-to-node maps: a node that carries only demand (no unit or line) must
    # still get a balance, otherwise its demand is silently dropped at zero cost.
    ed2n = defaultdict(list)
    for nd,ed in model.nd*model.ed:
        if (nd,ed) in model.n2ed:
            ed2n[nd].append(ed)
    hd2n = defaultdict(list)
    for nd,hd in model.nd*model.hd:
        if (nd,hd) in model.n2hd:
            hd2n[nd].append(hd)

    # Cross-sector electricity coupling at each node: heat pumps (htp) draw electricity,
    # heat-to-power units (htw) inject it, and charging a hydrogen store draws compressor
    # electricity. These enter the physical balance (eEleBalance) AND, so that audit C14's
    # import == buy coupling holds, the commercial retail balance (eEleRetNodeBalance) -- the
    # retailer pays for the electricity its heat pump / compressor consumes. All are empty
    # (and the terms are zero) for a case without heat or compression.
    _htp_set = set(getattr(model, "htp", []) or [])
    _htp_at = defaultdict(list)
    for (_nd, _g) in getattr(model, "n2htg", []):
        if _g in _htp_set:
            _htp_at[_nd].append(_g)
    _htw_at = defaultdict(list)
    for (_nd, _w) in getattr(model, "n2htw", []):
        _htw_at[_nd].append(_w)
    _comp_at = defaultdict(list)
    for nd in model.nd:
        for hgs in hgs2n[nd]:
            if model.Par['pHydGenMaxCompressorConsumption'][hgs] > 0:
                _comp_at[nd].append(hgs)
    # Standalone compressors (model.hc): a compressor withdraws H2 from its suction node
    # (InitialNode), injects Efficiency x throughput into its discharge node (FinalNode), and
    # draws electricity at the suction node -- the electrified low-pressure side where it wires
    # to the grid. All three maps are empty without a dfHydrogenCompressor input, so the terms
    # they drive are zero and existing cases are unchanged.
    # Physical draw lands on the suction node (n-based, eEleBalance); the commercial charge goes
    # to the compressor's assigned retailer (r-based, eEleRetNodeBalance), exactly like an
    # electrolyser (physical at n2hg, commercial at r2hg). The two reconcile through the network
    # and the import == buy coupling, so the retailer need not sit at the suction node.
    _hcomp_elec_at = defaultdict(list)   # compressors drawing electricity at node nd (suction side)
    _hcomp_suct_at = defaultdict(list)   # compressors withdrawing H2 from node nd (suction)
    _hcomp_disc_at = defaultdict(list)   # compressors injecting H2 into  node nd (discharge)
    _hcomp_at_er   = defaultdict(list)   # compressors whose electricity is billed to retailer er
    for hc in getattr(model, 'hc', []):
        _hcomp_elec_at[model.Par['pHydGenNode'         ][hc]].append(hc)
        _hcomp_suct_at[model.Par['pHydGenNode'         ][hc]].append(hc)
        _hcomp_disc_at[model.Par['pHydGenDischargeNode'][hc]].append(hc)
        _hcomp_at_er  [model.Par['pHydGenRetailer'     ][hc]].append(hc)
    # The cross-sector loads belong to the node, but C14 sums every retailer's buy at the
    # node; charge them to a single retailer per node so the sum is not double-counted when
    # two retailers share a node (e.g. an energy community).
    _first_er_at = {}
    for er in model.er:
        _first_er_at.setdefault(model.Par['pEleRetNode'][er], er)

    #%% Constraints
    # Energy-community sharing terms enter the retail balance like buy/sell but
    # internal to the community; the term is absent unless the community layer is
    # on, so existing cases build an identical constraint.
    community_on = bool(model.Par.get('pOptIndBinCommunity', 0))

    # Audit C14: this is the COMMERCIAL per-retailer balance (the retailer's assigned
    # generation/demand/charge closed by vEleBuy/vEleSell). The PHYSICAL nodal balance with
    # line flows and grid import/export is eEleBalance below. The two layers are tied together
    # by eEleImportBuyLink / eEleExportSellLink (below), which couple the retail buy/sell to the
    # grid import/export at the electricity reference node; see docs/model_audit.md C14.
    def eEleRetNodeBalance(optmodel, p,sc,n,er):
        nd = model.Par['pEleRetNode'][er]
        # cross-sector electricity (heat pump / heat-to-power / compressor) at this node,
        # charged to the first retailer at the node so the retailer's buy reflects it and
        # audit C14's import == buy holds. Zero for a case without heat or compression.
        first = (er == _first_er_at.get(nd))
        xsec = ((heat_to_power_output(optmodel, _htw_at[nd], p, sc, n)
                 - heat_electricity_load(optmodel, _htp_at[nd], p, sc, n)
                 - sum(model.Par['pHydGenMaxCompressorConsumption'][hgs] * optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in _comp_at[nd]))
                if first else 0.0)
        # Standalone compressor electricity is billed to its assigned retailer (r-based), like an
        # electrolyser's charge above -- independent of which retailer is "first" at the node.
        comp_er = sum(model.Par['pHydGenMaxCompressorConsumption'][hc] * optmodel.vHydCompFlow[p,sc,n,hc] for hc in _hcomp_at_er[er])
        if (sum(1 for eg in eg2n[nd]) + sum(1 for egs in egs2n[nd]) + sum(1 for nf, cc in lout[nd]) + sum(1 for ni, cc in lin[nd])
                + len(_hcomp_at_er[er])
                + (len(_htp_at[nd]) + len(_htw_at[nd]) + len(_comp_at[nd]) if first else 0)):
            share = (optmodel.vEleShareIn[p,sc,n,er] - optmodel.vEleShareOut[p,sc,n,er]) if community_on else 0.0
            return (sum(optmodel.vEleTotalOutput[p,sc,n,egr] for egr in model.egr  if (er,egr) in model.r2eg) + sum(optmodel.vEleGenCommitment[p,sc,n,egt] * model.Par['pEleMinPower'][egt][p,sc,n] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] for egt in model.egt if (er,egt) in model.r2eg) + sum(optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg)
                    - sum(optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] for egs in model.egs if (er,egs) in model.r2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,e2h] for e2h in model.e2h if (er,e2h) in model.r2hg)
                    + optmodel.vEleBuy[p,sc,n,er] - optmodel.vEleSell[p,sc,n,er] + share + xsec - comp_er == sum(optmodel.vEleDemand[p,sc,n,ed] - optmodel.vENS[p,sc,n,ed] for ed in model.ed if (er,ed) in model.r2ed))
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

    # Audit C14: couple the commercial layer (vEleBuy/vEleSell, which carry the day-ahead
    # energy cost) to the physical layer (vEleImport/vEleExport at the reference node, which
    # carry the grid-transfer fee and energy tax). All external trade crosses the electricity
    # reference node -- import/export are fixed to zero at every other node in network mode --
    # so the grid import equals the sum of every retailer's buy and the grid export equals the
    # sum of every retailer's sell. This is the finished form of the old eEleBuyComposition
    # stub: it makes the energy-cost base and the grid-fee base the same physical quantity and
    # is correct for one or more retailers. (For a single retailer that owns the whole portfolio
    # the retail and physical balances already drive buy to the net grid draw, so this is
    # non-binding there; it becomes load-bearing once multiple retailers transact at the grid.)
    def eEleImportBuyLink(optmodel, p,sc,n,nd):
        if nd in model.endrf and len(model.er) > 0:
            return optmodel.vEleImport[p,sc,n,nd] == sum(optmodel.vEleBuy[p,sc,n,er] for er in model.er)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleImportBuyLink', Constraint(optmodel.psnnd, rule=eEleImportBuyLink, doc='Couple grid import to retail buy at the reference node (C14) [kW]'))

    def eEleExportSellLink(optmodel, p,sc,n,nd):
        if nd in model.endrf and len(model.er) > 0:
            return optmodel.vEleExport[p,sc,n,nd] == sum(optmodel.vEleSell[p,sc,n,er] for er in model.er)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleExportSellLink', Constraint(optmodel.psnnd, rule=eEleExportSellLink, doc='Couple grid export to retail sell at the reference node (C14) [kW]'))

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

    # Hydrogen demand shift: load shifting that preserves the per-window total. The
    # hydrogen analogue of the electricity demand shift above. The scheduled demand equals
    # the profile plus a bounded deviation (eHydDemandShifted), and over each window of
    # pHydDemShiftedSteps load levels the total scheduled demand equals the total profile
    # (eHydDemandShiftBalance) -- so the day/week/month volume is unchanged and only the
    # timing moves. Both Skip (no-op) unless pHydDemShiftedSteps is set, so existing cases
    # are unchanged.
    def eHydDemandShifted(optmodel, p,sc,n,hd):
        if model.Par['pHydDemShiftedSteps'][hd] > 0:
            return optmodel.vHydDemand[p,sc,n,hd] == model.Par['pVarMaxDemand'][hd][p,sc,n] + optmodel.vHydDemFlex[p,sc,n,hd]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydDemandShifted', Constraint(optmodel.psnhd, rule=eHydDemandShifted, doc='Hydrogen demand after shifting [kgH2]'))

    def eHydDemandShiftBalance(optmodel, p,sc,n,hd):
        steps = model.Par['pHydDemShiftedSteps'][hd]
        if steps > 0 and model.n.ord(n) % steps == 0:
            window = n2_list[model.n.ord(n) - steps:model.n.ord(n)]
            return sum(optmodel.vHydDemand[p,sc,n2,hd] for n2 in window) == sum(model.Par['pVarMaxDemand'][hd][p,sc,n2] for n2 in window)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydDemandShiftBalance', Constraint(optmodel.psnhd, rule=eHydDemandShiftBalance, doc='Hydrogen demand shift balance [kgH2]'))

    # Hydrogen not served cannot exceed the hydrogen demand actually scheduled.
    # Flexible hydrogen demand is a curtailable range [min, max] (the hydrogen demand
    # file carries no shift parameter, so there is no electricity-style recovery
    # balance); without this cap vHydDemand - vHNS can go negative and the demand node
    # becomes a paid hydrogen sink. For fixed demand vHydDemand == max, so the cap is
    # implied by the vHNS <= max bound and adds nothing.
    def eHydNotServedCap(optmodel, p,sc,n,hd):
        if model.Par['pHydDemFlexible'][hd] == 1.0:
            return optmodel.vHNS[p,sc,n,hd] <= optmodel.vHydDemand[p,sc,n,hd]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydNotServedCap', Constraint(optmodel.psnhd, rule=eHydNotServedCap, doc='Hydrogen not served capped by scheduled demand [kgH2]'))

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

    # electrical energy conservation or balance. The cross-sector node maps (_htp_at,
    # _htw_at, _comp_at) are built once before the retail balance above and reused here.
    def eEleBalance(optmodel, p,sc,n,nd):
        if sum(1 for eg in eg2n[nd]) + sum(1 for egs in egs2n[nd]) + sum(1 for nf, cc in lout[nd]) + sum(1 for ni, cc in lin[nd]) + sum(1 for ed in ed2n[nd]) + sum(1 for hgs in _comp_at[nd]) + len(_hcomp_elec_at[nd]):
            return (sum(optmodel.vEleTotalOutput[p,sc,n,eg] for eg in model.eg  if (nd,eg) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,egs] for egs in model.egs if (nd,egs) in model.n2eg) - sum(optmodel.vEleTotalCharge[p,sc,n,e2h] for e2h in model.e2h if (nd,e2h) in model.n2hg)
                  - sum(optmodel.vEleNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in lout[nd]) + sum(optmodel.vEleNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in lin[nd]) + optmodel.vEleImport[p,sc,n,nd] - optmodel.vEleExport[p,sc,n,nd]
                  + heat_to_power_output(optmodel, _htw_at[nd], p, sc, n) - heat_electricity_load(optmodel, _htp_at[nd], p, sc, n)
                  - sum(model.Par['pHydGenMaxCompressorConsumption'][hgs] * optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in _comp_at[nd])
                  - sum(model.Par['pHydGenMaxCompressorConsumption'][hc] * optmodel.vHydCompFlow[p,sc,n,hc] for hc in _hcomp_elec_at[nd])
                  - sum(model.Par['pHydDemMaxCompressorConsumption'][hd] * optmodel.vHydDemand[p,sc,n,hd] for hd in model.hd if (nd,hd) in model.n2hd)
                  == sum(optmodel.vEleDemand[p,sc,n,ed] - optmodel.vENS[p,sc,n,ed] for ed in model.ed if (nd,ed) in model.n2ed))
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleBalance', Constraint(optmodel.psnnd, rule=eEleBalance, doc='Electricity balance in the DA market'))

    # hydrogen energy conservation or balance
    def eHydBalance(optmodel, p,sc,n,nd):
        if sum(1 for hg in hg2n[nd]) + sum(1 for hgs in hgs2n[nd]) + sum(1 for nf, cc in hout[nd]) + sum(1 for ni, cc in hin[nd]) + sum(1 for hd in hd2n[nd]) + len(_hcomp_suct_at[nd]) + len(_hcomp_disc_at[nd]):
            return (sum(optmodel.vHydTotalOutput[p,sc,n,hg] for hg in model.hg if (nd,hg) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in model.hgs if (nd,hgs) in model.n2hg) - sum(optmodel.vHydTotalCharge[p,sc,n,h2e] for h2e in model.h2e if (nd,h2e) in model.n2eg)
                  - sum(optmodel.vHydNetFlow[p,sc,n,nd,nf,cc] for (nf,cc) in hout[nd]) + sum(optmodel.vHydNetFlow[p,sc,n,ni,nd,cc] for (ni,cc) in hin[nd]) + optmodel.vHydImport[p,sc,n,nd] - optmodel.vHydExport[p,sc,n,nd]
                  - sum(optmodel.vHydCompFlow[p,sc,n,hc] for hc in _hcomp_suct_at[nd]) + sum(model.Par['pHydGenEfficiency'][hc] * optmodel.vHydCompFlow[p,sc,n,hc] for hc in _hcomp_disc_at[nd])
                  == sum(optmodel.vHydDemand[p,sc,n,hd] - optmodel.vHNS[p,sc,n,hd] for hd in model.hd if (nd,hd) in model.n2hd))
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
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) + sum(1 for e2h in model.e2h if model.Par['pHydGenNoFCRD'][e2h] == 0):
            return sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) + sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,e2h] for e2h in model.e2h if model.Par['pHydGenNoFCRD'][e2h] == 0) + sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e] for h2e in model.h2e if model.Par['pEleGenNoFCRD'][h2e] == 0) <= model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveDisUpward', Constraint(optmodel.psn, rule=eEleFreqContReserveDisUpward, doc='Frequency containment reserve - upward'))

    def eEleFreqContReserveDisDownward(optmodel, p,sc,n):
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) + sum(1 for e2h in model.e2h if model.Par['pHydGenNoFCRD'][e2h] == 0):
            return sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRD'][egt] == 0) + sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRD'][egs] == 0) + sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,e2h] for e2h in model.e2h if model.Par['pHydGenNoFCRD'][e2h] == 0) + sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,h2e] for h2e in model.h2e if model.Par['pEleGenNoFCRD'][h2e] == 0) <= model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveDisDownward', Constraint(optmodel.psn, rule=eEleFreqContReserveDisDownward, doc='Frequency containment reserve - downward'))

    def eEleFreqContReserveNor(optmodel, p,sc,n):
        if sum(1 for egt in model.egt if model.Par['pEleGenNoFCRN'][egt] == 0) + sum(1 for egs in model.egs if model.Par['pEleGenNoFCRN'][egs] == 0) + sum(1 for e2h in model.e2h if model.Par['pHydGenNoFCRN'][e2h] == 0):
            return sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] for egt in model.egt if model.Par['pEleGenNoFCRN'][egt] == 0) + sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] for egs in model.egs if model.Par['pEleGenNoFCRN'][egs] == 0) + sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,e2h] for e2h in model.e2h if model.Par['pHydGenNoFCRN'][e2h] == 0) + sum(optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e] for h2e in model.h2e if model.Par['pEleGenNoFCRN'][h2e] == 0) <= min(model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n], model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqContReserveNor', Constraint(optmodel.psn, rule=eEleFreqContReserveNor, doc='Frequency containment reserve - normal'))

    # The relation between the upward and downward bids and the provision of FCR-D reserves from an electric generator is defined as follows:
    def eEleRelationFreqDisUpBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egt] == 0:
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egt] == optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisUpBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqDisUpBid2Gen, doc='Relation FCR-D upward bid to generation'))

    def eEleRelationFreqDisDownBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egt] == 0:
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egt] == optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisDownBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqDisDownBid2Gen, doc='Relation FCR-D downward bid to generation'))

    def eEleRelationFreqNorUpBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egt] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] <= optmodel.vEleFreqContReserveNorUpGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorUpBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqNorUpBid2Gen, doc='Relation FCR-N upward bid to generation'))

    def eEleRelationFreqNorDownBid2Gen(optmodel, p,sc,n,egt):
        if model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egt] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egt] <= optmodel.vEleFreqContReserveNorDownGen[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorDownBid2Gen', Constraint(optmodel.psnegt, rule=eEleRelationFreqNorDownBid2Gen, doc='Relation FCR-N downward bid to generation'))

    # The relation between the upward and downward bids and the provision of FCR-D reserves from an electric storage system is defined as follows:
    def eEleRelationFreqDisUpBid2Stor(optmodel, p,sc,n,egs):
        if model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0:
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs] == optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisUpBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqDisUpBid2Stor, doc='Relation FCR-D upward bid to storage'))

    def eEleRelationFreqDisDownBid2Stor(optmodel, p,sc,n,egs):
        if model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0:
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs] == optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisDownBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqDisDownBid2Stor, doc='Relation FCR-D downward bid to storage'))

    def eEleRelationFreqNorUpBid2Stor(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] == optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorUpBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqNorUpBid2Stor, doc='Relation FCR-N upward bid to storage'))

    def eEleRelationFreqNorDownBid2Stor(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorDownBid2Stor', Constraint(optmodel.psnegs, rule=eEleRelationFreqNorDownBid2Stor, doc='Relation FCR-N downward bid to storage'))

    # symmetrical FCR-N provision from an electric ESS
    def eEleSymmFreqNorStor2Ch(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleSymmFreqNorStor2Ch', Constraint(optmodel.psnegs, rule=eEleSymmFreqNorStor2Ch, doc='Symmetrical FCR-N charge provision from storage'))

    def eEleSymmFreqNorStor2Dis(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] == optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleSymmFreqNorStor2Dis', Constraint(optmodel.psnegs, rule=eEleSymmFreqNorStor2Dis, doc='Symmetrical FCR-N discharge provision from storage'))

    # The tight headroom bounds for FCR-D provision from an electric ESS is defined as follows:
    def eEleFreqUpDischargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            # For a candidate storage unit cap the up-discharge reserve by the BUILT power
            # (nameplate * build fraction), so a fractionally built unit cannot sell upward
            # reserve on discharge capacity it has not built (mirrors the C21b down-charge fix).
            if  model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                if egs in model.egsc:
                    return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n] * optmodel.vEleGenInvest[egs] - optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]
                return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n] - optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]
            else:
                # Discharge reserve must be bounded by the DISCHARGE rating, not the charge
                # rating: a non-dischargeable unit (MaxPower ~ 0) then has zero discharge
                # headroom, and a NoDayAhead unit (output2ndBlock fixed to 0) is bounded by
                # its MaxPower -- the same quantity as the branch above (C18).
                if egs in model.egsc:
                    return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n] * optmodel.vEleGenInvest[egs]
                return optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpDischargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqUpDischargeHeadroom, doc='FCR-D and FCR-N upward discharge headroom'))

    def eEleFreqUpChargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            return optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] <= optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqUpChargeHeadroom, doc='FCR-D and FCR-N upward charge headroom'))

    def eEleFreqDownDischargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] <= optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]
            else:
                # bound the down-discharge reserve by the DISCHARGE rating, not the charge
                # rating, so a non-dischargeable unit cannot sell it (C18)
                return optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs] <= model.Par['pEleMaxPower'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownDischargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqDownDischargeHeadroom, doc='FCR-D downward discharge headroom'))

    def eEleFreqDownChargeHeadroom(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            # For a candidate storage unit cap the down-charge reserve by the BUILT charge
            # capacity (nameplate * build fraction), so a fractionally built unit cannot
            # sell down-reserve on capacity it has not built (C21b).
            if egs in model.egsc:
                return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs] <= model.Par['pEleMaxCharge'][egs][p,sc,n] * optmodel.vEleGenInvest[egs] - optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
            return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs] <= model.Par['pEleMaxCharge'][egs][p,sc,n] - optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeHeadroom', Constraint(optmodel.psnegs, rule=eEleFreqDownChargeHeadroom, doc='FCR-D downward charge headroom'))

    def eEleFreqUpChargeBound(optmodel, p,sc,n,egs):
        if ((model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0)) and model.Par['pEleMaxCharge'][egs][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeBound', Constraint(optmodel.psnegs, rule=eEleFreqUpChargeBound, doc='FCR-D and FCR-N upward charge bound'))

    def eEleFreqUpDischargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
            if model.Par['pEleGenNoDayAhead'][egs] == 0 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5:
                return (optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
            else:
                return (optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpDischargeBound', Constraint(optmodel.psnegs, rule=eEleFreqUpDischargeBound, doc='FCR-D upward discharge bound'))

    def eEleFreqDownChargeBound(optmodel, p,sc,n,egs):
        if ((model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0)) and model.Par['pEleMaxCharge'][egs][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= model.Par['pVarFixedAvailability'][egs][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeBound', Constraint(optmodel.psnegs, rule=eEleFreqDownChargeBound, doc='FCR-D downward charge bound'))

    # Leg-exclusive FCR (feature IndStorFCRLegExclusive). A battery is either charging or
    # discharging (eEleStorageMode: vEleStorCharge + vEleStorDischarge <= availability), so it
    # must not bid reserve from BOTH legs in the same hour -- doing so double-counts headroom and
    # overstates FCR capability. Gate each leg's total FCR reserve by its mode binary times the
    # leg rating; combined with the mode exclusivity this closes the simultaneous
    # charge+discharge reserve loophole. Constant rating * binary = linear; the existing headroom
    # rows still cap built/2nd-block capacity, so the nameplate here is only the on/off gate.
    # Exact when the mode binary is enforced (MILP); tightens the relaxation otherwise.
    def _stor_fcr_active(p, sc, n, egs):
        return (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 or model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0
                or model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 or model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0)

    def eEleStorFCRDischargeLeg(optmodel, p,sc,n,egs):
        if model.Par['pOptIndStorFCRLegExclusive'] == 1 and model.Par['pEleMaxPower'][egs][p,sc,n] > 1e-5 and _stor_fcr_active(p,sc,n,egs):
            return (optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]
                    + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egs]
                    ) <= model.Par['pEleMaxPower'][egs][p,sc,n] * optmodel.vEleStorDischarge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorFCRDischargeLeg', Constraint(optmodel.psnegs, rule=eEleStorFCRDischargeLeg, doc='leg-exclusive FCR: discharge-leg reserve only when discharging'))

    def eEleStorFCRChargeLeg(optmodel, p,sc,n,egs):
        if model.Par['pOptIndStorFCRLegExclusive'] == 1 and model.Par['pEleMaxCharge'][egs][p,sc,n] > 1e-5 and _stor_fcr_active(p,sc,n,egs):
            return (optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]
                    + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
                    ) <= model.Par['pEleMaxCharge'][egs][p,sc,n] * optmodel.vEleStorCharge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorFCRChargeLeg', Constraint(optmodel.psnegs, rule=eEleStorFCRChargeLeg, doc='leg-exclusive FCR: charge-leg reserve only when charging'))

    def eEleFreqDownDischargeBound(optmodel, p,sc,n,egs):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRD'][egs] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and  model.Par['pEleGenNoFCRN'][egs] == 0):
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
            return model.Par['pEleMaxStorage'][egs][p,sc,n] * model.factor1 * (optmodel.vEleGenInvest[egs] if egs in model.egsc else 1.0) - optmodel.vEleInventory[p,sc,n,egs] >= model.Par['pEleGenEfficiency_charge'][egs] * ((model.Par['pEleGenEnduranceFCRD'][egs]/60) * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,model.n.prev(n,1),egs] + (model.Par['pEleGenEnduranceFCRN'][egs]/60) * optmodel.vEleFreqContReserveNorBid[p,sc,model.n.prev(n,1),egs])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageEnduranceDown', Constraint(optmodel.psnegs, rule=eEleStorageEnduranceDown, doc='Storage endurance for FCR-D and FCR-N downward'))

    # C30: the two rolling endurance constraints above back the bid at n-1 with the inventory
    # at n and skip the first level, so the bid at the LAST level has no energy backing. Add a
    # terminal row that backs the last level's bid with the last level's inventory (the
    # inventory one period ahead does not exist), so end-of-horizon bids are not free.
    def eEleStorageEnduranceUpEnd(optmodel, p,sc,n,egs):
        if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and model.Par['pEleMaxStorage'][egs][p,sc,n] and n == model.n.last():
            return optmodel.vEleInventory[p,sc,n,egs] >= (1/model.Par['pEleGenEfficiency_discharge'][egs]) * ((model.Par['pEleGenEnduranceFCRD'][egs]/60) * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs] + (model.Par['pEleGenEnduranceFCRN'][egs]/60) * optmodel.vEleFreqContReserveNorBid[p,sc,n,egs])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageEnduranceUpEnd', Constraint(optmodel.psnegs, rule=eEleStorageEnduranceUpEnd, doc='Storage endurance for the terminal-level FCR-D/N upward bid (C30)'))

    def eEleStorageEnduranceDownEnd(optmodel, p,sc,n,egs):
        if (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0) and model.Par['pEleMaxStorage'][egs][p,sc,n] and n == model.n.last():
            return model.Par['pEleMaxStorage'][egs][p,sc,n] * model.factor1 * (optmodel.vEleGenInvest[egs] if egs in model.egsc else 1.0) - optmodel.vEleInventory[p,sc,n,egs] >= model.Par['pEleGenEfficiency_charge'][egs] * ((model.Par['pEleGenEnduranceFCRD'][egs]/60) * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs] + (model.Par['pEleGenEnduranceFCRN'][egs]/60) * optmodel.vEleFreqContReserveNorBid[p,sc,n,egs])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleStorageEnduranceDownEnd', Constraint(optmodel.psnegs, rule=eEleStorageEnduranceDownEnd, doc='Storage endurance for the terminal-level FCR-D/N downward bid (C30)'))

    # --- Electrolyser (e2h) FCR provision: charge-side mirror of the storage formulation.
    # An electrolyser is a controllable load, so it offers FCR by modulating consumption
    # (FCR-up = reduce, FCR-down = increase). There is no discharge side. Gated on the
    # electrolyser's own participation flags pHydGenNoFCRD / pHydGenNoFCRN (default 1).
    def eEleRelationFreqDisUpBid2Conv(optmodel, p,sc,n,e2h):
        if model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0:
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,e2h] == optmodel.vEleFreqContReserveDisUpCha[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisUpBid2Conv', Constraint(optmodel.psne2h, rule=eEleRelationFreqDisUpBid2Conv, doc='Relation FCR-D upward bid to electrolyser consumption'))

    def eEleRelationFreqDisDownBid2Conv(optmodel, p,sc,n,e2h):
        if model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0:
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,e2h] == optmodel.vEleFreqContReserveDisDownCha[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqDisDownBid2Conv', Constraint(optmodel.psne2h, rule=eEleRelationFreqDisDownBid2Conv, doc='Relation FCR-D downward bid to electrolyser consumption'))

    def eEleRelationFreqNorUpBid2Conv(optmodel, p,sc,n,e2h):
        if model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,e2h] == optmodel.vEleFreqContReserveNorUpCha[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorUpBid2Conv', Constraint(optmodel.psne2h, rule=eEleRelationFreqNorUpBid2Conv, doc='Relation FCR-N upward bid to electrolyser consumption'))

    def eEleRelationFreqNorDownBid2Conv(optmodel, p,sc,n,e2h):
        if model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0:
            return optmodel.vEleFreqContReserveNorBid[p,sc,n,e2h] == optmodel.vEleFreqContReserveNorDownCha[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleRelationFreqNorDownBid2Conv', Constraint(optmodel.psne2h, rule=eEleRelationFreqNorDownBid2Conv, doc='Relation FCR-N downward bid to electrolyser consumption'))

    def eEleSymmFreqNorConv(optmodel, p,sc,n,e2h):
        if (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 or model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0) and model.Par['pHydGenNoFCRN'][e2h] == 0:
            return optmodel.vEleFreqContReserveNorUpCha[p,sc,n,e2h] == optmodel.vEleFreqContReserveNorDownCha[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleSymmFreqNorConv', Constraint(optmodel.psne2h, rule=eEleSymmFreqNorConv, doc='Symmetrical FCR-N provision from the electrolyser'))

    def eEleFreqUpChargeHeadroomConv(optmodel, p,sc,n,e2h):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0):
            return optmodel.vEleFreqContReserveDisUpCha[p,sc,n,e2h] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,e2h] <= optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeHeadroomConv', Constraint(optmodel.psne2h, rule=eEleFreqUpChargeHeadroomConv, doc='FCR upward charge headroom for the electrolyser'))

    def eEleFreqDownChargeHeadroomConv(optmodel, p,sc,n,e2h):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0):
            return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,e2h] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,e2h] <= model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] * optmodel.vHydGenCommitment[p,sc,n,e2h] - optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeHeadroomConv', Constraint(optmodel.psne2h, rule=eEleFreqDownChargeHeadroomConv, doc='FCR downward charge headroom for the electrolyser'))

    # For a candidate electrolyser, also cap the down-charge reserve (plus the charge) by
    # the BUILT input capacity (nameplate * build fraction), so a fractionally built unit
    # cannot sell down-reserve on capacity it has not built. This is a separate constraint
    # because the headroom above already multiplies the nameplate by the commitment, and
    # multiplying by the build fraction too would be bilinear (C21b).
    def eEleFreqDownChargeHeadroomConvInvest(optmodel, p,sc,n,e2h):
        if e2h in model.hgc and ((model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0)):
            return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,e2h] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,e2h] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] <= model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] * optmodel.vHydGenInvest[e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeHeadroomConvInvest', Constraint(optmodel.psne2h, rule=eEleFreqDownChargeHeadroomConvInvest, doc='FCR downward charge headroom for a candidate electrolyser (build-limited)'))

    # RESERVE RESPONSE SPEED = the paper's technology-resolved FCR-D ramp gate (eq:rampgate),
    # implemented in code and extended to the downward direction now that the cascade lets the
    # electrolyser bid down. FCR-D must reach 86% of the bid within 7.5 s, so a stack ramping at
    # rho_g (fraction of rated consumption per second) can back only (7.5/0.86)*rho_g of its rating
    # on FCR-D: PEM ~10%/s backs ~87%, alkaline ~2%/s backs ~17%. FCR-N is NOT gated -- its 60 s
    # window is long enough that the ramp never binds. A battery reaches full power in << 1 s, so
    # the gate is slack for it. Per-technology rho is env-tunable; default off = golden-neutral.
    _fcrd_gate_on = os.environ.get('ELE_FCRD_RAMPGATE', '0') == '1'
    _rho_tech = {'AEL': float(os.environ.get('AEL_FCRD_RAMP_PER_S', '0.02')),
                 'PEM': float(os.environ.get('PEM_FCRD_RAMP_PER_S', '0.10'))}
    _act_factor = 7.5 / 0.86   # effective seconds to meet the 86%-within-7.5s FCR-D requirement
    def _fcrd_cap(p,sc,n,e2h):
        tech = 'AEL' if 'AEL' in str(e2h) else 'PEM'
        rated = model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] * (optmodel.vHydGenInvest[e2h] if e2h in model.hgc else 1.0)
        return _act_factor * _rho_tech[tech] * rated
    def eEleFCRDRampGateUp(optmodel, p,sc,n,e2h):
        if not _fcrd_gate_on or model.Par['pHydGenNoFCRD'][e2h] == 1:
            return Constraint.Skip
        return optmodel.vEleFreqContReserveDisUpCha[p,sc,n,e2h] <= _fcrd_cap(p,sc,n,e2h)
    optmodel.__setattr__('eEleFCRDRampGateUp', Constraint(optmodel.psne2h, rule=eEleFCRDRampGateUp, doc='Electrolyser upward FCR-D bounded by per-technology stack ramp within the 7.5s activation window'))

    def eEleFCRDRampGateDown(optmodel, p,sc,n,e2h):
        if not _fcrd_gate_on or model.Par['pHydGenNoFCRD'][e2h] == 1:
            return Constraint.Skip
        return optmodel.vEleFreqContReserveDisDownCha[p,sc,n,e2h] <= _fcrd_cap(p,sc,n,e2h)
    optmodel.__setattr__('eEleFCRDRampGateDown', Constraint(optmodel.psne2h, rule=eEleFCRDRampGateDown, doc='Electrolyser downward FCR-D bounded by per-technology stack ramp within the 7.5s activation window'))

    def eEleFreqUpChargeBoundConv(optmodel, p,sc,n,e2h):
        if ((model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0)) and model.Par['pHydMaxCharge'][e2h][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisUpCha[p,sc,n,e2h] + optmodel.vEleFreqContReserveNorUpCha[p,sc,n,e2h]) / model.Par['pHydMaxCharge'][e2h][p,sc,n] <= model.Par['pVarFixedAvailability'][e2h][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpChargeBoundConv', Constraint(optmodel.psne2h, rule=eEleFreqUpChargeBoundConv, doc='FCR upward charge bound for the electrolyser'))

    def eEleFreqDownChargeBoundConv(optmodel, p,sc,n,e2h):
        if ((model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRD'][e2h] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pHydGenNoFCRN'][e2h] == 0)) and model.Par['pHydMaxCharge'][e2h][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisDownCha[p,sc,n,e2h] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,e2h]) / model.Par['pHydMaxCharge'][e2h][p,sc,n] <= model.Par['pVarFixedAvailability'][e2h][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownChargeBoundConv', Constraint(optmodel.psne2h, rule=eEleFreqDownChargeBoundConv, doc='FCR downward charge bound for the electrolyser'))

    # FCR-down endurance: the extra hydrogen the electrolysers at a node would produce while
    # sustaining a down-bid over the endurance window must fit in the empty headroom of the
    # hydrogen stores it can reach. The extra H2 is lifted through the compressor into the tank,
    # so the reachable headroom is the store at nd (flat/tank-welded case) PLUS the store at the
    # discharge node of any compressor suctioning from nd (the pressure cascade: electrolysers at
    # 30 bar reaching the 500-bar tank). Under the flat single-node topology the compressor and
    # tank share the electrolyser's node, so this adds nothing and existing cases are byte-
    # unchanged; under the pressure-resolved topology it backs the down-bid with the tank the
    # compressor feeds instead of forcing it to zero. FCR-up (cutting consumption) needs no
    # storage, so only the down direction is constrained. Mirrors _hgs_reachable (used by the
    # fuel-cell up-endurance) but in the lift direction rather than the let-down direction.
    def _hgs_reachable_up(nd):
        seen, out = set(), []
        for hgs in model.hgs:
            if (nd, hgs) in model.n2hg and hgs not in seen:
                seen.add(hgs); out.append(hgs)
        for hc in _hcomp_suct_at[nd]:
            dn = model.Par['pHydGenDischargeNode'][hc]
            for hgs in model.hgs:
                if (dn, hgs) in model.n2hg and hgs not in seen:
                    seen.add(hgs); out.append(hgs)
        return out
    def eEleFreqDownEnduranceConv(optmodel, p,sc,n,nd):
        if n == model.n.first():
            return Constraint.Skip
        e2h_at_node = [e2h for e2h in model.e2h if (nd,e2h) in model.n2hg and (model.Par['pHydGenNoFCRD'][e2h] == 0 or model.Par['pHydGenNoFCRN'][e2h] == 0)]
        hgs_at_node = _hgs_reachable_up(nd)
        if not e2h_at_node:
            return Constraint.Skip
        lhs = sum(((model.Par['pHydGenEnduranceFCRD'][e2h]/60) * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,model.n.prev(n,1),e2h]
                 + (model.Par['pHydGenEnduranceFCRN'][e2h]/60) * optmodel.vEleFreqContReserveNorBid       [p,sc,model.n.prev(n,1),e2h]) / model.Par['pHydGenProductionFunction'][e2h] for e2h in e2h_at_node)
        rhs = sum(model.Par['pHydMaxStorage'][hgs][p,sc,n] * model.factor1 * (optmodel.vHydGenInvest[hgs] if hgs in model.hgc else 1.0) - optmodel.vHydInventory[p,sc,n,hgs] for hgs in hgs_at_node)
        return lhs <= rhs
    optmodel.__setattr__('eEleFreqDownEnduranceConv', Constraint(optmodel.psnnd, rule=eEleFreqDownEnduranceConv, doc='Electrolyser FCR-down endurance bounded by node hydrogen-store headroom'))

    # C30: the rolling conv-endurance above backs the bid at n-1 with the store headroom at n
    # and skips the first level, leaving the last level's bid unbacked. Back it with the
    # terminal-level store headroom (mirrors eEleStorageEnduranceDownEnd for the e2h node).
    def eEleFreqDownEnduranceConvEnd(optmodel, p,sc,n,nd):
        if n != model.n.last():
            return Constraint.Skip
        e2h_at_node = [e2h for e2h in model.e2h if (nd,e2h) in model.n2hg and (model.Par['pHydGenNoFCRD'][e2h] == 0 or model.Par['pHydGenNoFCRN'][e2h] == 0)]
        hgs_at_node = _hgs_reachable_up(nd)
        if not e2h_at_node:
            return Constraint.Skip
        lhs = sum(((model.Par['pHydGenEnduranceFCRD'][e2h]/60) * optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,e2h]
                 + (model.Par['pHydGenEnduranceFCRN'][e2h]/60) * optmodel.vEleFreqContReserveNorBid       [p,sc,n,e2h]) / model.Par['pHydGenProductionFunction'][e2h] for e2h in e2h_at_node)
        rhs = sum(model.Par['pHydMaxStorage'][hgs][p,sc,n] * model.factor1 * (optmodel.vHydGenInvest[hgs] if hgs in model.hgc else 1.0) - optmodel.vHydInventory[p,sc,n,hgs] for hgs in hgs_at_node)
        return lhs <= rhs
    optmodel.__setattr__('eEleFreqDownEnduranceConvEnd', Constraint(optmodel.psnnd, rule=eEleFreqDownEnduranceConvEnd, doc='Electrolyser FCR-down endurance for the terminal load level (C30)'))

    # Phase 2 -- FCR-down bounded by the compressor RATE, not just the tank volume. The
    # endurance constraints above limit the extra hydrogen by the empty tank headroom (a
    # volume limit). A held FCR-down bid, if activated, also has to be COMPRESSED as it is made:
    # the extra production rate (bid / ProductionFunction) plus the baseline compression must fit
    # through the built compressor throughput at the node. Two compressor representations feed the
    # spare-throughput headroom: (i) the legacy tank-welded compressor (model.hgcompc, throughput =
    # tank charge vHydTotalCharge), and (ii) the standalone compressor unit (model.hc) whose SUCTION
    # node is the electrolyser's node (throughput = vHydCompFlow). Both terms are present; a case
    # uses whichever it defines (existing cases have no hc, the pressure-resolved case has no
    # hgcompc), so this stays golden-neutral. Tying the FCR-down bid to the SIZED compressor rate is
    # the part no reviewed prior work models (see docs/lit_review_electrolyser_fcr.md).
    def eEleFreqDownCompressorRate(optmodel, p,sc,n,nd):
        e2h_at_node = [e2h for e2h in model.e2h if (nd,e2h) in model.n2hg and (model.Par['pHydGenNoFCRD'][e2h] == 0 or model.Par['pHydGenNoFCRN'][e2h] == 0)]
        comp_at_node = [hgs for hgs in model.hgcompc if (nd,hgs) in model.n2hg]
        comp_std_at_node = [hc for hc in getattr(model, 'hc', []) if model.Par['pHydGenNode'][hc] == nd]
        if not e2h_at_node or (not comp_at_node and not comp_std_at_node):
            return Constraint.Skip
        lhs = sum((optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,e2h]
                 + optmodel.vEleFreqContReserveNorBid       [p,sc,n,e2h]) / model.Par['pHydGenProductionFunction'][e2h] for e2h in e2h_at_node)
        rhs = (sum(model.Par['pHydGenCompressorNameplate'][hgs] * model.factor1 * optmodel.vHydCompInvest[hgs]
                   - optmodel.vHydTotalCharge[p,sc,n,hgs] for hgs in comp_at_node)
               + sum(model.Par['pHydGenMaximumCharge'][hc] * (optmodel.vHydCompBuild[hc] if hc in model.hcc else 1.0)
                     - optmodel.vHydCompFlow[p,sc,n,hc] for hc in comp_std_at_node))
        return lhs <= rhs
    optmodel.__setattr__('eEleFreqDownCompressorRate', Constraint(optmodel.psnnd, rule=eEleFreqDownCompressorRate, doc='Electrolyser FCR-down extra production rate bounded by spare node compressor throughput'))

    # --- Fuel cell (h2e) FCR provision: generation-side mirror of the thermal-generator
    # formulation. A fuel cell is a hydrogen-fired generator (h2e is a subset of model.eg),
    # so it offers FCR by modulating its electricity output (FCR-up = produce more, FCR-down
    # = back off). The bids are the same variables the thermal generators use, already summed
    # into the FCR requirement and revenue. These constraints give them the missing physical
    # backing. Gated on the generator's own participation flags pEleGenNoFCRD / pEleGenNoFCRN
    # (default 1), so a unit only offers FCR when those columns are set to "No". The FCR-N
    # bid (NorBid) is symmetric: it appears in both the up-headroom (1) and the down-headroom
    # (2), so it is automatically bounded by min(spare-up, output) -- the correct two-sided
    # availability for a generator.
    #
    # 1. Up-bid headroom: the up bid (FCR-D up + FCR-N) cannot exceed the spare generation
    #    capacity, i.e. built MaxPower minus the current output. For a candidate fuel cell the
    #    capacity is the built fraction (MaxPower * build); for a fixed unit it is MaxPower
    #    directly (mirrors the candidate/fixed split used for the storage and electrolyser
    #    headroom constraints).
    def eEleFreqUpHeadroomFuelCell(optmodel, p,sc,n,h2e):
        if (model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRD'][h2e] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][h2e] == 0):
            if h2e in model.egc:
                return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e] + optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e] <= model.Par['pEleMaxPower'][h2e][p,sc,n] * optmodel.vEleGenInvest[h2e] - optmodel.vEleTotalOutput[p,sc,n,h2e]
            return optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e] + optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e] <= model.Par['pEleMaxPower'][h2e][p,sc,n] - optmodel.vEleTotalOutput[p,sc,n,h2e]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpHeadroomFuelCell', Constraint(optmodel.psnh2e, rule=eEleFreqUpHeadroomFuelCell, doc='FCR-D and FCR-N upward headroom for a fuel cell (spare generation capacity)'))

    # 2. Down-bid headroom: the down bid (FCR-D down + FCR-N) cannot exceed the current
    #    output, because a generator can back off only as far as zero.
    def eEleFreqDownHeadroomFuelCell(optmodel, p,sc,n,h2e):
        if (model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRD'][h2e] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][h2e] == 0):
            return optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,h2e] + optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e] <= optmodel.vEleTotalOutput[p,sc,n,h2e]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownHeadroomFuelCell', Constraint(optmodel.psnh2e, rule=eEleFreqDownHeadroomFuelCell, doc='FCR-D and FCR-N downward headroom for a fuel cell (can back down to zero)'))

    # 3. Availability bound: the up and down bids, scaled by the nameplate, cannot exceed the
    #    unit's fixed availability (mirrors eEleFreqUpDischargeBound / eEleFreqDownDischargeBound
    #    for storage and eEleFreqUpChargeBoundConv for the electrolyser).
    def eEleFreqUpBoundFuelCell(optmodel, p,sc,n,h2e):
        if ((model.Par['pOperatingReserveRequire_FCRD_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRD'][h2e] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Up'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][h2e] == 0)) and model.Par['pEleMaxPower'][h2e][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e] + optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e]) / model.Par['pEleMaxPower'][h2e][p,sc,n] <= model.Par['pVarFixedAvailability'][h2e][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqUpBoundFuelCell', Constraint(optmodel.psnh2e, rule=eEleFreqUpBoundFuelCell, doc='FCR upward availability bound for a fuel cell'))

    def eEleFreqDownBoundFuelCell(optmodel, p,sc,n,h2e):
        if ((model.Par['pOperatingReserveRequire_FCRD_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRD'][h2e] == 0) or (model.Par['pOperatingReserveRequire_FCRN_Down'][p,sc,n] > 0 and model.Par['pEleGenNoFCRN'][h2e] == 0)) and model.Par['pEleMaxPower'][h2e][p,sc,n]:
            return (optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,h2e] + optmodel.vEleFreqContReserveNorBid[p,sc,n,h2e]) / model.Par['pEleMaxPower'][h2e][p,sc,n] <= model.Par['pVarFixedAvailability'][h2e][p,sc,n]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleFreqDownBoundFuelCell', Constraint(optmodel.psnh2e, rule=eEleFreqDownBoundFuelCell, doc='FCR downward availability bound for a fuel cell'))

    # 4. NOVEL upward endurance, node level. This is the dual of the electrolyser down-endurance
    #    (eEleFreqDownEnduranceConv): a fuel cell sustaining an UP bid over the endurance window
    #    BURNS hydrogen, so the hydrogen it would consume must already be available in the node's
    #    tanks. lhs = sum over h2e at the node of the energy that would be delivered over the
    #    endurance window (EnduranceFCRD/60 * up-bid + EnduranceFCRN/60 * Nor-bid), converted to
    #    kg of hydrogen by dividing by the production function (electricity per kg). rhs = the
    #    hydrogen actually stored in the node's tanks (tank CONTENTS, not headroom). The bid at
    #    n-1 is backed by the inventory at n, mirroring the rolling form of the electrolyser
    #    constraint; the first level is skipped. With EnduranceFCRD/N defaulting to 0 the
    #    left-hand side is 0, so the constraint is inert for cases that do not set an endurance.
    # The cascade backing a fuel cell may sit at a HIGHER-pressure node than the fuel-cell inlet,
    # reachable only by a pressure let-down pipe (e.g. a 500-bar store feeding a 30-bar fuel cell).
    # So the H2 available to a fuel cell at node nd is the store contents AT nd plus the store
    # contents at any node feeding nd through a pipe (hin[nd]). For a flat case where the fuel cell
    # shares the tank's node this adds nothing (no upstream store), so existing cases are unchanged.
    def _hgs_reachable(nd):
        seen, out = set(), []
        for hgs in model.hgs:
            if (nd, hgs) in model.n2hg and hgs not in seen:
                seen.add(hgs); out.append(hgs)
        for (ni, cc) in hin[nd]:
            for hgs in model.hgs:
                if (ni, hgs) in model.n2hg and hgs not in seen:
                    seen.add(hgs); out.append(hgs)
        return out

    def eEleFreqUpEnduranceFuelCell(optmodel, p,sc,n,nd):
        if n == model.n.first():
            return Constraint.Skip
        h2e_at_node = [h2e for h2e in model.h2e if (nd,h2e) in model.n2eg and (model.Par['pEleGenNoFCRD'][h2e] == 0 or model.Par['pEleGenNoFCRN'][h2e] == 0)]
        hgs_at_node = _hgs_reachable(nd)
        if not h2e_at_node:
            return Constraint.Skip
        lhs = sum(((model.Par['pEleGenEnduranceFCRD'][h2e]/60) * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,model.n.prev(n,1),h2e]
                 + (model.Par['pEleGenEnduranceFCRN'][h2e]/60) * optmodel.vEleFreqContReserveNorBid       [p,sc,model.n.prev(n,1),h2e]) / model.Par['pEleGenProductionFunction'][h2e] for h2e in h2e_at_node)
        rhs = sum(optmodel.vHydInventory[p,sc,n,hgs] for hgs in hgs_at_node)
        return lhs <= rhs
    optmodel.__setattr__('eEleFreqUpEnduranceFuelCell', Constraint(optmodel.psnnd, rule=eEleFreqUpEnduranceFuelCell, doc='Fuel-cell FCR-up endurance bounded by reachable hydrogen-store contents (node + let-down cascade)'))

    # C30: the rolling endurance above backs the bid at n-1 with the store contents at n and
    # skips the first level, leaving the last level's bid unbacked. Add a terminal row that
    # backs the last level's bid with the last level's store contents (mirrors
    # eEleFreqDownEnduranceConvEnd for the fuel-cell node).
    def eEleFreqUpEnduranceFuelCellEnd(optmodel, p,sc,n,nd):
        if n != model.n.last():
            return Constraint.Skip
        h2e_at_node = [h2e for h2e in model.h2e if (nd,h2e) in model.n2eg and (model.Par['pEleGenNoFCRD'][h2e] == 0 or model.Par['pEleGenNoFCRN'][h2e] == 0)]
        hgs_at_node = _hgs_reachable(nd)
        if not h2e_at_node:
            return Constraint.Skip
        lhs = sum(((model.Par['pEleGenEnduranceFCRD'][h2e]/60) * optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,h2e]
                 + (model.Par['pEleGenEnduranceFCRN'][h2e]/60) * optmodel.vEleFreqContReserveNorBid       [p,sc,n,h2e]) / model.Par['pEleGenProductionFunction'][h2e] for h2e in h2e_at_node)
        rhs = sum(optmodel.vHydInventory[p,sc,n,hgs] for hgs in hgs_at_node)
        return lhs <= rhs
    optmodel.__setattr__('eEleFreqUpEnduranceFuelCellEnd', Constraint(optmodel.psnnd, rule=eEleFreqUpEnduranceFuelCellEnd, doc='Fuel-cell FCR-up endurance for the terminal load level (C30)'))

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

    # Energy inflows of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) bounded by the inflows data parameter [p.u.].
    # Note (audit C42): despite the "2Commitment" attribute name, the right-hand side is the
    # parameter limit, not a commitment variable -- the commitment-coupled form was never wired.
    # The name is kept to avoid renaming the constraint in result/.lp output; only the doc is corrected.
    def eEleMaxInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMaxInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMaxInflows'][egs][p,sc,n] <= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMaxInflows2Commitment, doc='energy inflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eEleMinInflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMinStorage'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMinInflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyInflows[p,sc,n,egs] / model.Par['pEleMinInflows'][egs][p,sc,n] >= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinInflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMinInflows2Commitment, doc='energy inflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eHydMaxInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMaxInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMaxInflows'][hgs][p,sc,n] <= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMaxInflows2Commitment, doc='energy inflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eHydMinInflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinStorage'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMinInflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyInflows[p,sc,n,hgs] / model.Par['pHydMinInflows'][hgs][p,sc,n] >= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinInflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMinInflows2Commitment, doc='energy inflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

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
    optmodel.__setattr__('eEleInventory', Constraint(optmodel.psnegs, rule=eEleInventory, doc='Electricity ESS inventory balance [kWh]'))

    def eHydInventory(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            if   model.n.ord(n) == model.Par['pHydCycleTimeStep'][hgs]:
                return model.Par['pHydInitialInventory'][hgs][p,sc,n]                                       + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in n2_list[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            elif model.n.ord(n) >  model.Par['pHydCycleTimeStep'][hgs]:
                return optmodel.vHydInventory[p,sc,model.n.prev(n,model.Par['pHydCycleTimeStep'][hgs]),hgs] + sum(model.Par['pDuration'][p,sc,n2] * (optmodel.vHydEnergyInflows[p,sc,n2,hgs] - optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - optmodel.vHydTotalOutput[p,sc,n2,hgs] + model.Par['pHydGenEfficiency'][hgs] * optmodel.vHydTotalCharge[p,sc,n2,hgs]) for n2 in n2_list[model.n.ord(n) - model.Par['pHydCycleTimeStep'][hgs]:model.n.ord(n)]) == optmodel.vHydInventory[p,sc,n,hgs] + optmodel.vHydSpillage[p,sc,n,hgs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydInventory', Constraint(optmodel.psnhgs, rule=eHydInventory, doc='Hydrogen ESS inventory balance [kgH2]'))

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
    # A PWL-flagged electrolyser (e2h in model.hpwl) uses the piecewise-linear part-load
    # curve below instead of this constant-efficiency conversion, so it is skipped here.
    _hpwl = getattr(model, 'hpwl', [])
    def eAllEnergy2Hyd(optmodel, p,sc,n,e2h):
        if model.Par['pHydMaxPower'][e2h][p,sc,n] and e2h in model.e2h and e2h not in _hpwl:
            # Only the productive consumption makes hydrogen; the standby draw
            # (StandByPower while in the standby state) produces none, so it is
            # subtracted before converting electricity input to hydrogen output.
            return optmodel.vHydTotalOutput[p,sc,n,e2h] == (optmodel.vEleTotalCharge[p,sc,n,e2h] - model.Par['pHydGenStandByPower'][e2h] * optmodel.vHydGenStandBy[p,sc,n,e2h]) / model.Par['pHydGenProductionFunction'][e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eAllEnergy2Hyd', Constraint(optmodel.psne2h, rule=eAllEnergy2Hyd, doc='energy conversion from different energy type to hydrogen [p.u.]'))

    # Piecewise-linear electrolyser part-load efficiency (audit Phase B / B1). Replaces the
    # constant-efficiency conversion above for the flagged electrolysers (model.hpwl) with a
    # SOS2 convex combination over the (productive electricity, hydrogen) breakpoints in
    # model.pwl_curve. appsi/HiGHS has no native SOS2, so the SOS2 condition is encoded with
    # segment binaries (adjacency): the weights may be nonzero only on the two breakpoints of a
    # single active segment, giving an exact piecewise-linear conversion. The convexity and
    # segment-sum rows equal the commitment, so an off or standby unit (commitment = 0) has all
    # weights zero -> zero productive power and zero hydrogen, while an on unit sits on the curve
    # between MinCharge and MaxCharge. The productive electricity excludes the standby draw,
    # matching the constant-efficiency form.
    if _hpwl:
        psn_hpwl = [(p, sc, n, g) for (p, sc, n) in model.psn for g in _hpwl]

        def ePWLConvexity(optmodel, p,sc,n,g):
            return sum(optmodel.vHydGenPWLWeight[p,sc,n,g,k] for k in model.pwlbp) == optmodel.vHydGenCommitment[p,sc,n,g]
        optmodel.__setattr__('ePWLConvexity', Constraint(psn_hpwl, rule=ePWLConvexity, doc='electrolyser PWL weights sum to the on-state'))

        # Segment-sum + SOS2 adjacency enforce a single active segment via the segment binaries.
        # The PWL-relax (IndElectrolyserPWLRelax=1) drops both, keeping only the free convex
        # combination (ePWLConvexity + ePWLPower + ePWLHydrogen): on a concave H2 curve the
        # optimum then sits on the upper envelope when H2 is valued, so the binaries are not
        # needed and the relaxation is exact. Verify the curve binds at every productive hour.
        if model.Par['pOptIndElectrolyserPWLRelax'] == 0:
            def ePWLSegmentSum(optmodel, p,sc,n,g):
                return sum(optmodel.vHydGenPWLSegment[p,sc,n,g,s] for s in model.pwlseg) == optmodel.vHydGenCommitment[p,sc,n,g]
            optmodel.__setattr__('ePWLSegmentSum', Constraint(psn_hpwl, rule=ePWLSegmentSum, doc='electrolyser PWL exactly one active segment when on'))

            psn_hpwl_bp = [(p, sc, n, g, k) for (p, sc, n) in model.psn for g in _hpwl for k in model.pwlbp]
            def ePWLAdjacency(optmodel, p,sc,n,g,k):
                # weight on breakpoint k is allowed only if an adjacent segment (k-1 or k) is active
                segs = [s for s in (k - 1, k) if s in model.pwlseg]
                return optmodel.vHydGenPWLWeight[p,sc,n,g,k] <= sum(optmodel.vHydGenPWLSegment[p,sc,n,g,s] for s in segs)
            optmodel.__setattr__('ePWLAdjacency', Constraint(psn_hpwl_bp, rule=ePWLAdjacency, doc='electrolyser PWL SOS2 adjacency (weights only on the active segment)'))

        def ePWLPower(optmodel, p,sc,n,g):
            return optmodel.vEleTotalCharge[p,sc,n,g] - model.Par['pHydGenStandByPower'][g] * optmodel.vHydGenStandBy[p,sc,n,g] == sum(optmodel.vHydGenPWLWeight[p,sc,n,g,k] * model.pwl_curve[g][k][0] for k in model.pwlbp)
        optmodel.__setattr__('ePWLPower', Constraint(psn_hpwl, rule=ePWLPower, doc='electrolyser PWL productive electricity from breakpoint weights'))

        def ePWLHydrogen(optmodel, p,sc,n,g):
            return optmodel.vHydTotalOutput[p,sc,n,g] == sum(optmodel.vHydGenPWLWeight[p,sc,n,g,k] * model.pwl_curve[g][k][1] for k in model.pwlbp)
        optmodel.__setattr__('ePWLHydrogen', Constraint(psn_hpwl, rule=ePWLHydrogen, doc='electrolyser PWL hydrogen output from breakpoint weights'))

    # Electrolyser three-state model (on / standby / off): on and standby are mutually
    # exclusive, off is the remainder. Only built where the unit has a standby capability
    # (pHydGenStandByStatus); otherwise the standby variable is fixed to zero (plain on/off).
    # Three-state formulation after Qiu et al. (2022), CIEEC -- standby draws StandByPower
    # to stay warm and produces no hydrogen.
    def eHydElectrolyserStandBy(optmodel, p,sc,n,e2h):
        if model.Par['pHydGenStandByStatus'][e2h] == 1:
            return optmodel.vHydGenCommitment[p,sc,n,e2h] + optmodel.vHydGenStandBy[p,sc,n,e2h] <= 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydElectrolyserStandBy', Constraint(optmodel.psne2h, rule=eHydElectrolyserStandBy, doc='electrolyser on/standby mutual exclusivity (off = remainder)'))

    # Standby is only reachable when the stack is already warm: the unit can be in standby
    # at t only if it was on or in standby at t-1. Without this the solver could slip into
    # standby straight from off, pay one period of StandByPower to be "warm", and then start
    # for free -- dodging the cold-start cost. The first step uses the pre-horizon state
    # (pHydInitialUC / pHydInitialStandBy).
    def eHydElectrolyserStandByTransition(optmodel, p,sc,n,e2h):
        if model.Par['pHydGenStandByStatus'][e2h] == 1:
            if n == model.n.first():
                return optmodel.vHydGenStandBy[p,sc,n,e2h] <= model.Par['pHydInitialUC'][p,sc,e2h] + model.Par['pHydInitialStandBy'][p,sc,e2h]
            else:
                return optmodel.vHydGenStandBy[p,sc,n,e2h] <= optmodel.vHydGenCommitment[p,sc,model.n.prev(n),e2h] + optmodel.vHydGenStandBy[p,sc,model.n.prev(n),e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydElectrolyserStandByTransition', Constraint(optmodel.psne2h, rule=eHydElectrolyserStandByTransition, doc='electrolyser standby only reachable when warm (on or standby at t-1)'))

    # Cold start: turning the electrolyser ON from OFF triggers the start-up cost
    # (pHydGenStartUpCost, already summed in the objective over hgt). Starting from
    # STANDBY is free, since the stack is kept warm -- this is what makes the standby
    # state worthwhile (sit in standby through a short idle period to dodge a cold start)
    # and follows the on/off/standby scheduling of Qiu et al. (2022), IEEE CIEEC.
    def eHydElectrolyserColdStart(optmodel, p,sc,n,e2h):
        if model.Par['pHydGenStartUpCost'][e2h]:
            if n == model.n.first():
                return optmodel.vHydGenStartUp[p,sc,n,e2h] >= optmodel.vHydGenCommitment[p,sc,n,e2h] - model.Par['pHydInitialUC'][p,sc,e2h]
            else:
                return optmodel.vHydGenStartUp[p,sc,n,e2h] >= optmodel.vHydGenCommitment[p,sc,n,e2h] - optmodel.vHydGenCommitment[p,sc,model.n.prev(n),e2h] - optmodel.vHydGenStandBy[p,sc,model.n.prev(n),e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydElectrolyserColdStart', Constraint(optmodel.psne2h, rule=eHydElectrolyserColdStart, doc='electrolyser cold start (off->on) incurs the start-up cost; a warm start from standby is free'))

    # A start-up only happens when the electrolyser ends up on, so the (cold) start-up
    # cannot exceed the commitment. With the cold-start lower bound above this pins the
    # start-up to exactly the off->on transitions, keeping the binary logic airtight.
    def eHydElectrolyserStartUpBound(optmodel, p,sc,n,e2h):
        if model.Par['pHydGenStartUpCost'][e2h]:
            return optmodel.vHydGenStartUp[p,sc,n,e2h] <= optmodel.vHydGenCommitment[p,sc,n,e2h]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydElectrolyserStartUpBound', Constraint(optmodel.psne2h, rule=eHydElectrolyserStartUpBound, doc='electrolyser start-up implies the unit is on'))

    # Operational symmetry-breaking for identical electrolyser units (feature
    # IndElectrolyserOperSymBreak). Identical units (same signature in every parameter) create a
    # per-hour permutation symmetry that bloats branch-and-bound and weakens the bound. Order each
    # identical group lexicographically every hour -- by ON, then by ON-or-standby -- so only one
    # representative of each symmetric schedule survives. Exact when min-up/down is off (no per-unit
    # intertemporal coupling that the ordering could distort). Complements the investment-side ordering.
    if model.Par['pOptIndElectrolyserOperSymBreak'] == 1:
        from .oM_Investment import _identical_groups
        _e2h_pairs = [(grp[i], grp[i+1]) for grp in _identical_groups(model.Par, list(model.e2h))
                      for i in range(len(grp) - 1)]
        _psn_pairs = [(p, sc, n, gi, gj) for (p, sc, n) in model.psn for (gi, gj) in _e2h_pairs]
        if _e2h_pairs:
            print(f'-- Operational symmetry-breaking: ordered {len(_e2h_pairs)} identical electrolyser pair(s): {_e2h_pairs}', flush=True)

        def eHydOperSymOn(om, p,sc,n,gi,gj):
            return om.vHydGenCommitment[p,sc,n,gi] >= om.vHydGenCommitment[p,sc,n,gj]
        optmodel.__setattr__('eHydOperSymOn', Constraint(_psn_pairs, rule=eHydOperSymOn, doc='oper symmetry-break: order identical electrolysers by ON state'))

        def eHydOperSymWarm(om, p,sc,n,gi,gj):
            return (om.vHydGenCommitment[p,sc,n,gi] + om.vHydGenStandBy[p,sc,n,gi]
                    >= om.vHydGenCommitment[p,sc,n,gj] + om.vHydGenStandBy[p,sc,n,gj])
        optmodel.__setattr__('eHydOperSymWarm', Constraint(_psn_pairs, rule=eHydOperSymWarm, doc='oper symmetry-break: order identical electrolysers by on-or-standby'))

    # Compact tight 3-state cut (feature IndElectrolyser3StateTight). The off/standby/on 2-period
    # transition polytope has one facet the loose single-period rows above miss (computed via vertex
    # enumeration of the 8 transitions): the WARM-STATE CONTINUITY facet
    #     u_t + z_t <= u_{t-1} + z_{t-1} + su_t
    # i.e. the stack is on-or-standby at t only if it was on-or-standby at t-1, or it cold-started.
    # Adding this single inequality (no new columns) completes the convex hull of the transition
    # polytope -- the same tightening as the arc/flow extended formulation but compact, so it does not
    # bloat the model or degrade the primal heuristics.
    if model.Par['pOptIndElectrolyser3StateTight'] == 1:
        def eHydElectrolyserWarmContinuity(optmodel, p,sc,n,e2h):
            if model.Par['pHydGenStandByStatus'][e2h] == 1:
                if n == model.n.first():
                    prev_warm = model.Par['pHydInitialUC'][p,sc,e2h] + model.Par['pHydInitialStandBy'][p,sc,e2h]
                else:
                    prev_warm = optmodel.vHydGenCommitment[p,sc,model.n.prev(n),e2h] + optmodel.vHydGenStandBy[p,sc,model.n.prev(n),e2h]
                return optmodel.vHydGenCommitment[p,sc,n,e2h] + optmodel.vHydGenStandBy[p,sc,n,e2h] <= prev_warm + optmodel.vHydGenStartUp[p,sc,n,e2h]
            else:
                return Constraint.Skip
        optmodel.__setattr__('eHydElectrolyserWarmContinuity', Constraint(optmodel.psne2h, rule=eHydElectrolyserWarmContinuity, doc='compact tight 3-state: warm at t requires warm at t-1 or a cold start'))

    def eAllEnergy2Ele(optmodel, p,sc,n,h2e):
        if model.Par['pEleMaxPower'][h2e][p,sc,n] and h2e in model.h2e:
            return optmodel.vEleTotalOutput[p,sc,n,h2e] == optmodel.vHydTotalCharge[p,sc,n,h2e] * model.Par['pEleGenProductionFunction'][h2e]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eAllEnergy2Ele', Constraint(optmodel.psnh2e, rule=eAllEnergy2Ele, doc='energy conversion from different energy type to electricity [p.u.]'))

    # ESS outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) bounded by the outflows data parameter [p.u.].
    # Note (audit C42): the "2Commitment" attribute name is a misnomer -- the right-hand side
    # is the parameter limit, not a commitment variable. Name kept; only the doc is corrected.
    def eEleMaxOutflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMaxOutflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyOutflows[p,sc,n,egs] / model.Par['pEleMaxOutflows'][egs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxOutflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMaxOutflows2Commitment, doc='energy outflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eEleMinOutflows2Commitment(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] and model.Par['pEleMaxPower2ndBlock'][egs][p,sc,n] and model.Par['pEleMinOutflows'][egs][p,sc,n] and (n,egs) in model.negs:
            return optmodel.vEleEnergyOutflows[p,sc,n,egs] / model.Par['pEleMinOutflows'][egs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinOutflows2Commitment', Constraint(optmodel.psnegs, rule=eEleMinOutflows2Commitment, doc='energy outflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eHydMaxOutflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMaxOutflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyOutflows[p,sc,n,hgs] / model.Par['pHydMaxOutflows'][hgs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxOutflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMaxOutflows2Commitment, doc='energy outflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eHydMinOutflows2Commitment(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinCharge'][hgs][p,sc,n] and model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] and model.Par['pHydMinOutflows'][hgs][p,sc,n] and (n,hgs) in model.nhgs:
            return optmodel.vHydEnergyOutflows[p,sc,n,hgs] / model.Par['pHydMinOutflows'][hgs][p,sc,n] >= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinOutflows2Commitment', Constraint(optmodel.psnhgs, rule=eHydMinOutflows2Commitment, doc='energy outflows bound [p.u.] (parameter limit, not commitment; audit C42)'))

    def eEleMaxEnergyOutflows(optmodel, p,sc,n,egs):
        if model.Par['pEleMaxCharge'][egs][p,sc,n] + model.Par['pEleMaxPower'][egs][p,sc,n] and (n,egs) in model.negso:
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMaxOutflows'][egs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMaxEnergyOutflows, doc='electricity energy outflows of an ESS unit [kW]'))

    def eEleMinEnergyOutflows(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n] + model.Par['pEleMinPower'][egs][p,sc,n] and (n,egs) in model.negso:
            return sum(optmodel.vEleEnergyOutflows[p,sc,n2,egs] - model.Par['pEleMinOutflows'][egs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pEleOutflowsTimeStep'][egs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMinEnergyOutflows', Constraint(optmodel.psnegs, rule=eEleMinEnergyOutflows, doc='electricity energy outflows of an ESS unit [kW]'))

    def eHydMaxEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] + model.Par['pHydMaxPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMaxOutflows'][hgs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) <= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMaxEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [kgH2/h]'))

    def eHydMinEnergyOutflows(optmodel, p,sc,n,hgs):
        if model.Par['pHydMinCharge'][hgs][p,sc,n] + model.Par['pHydMinPower'][hgs][p,sc,n] and (n,hgs) in model.nhgso:
            return sum(optmodel.vHydEnergyOutflows[p,sc,n2,hgs] - model.Par['pHydMinOutflows'][hgs][p,sc,n2] for n2 in n2_list[model.n.ord(n) - model.Par['pHydOutflowsTimeStep'][hgs]:model.n.ord(n)]) >= 0.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinEnergyOutflows', Constraint(optmodel.psnhgs, rule=eHydMinEnergyOutflows, doc='hydrogen energy outflows of an ESS unit [kgH2/h]'))

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
        if   model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs and hgt not in model.e2h and n != model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] <= optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt] - optmodel.vHydGenShutDown[p,sc,model.n.next(n),hgt]
        elif model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs and hgt not in model.e2h and n == model.n.last():
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt] / model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] <= optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxOutput2ndBlock', Constraint(optmodel.psnhgt, rule=eHydMaxOutput2ndBlock, doc='max output of the second block of a committed unit [p.u.]'))

    def eHydMinOutput2ndBlock(optmodel, p,sc,n,hgt):
        if model.Par['pHydMaxPower2ndBlock'][hgt][p,sc,n] and hgt not in model.hgs and hgt not in model.e2h:
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
            # BUGFIX (2026-07-04): the discharge-mode gate must hold whether or not the unit may
            # bid FCR. The FCR-capable branch previously relaxed the RHS to 1.0, which removed the
            # charge/discharge exclusivity for FCR-capable storage (simultaneous charge+discharge
            # in the LP) and let the mere FCR *permission* change the physical dispatch. The
            # discharge-side reserve legs (DisUpDis, NorUpDis) belong under the same gate: upward
            # reserve carried on the discharge leg needs the unit in discharge mode; a charging
            # unit offers upward reserve through the charge legs instead.
            return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxPower'][egs][p,sc,n] <= optmodel.vEleStorDischarge[p,sc,n,egs]
        elif model.Par['pEleMaxPower'][egs][p,sc,n] <= 1e-5 and model.Par['pEleGenNoDayAhead'][egs] == 0 and (model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0):
            return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs] + optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= 1.0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSOutput2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSOutput2ndBlock, doc='max output of the second block of an ESS [p.u.]'))

    def eEleMinESSOutput2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMinPower'][egs][p,sc,n]:
            # return (optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]) / model.Par['pEleMinPower'][egs][p,sc,n] >= 0.0
            if model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0:
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
            # output (discharge) is gated by the DISCHARGE binary, matching the
            # electricity ESS (eEleMaxESSOutput2ndBlock). See docs/model_audit.md.
            return optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxPower2ndBlock'][hgs][p,sc,n] <= optmodel.vHydStorDischarge[p,sc,n,hgs]
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
            # BUGFIX (2026-07-04): mirror of eEleMaxESSOutput2ndBlock — the charge-mode gate must
            # hold whether or not the unit may bid FCR (the FCR-capable branch previously relaxed
            # the RHS to 1.0). Down-reserve carried on the charge leg needs charge mode.
            return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] + optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pEleMaxCharge'][egs][p,sc,n] <= optmodel.vEleStorCharge[p,sc,n,egs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxESSCharge2ndBlock', Constraint(optmodel.psnegs, rule=eEleMaxESSCharge2ndBlock, doc='max charge of an ESS [p.u.]'))

    def eEleMinESSCharge2ndBlock(optmodel, p,sc,n,egs):
        if model.Par['pEleMinCharge'][egs][p,sc,n]:
            # return (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] - optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]) / model.Par['pEleMinCharge'][egs][p,sc,n] >= 0.0
            if  model.Par['pEleGenNoFCRD'][egs] == 0 or model.Par['pEleGenNoFCRN'][egs] == 0:
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

    # Standard min-2nd-block symmetry constraint (audit C28): with a NonNegative 2nd
    # block and a right-hand side of commitment-1 in {-1, 0}, this row is non-binding by
    # construction, exactly like eHydMinESSOutput2ndBlock / eHydMinOutput2ndBlock. The
    # state chain is enforced by eE2HMaxCharge2ndBlock; this is kept for structural
    # symmetry with the electricity ESS, not to bind.
    def eE2HMinCharge2ndBlock(optmodel, p,sc,n,e2h):
        if model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n]:
            return optmodel.vEleTotalCharge2ndBlock[p,sc,n,e2h] / model.Par['pHydMaxCharge2ndBlock'][e2h][p,sc,n] >= optmodel.vHydGenCommitment[p,sc,n,e2h] - 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eE2HMinCharge2ndBlock', Constraint(optmodel.psne2h, rule=eE2HMinCharge2ndBlock, doc='min charge of an ESS [p.u.]'))

    def eHydMaxESSCharge2ndBlock(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            # charge is gated by the CHARGE binary, matching the electricity ESS
            # (eEleMaxESSCharge2ndBlock). See docs/model_audit.md.
            return optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n] <= optmodel.vHydStorCharge[p,sc,n,hgs]
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
        # charge is normalized by the CHARGE capacity (not the output power), matching
        # the electricity ESS (eEleChargingDecision). See docs/model_audit.md.
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] :
            return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMaxCharge'][hgs][p,sc,n]  <= optmodel.vHydStorCharge[p,sc,n,hgs]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydChargingDecision', Constraint(optmodel.psnhgs, rule=eHydChargingDecision, doc='charging decision [p.u.]'))

    def eHydDischargingDecision(optmodel, p,sc,n,hgs):
        # output (discharge) is normalized by the OUTPUT power (not the charge
        # capacity), matching the electricity ESS (eEleDischargingDecision).
        if model.Par['pHydMaxPower'][hgs][p,sc,n] :
            return optmodel.vHydTotalOutput[p,sc,n,hgs] / model.Par['pHydMaxPower'][hgs][p,sc,n]  <= optmodel.vHydStorDischarge[p,sc,n,hgs]
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
        # A fuel cell (h2e) is a hydrogen-fired generator: its output is set by the
        # hydrogen-to-electricity relation eAllEnergy2Ele (output == hydrogen charge *
        # production function), not by the thermal output/2nd-block blocks. It also has no
        # vEleFreqContReserveDisUpGen reserve variable (those live on psnegt only), so skip
        # it here -- its FCR is handled by the dedicated fuel-cell headroom/endurance rules.
        if egnr in model.h2e:
            return Constraint.Skip
        if model.Par['pEleMaxPower'][egnr][p,sc,n]:
            if  egnr in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr]                                           ==                                             optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpDis[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownDis[p,sc,n,egnr]
            elif model.Par['pEleMinPower'][egnr][p,sc,n] == 0.0 and egnr not in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr]                                           ==                                             optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownGen[p,sc,n,egnr]
            elif model.Par['pEleMinPower'][egnr][p,sc,n] != 0.0 and egnr not in model.egs:
                return optmodel.vEleTotalOutput[p,sc,n,egnr] / model.Par['pEleMinPower'][egnr][p,sc,n] == optmodel.vEleGenCommitment[p,sc,n,egnr] + ((optmodel.vEleTotalOutput2ndBlock[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egnr] + model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpGen[p,sc,n,egnr] - model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownGen[p,sc,n,egnr]) / model.Par['pEleMinPower'][egnr][p,sc,n])
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalOutput', Constraint(optmodel.psnegnr, rule=eEleTotalOutput, doc='total output of a unit [kW]'))

    # Total output of an H2 producer unit [kgH2/h]
    def eHydTotalOutput(optmodel, p,sc,n,hgt):
        # e2h electrolysers are electricity-driven loads: their hydrogen output is set by
        # eAllEnergy2Hyd (output = electricity input / production function), not by an
        # independent H2-generator output block, so skip them here.
        if model.Par['pHydMaxPower'][hgt][p,sc,n] and hgt not in model.e2h:
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
    optmodel.__setattr__('eHydTotalOutput', Constraint(optmodel.psnhgt, rule=eHydTotalOutput, doc='total output of an H2 producer unit [kgH2/h]'))

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
                    return optmodel.vEleTotalCharge[p,sc,n,egs]                                           ==                                           optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] + model.Par['pHydGenStandByPower'][egs] * optmodel.vHydGenStandBy[p,sc,n,egs] - model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] - model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]
                else:
                    return optmodel.vEleTotalCharge[p,sc,n,egs] / model.Par['pHydMinCharge'][egs][p,sc,n] == optmodel.vHydGenCommitment[p,sc,n,egs] + (optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs] / model.Par['pHydMinCharge'][egs][p,sc,n]) + (model.Par['pHydGenStandByPower'][egs] / model.Par['pHydMinCharge'][egs][p,sc,n]) * optmodel.vHydGenStandBy[p,sc,n,egs] + (- model.Par['pOperatingReserveActivation_FCRD_Up'][p,sc,n] * optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRD_Down'][p,sc,n] * optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs] - model.Par['pOperatingReserveActivation_FCRN_Up'][p,sc,n] * optmodel.vEleFreqContReserveNorUpCha[p,sc,n,egs] + model.Par['pOperatingReserveActivation_FCRN_Down'][p,sc,n] * optmodel.vEleFreqContReserveNorDownCha[p,sc,n,egs]) / model.Par['pHydMinCharge'][egs][p,sc,n]
            elif model.Par['pHydMaxCharge'][egs][p,sc,n]:
                # Fixed consumption: MinCharge == MaxCharge so the 2nd block is empty. The
                # charge is then not free -- it is MinCharge when committed plus the standby
                # draw (a fixed-consumption unit cannot modulate, so no 2nd block and no FCR).
                # Without this branch the constraint was skipped and vEleTotalCharge[e2h] was
                # free in [0, MaxCharge] with no commitment link (C12).
                return optmodel.vEleTotalCharge[p,sc,n,egs] == model.Par['pHydMinCharge'][egs][p,sc,n] * optmodel.vHydGenCommitment[p,sc,n,egs] + model.Par['pHydGenStandByPower'][egs] * optmodel.vHydGenStandBy[p,sc,n,egs]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleTotalCharge', Constraint(optmodel.psneh, rule=eEleTotalCharge, doc='total charge of an ESS unit [kW]'))

    # Total charge of an H2 ESS unit [kgH2/h]
    def eHydTotalCharge(optmodel, p,sc,n,hgs):
        if model.Par['pHydMaxCharge'][hgs][p,sc,n] and model.Par['pHydMaxCharge2ndBlock'][hgs][p,sc,n]:
            if model.Par['pHydMinCharge'][hgs][p,sc,n] == 0.0:
                return optmodel.vHydTotalCharge[p,sc,n,hgs]                                           ==                                                    optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs]
            else:
                return optmodel.vHydTotalCharge[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n] == optmodel.vHydStorCharge[p,sc,n,hgs] + (optmodel.vHydTotalCharge2ndBlock[p,sc,n,hgs] / model.Par['pHydMinCharge'][hgs][p,sc,n])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydTotalCharge', Constraint(optmodel.psnhgs, rule=eHydTotalCharge, doc='total charge of an H2 ESS unit [kgH2/h]'))

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
        # e2h electrolysers run as flexible loads (free on/off via vHydGenCommitment on the
        # charge side); they are not pre-committed and carry no startup/shutdown logic.
        if (model.Par['pHydMinPower'][hgt][p,sc,n] or model.Par['pHydGenConstantTerm'][hgt] or model.Par['pOptIndBinGenMinTime'] == 1) and hgt not in model.hgs and hgt not in model.e2h:
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
                return (- max(model.Par['pEleInitialOutput'][p,sc,egt] - model.Par['pEleMinPower'][egt][p,sc,n],0.0)                                               + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
            else:
                return (- optmodel.vEleTotalOutput2ndBlock[p,sc,model.n.prev(n),egt] - optmodel.vEleFreqContReserveDisDownGen[p,sc,model.n.prev(n),egt] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisUpGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampUp'][egt] <=   optmodel.vEleGenCommitment[p,sc,n,egt] - optmodel.vEleGenStartUp[p,sc,n,egt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleMaxRampUpOutput', Constraint(optmodel.psnegt, rule=eEleMaxRampUpOutput, doc='maximum ramp up   [p.u.]'))

    def eEleMaxRampDwOutput(optmodel, p,sc,n,egt):
        if model.Par['pEleGenRampDown'][egt] and model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pEleGenRampDown'][egt] < model.Par['pEleMaxPower2ndBlock'][egt][p,sc,n]:
            if n == model.n.first():
                return (- max(model.Par['pEleInitialOutput'][p,sc,egt] - model.Par['pEleMinPower'][egt][p,sc,n],0.0)                                             + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt] + optmodel.vEleFreqContReserveDisDownGen[p,sc,n,egt]) / model.Par['pDuration'][p,sc,n] / model.Par['pEleGenRampDown'][egt] >= - model.Par['pEleInitialUC'][p,sc,egt]                 + optmodel.vEleGenShutDown[p,sc,n,egt]
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
        if model.Par['pHydGenRampUp'][hgt] > 0 and model.Par['pOptIndBinGenRamps'] == 1 and hgt not in model.e2h:
            if n == model.n.first():
                return (                                                               optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgt] <=   optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
            else:
                return (- optmodel.vHydTotalOutput2ndBlock[p,sc,model.n.prev(n),hgt] + optmodel.vHydTotalOutput2ndBlock[p,sc,n,hgt]) / model.Par['pDuration'][p,sc,n] / model.Par['pHydGenRampUp'][hgt] <=   optmodel.vHydGenCommitment[p,sc,n,hgt] - optmodel.vHydGenStartUp[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampUpOutput', Constraint(optmodel.psnhgt, rule=eHydMaxRampUpOutput, doc='maximum ramp up   output [p.u.]'))

    def eHydMaxRampDwOutput(optmodel, p,sc,n,hgt):
        if model.Par['pHydGenRampDown'][hgt] > 0 and model.Par['pOptIndBinGenRamps'] == 1 and hgt not in model.e2h:
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
    # Audit C37: these charge/outflow ramps reuse the generation ramp parameter
    # pHydGenRampUp/Down because no dedicated hydrogen outflow-ramp parameter exists in the
    # input schema (the electricity side defines pEleGenOutflowsRampUp/Down but leaves the
    # matching constraint commented out, so electricity storage currently has no outflow
    # ramp at all). The physical charge/outflow ramp of an H2 store can differ from its
    # generation ramp; adding a dedicated pHydGenOutflowsRamp* parameter (with a fallback to
    # the generation ramp, keeping existing cases unchanged) is the documented follow-up.
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

    # Minimum up time and down time of an electrolyzer [h]. (hgt = schedulable H2 generators only;
    # electrolysers are e2h and get their own min-time block below.)
    def eHydMinUpTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenUpTime'][hgt] > 1 and hgt not in model.e2h and model.n.ord(n) > (model.Par['pHydGenUpTime'][hgt] - model.Par['pHydGenUpTimeZero'][hgt]):
            return sum(optmodel.vHydGenStartUp[p,sc,n2,hgt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pHydGenUpTime'   ][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenUpTime'  ][hgt] - model.Par['pHydGenUpTimeZero'  ][hgt])*(  model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <=     optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinUpTime', Constraint(optmodel.psnhgt, rule=eHydMinUpTime, doc='minimum up   time [h]'))

    def eHydMinDownTime(optmodel, p,sc,n,hgt):
        if model.Par['pOptIndBinGenMinTime'] == 1 and model.Par['pHydGenDownTime'][hgt] > 1 and hgt not in model.e2h and model.n.ord(n) > (model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt]):
            return sum(optmodel.vHydGenShutDown[p,sc,n2,hgt] for n2 in n2_list[int(max(model.n.ord(n)-model.Par['pHydGenDownTime'][hgt], max(0,min(model.n.ord(n),(model.Par['pHydGenDownTime'][hgt] - model.Par['pHydGenDownTimeZero'][hgt])*(1-model.Par['pHydInitialUC'][p,sc,hgt]))))):model.n.ord(n)]) <= 1 - optmodel.vHydGenCommitment[p,sc,n,hgt]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eHydMinDownTime', Constraint(optmodel.psnhgt, rule=eHydMinDownTime, doc='minimum down time [h]'))

    # --- Electrolyser (e2h) production ramp limit ---------------------------------------------------
    # Physical realism (spec sec 7a): the electrolyser's electricity draw cannot swing arbitrarily fast.
    # NOTE: minimum up/down time is deliberately NOT applied to e2h -- electrolysers are modelled as free
    # flexible loads (commitment tied to consumption), so forcing min-time/commitment drives production to
    # zero (verified 2026-07-09), and physically an electrolyser cycles in seconds-minutes, not hours. The
    # ramp is the meaningful, LP-preserving lever. Opt-in via build_case ELE_RAMP (RampUp/RampDown +
    # IndBinGenRamps); default off so cases are byte-unchanged.
    # RampUp/RampDown are ABSOLUTE rates (kW per hour) -- scaled by the model like the power vars, so
    # the constraint is factor1-invariant. build_case sets them = fraction x MaxCharge.
    def eHydMaxRampUpE2H(optmodel, p,sc,n,e2h):
        if model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pHydGenRampUp'][e2h] and n != model.n.first():
            return optmodel.vEleTotalCharge[p,sc,n,e2h] - optmodel.vEleTotalCharge[p,sc,model.n.prev(n),e2h] <= model.Par['pHydGenRampUp'][e2h] * model.Par['pDuration'][p,sc,n]
        return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampUpE2H', Constraint(optmodel.psne2h, rule=eHydMaxRampUpE2H, doc='e2h max ramp up on consumption [kW/h]'))

    def eHydMaxRampDwE2H(optmodel, p,sc,n,e2h):
        if model.Par['pOptIndBinGenRamps'] == 1 and model.Par['pHydGenRampDown'][e2h] and n != model.n.first():
            return optmodel.vEleTotalCharge[p,sc,model.n.prev(n),e2h] - optmodel.vEleTotalCharge[p,sc,n,e2h] <= model.Par['pHydGenRampDown'][e2h] * model.Par['pDuration'][p,sc,n]
        return Constraint.Skip
    optmodel.__setattr__('eHydMaxRampDwE2H', Constraint(optmodel.psne2h, rule=eHydMaxRampDwE2H, doc='e2h max ramp down on consumption [kW/h]'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eEleMinUpTime) > 0 or len(optmodel.eEleMinDownTime) > 0 or len(optmodel.eHydMinUpTime) > 0 or len(optmodel.eHydMinDownTime) > 0:
        log_time('--- Declaring the minimum up and down time:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time
    if len(optmodel.eHydMaxRampUpE2H) > 0 or len(optmodel.eHydMaxRampDwE2H) > 0:
        log_time(f'--- Declaring the electrolyser ramp limits (e2h ramp-up rows: {len(optmodel.eHydMaxRampUpE2H)}):', StartTime, ind_log=indlog)
        StartTime = time.time()

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
    optmodel.__setattr__('eEleTotalMaxChargeConditioned', Constraint(optmodel.psneh, rule=eEleTotalMaxChargeConditioned, doc='total charge of an ESS unit [kW]'))

    # print if the constraints object len is greater than 0
    # if len(optmodel.eEleMinEnergyStartUp) > 0 or len(optmodel.eEleTotalMaxChargeConditioned) > 0:
    if len(optmodel.eEleTotalMaxChargeConditioned) > 0:
        log_time('--- Declaring the minimum energy start up and total max charge:', StartTime, ind_log=indlog)
        StartTime = time.time() # to compute elapsed time

    # The peak-hour rules compare the grid import against a per-retailer "adjusted
    # import": a night-discount factor on the import (the night window is set per
    # retailer by StartNightTime / EndNightTime), plus -- only when the retailer
    # carries no demand -- a fixed addend so an idle retailer still registers a
    # baseline. The four night/day factors are read from the retailer data
    # (PeakNightBuyFactor / PeakDayBuyFactor / PeakNightAddend / PeakDayAddend); when a
    # column is absent they fall back to the historical defaults, which depend on the
    # tariff type (Hourly: 1, 1, 1, 1; Daily: 0.5, 1, 2, 5). One helper in place of the
    # same block previously copied across the six peak rules.
    def _ret_factor(er, name, default):
        try:
            return float(model.Par[f'pEleRet{name}'][er])
        except (KeyError, TypeError, ValueError):
            return default

    def _adjusted_import(optmodel, p, sc, n, er):
        is_daily = model.Par['pEleRetTariffType'][er] == 'Daily'
        d_buy_night, d_buy_day, d_add_night, d_add_day = (
            (0.5, 1.0, 2.0, 5.0) if is_daily else (1.0, 1.0, 1.0, 1.0))
        buy_night = _ret_factor(er, 'PeakNightBuyFactor', d_buy_night)
        buy_day = _ret_factor(er, 'PeakDayBuyFactor', d_buy_day)
        add_night = _ret_factor(er, 'PeakNightAddend', d_add_night)
        add_day = _ret_factor(er, 'PeakDayAddend', d_add_day)
        hour = optmodel.n.ord(n) % 24
        is_night = (hour >= model.Par['pEleRetStartNightTime'][er]
                    or hour <= model.Par['pEleRetEndNightTime'][er])
        buy_factor = buy_night if is_night else buy_day
        addend = add_night if is_night else add_day
        base = optmodel.vEleImport[p, sc, n, model.Par['pEleRetNode'][er]]
        has_demand = sum(model.Par['pVarMaxDemand'][ed][p, sc, n]
                         for ed in model.ed if (er, ed) in model.r2ed) > 0
        return (buy_factor * base) if has_demand else (buy_factor * (base + addend * model.factor1))   # addend is a kW quantity -> scale by factor1 (audit C38)

    def eElePeakHourValue(optmodel, p,sc,n,er,m,peak):
        # Check applicability
        if model.Par['pOptIndPeakThresholdLP'] == 0 and model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            # Peak-hour logic
            if peak == optmodel.Peaks.first():
                return optmodel.vEleDemPeakGlobal[p, sc, m, er, peak] >= adjusted_buy
            else:
                return optmodel.vEleDemPeakGlobal[p, sc, m, er, peak] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * sum(optmodel.vElePeakGlobalInd[p,sc,n,er,peak2] for peak2 in optmodel.Peaks if peak2 < peak)
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourValue', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourValue, doc='peak hour selection'))

    def eElePeakHourInd_C1(optmodel, p,sc,n,er,m,peak):
        if model.Par['pOptIndPeakThresholdLP'] == 0 and model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakGlobalInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C1', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C1, doc='peak hour indicator'))

    def eElePeakHourInd_C2(optmodel, p,sc,n,er,m,peak):
        if model.Par['pOptIndPeakThresholdLP'] == 0 and model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            # Peak-hour logic
            return optmodel.vEleDemPeakGlobal[p,sc,m,er,peak] <= adjusted_buy + model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakGlobalInd[p,sc,n,er,peak])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakHourInd_C2', Constraint(optmodel.psner, optmodel.moy, optmodel.Peaks, rule=eElePeakHourInd_C2, doc='peak hour indicator'))

    def eElePeakNumberMonths(optmodel, m,peak):
        if model.Par['pOptIndPeakThresholdLP'] == 0 and model.Par['pParNumberPowerPeaks'] > 0 and sum(model.Par['pEleRetPowerTariff'][er] for er in model.er if model.Par['pEleRetTariffType'][er] == 'Hourly') > 0:
            return sum(optmodel.vElePeakGlobalInd[p,sc,n,er,peak] for p,sc,n,er in model.psner if model.Par['pEleRetPowerTariff'][er] and (n,m) in model.n2m) == 1
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakNumberMonths', Constraint(optmodel.moy, optmodel.Peaks, rule=eElePeakNumberMonths, doc='peak number of months'))

    # Exact binary-free peak charge (CVaR / sum-of-largest). The billed monthly peak
    # is the mean of the N_pk highest hourly imports. Because the objective minimises
    # the peak charge and the charge increases with import, that mean equals
    #     billed_m = t_m + (1/N_pk) * sum_{n in m} s_n,   s_n >= import_n - t_m,  s_n >= 0,
    # with t_m free (it settles at the N_pk-th largest import). No binaries, exact,
    # tight LP -- the same threshold reformulation the decomposition path already uses.
    # Built in place of the big-M peak-hour selection when pOptIndPeakThresholdLP == 1
    # (Hourly tariff only). One slack constraint per (hour, retailer); the threshold
    # and the (1/N_pk) average enter the cost in eTotalElePeakCost.
    def eElePeakThreshold(optmodel, p,sc,n,er,m):
        if model.Par['pOptIndPeakThresholdLP'] == 1 and model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m:
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            return optmodel.vElePeakSlack[p,sc,n,er] >= adjusted_buy - optmodel.vElePeakThreshold[p,sc,m,er]
        else:
            return Constraint.Skip
    optmodel.__setattr__('eElePeakThreshold', Constraint(optmodel.psner, optmodel.moy, rule=eElePeakThreshold, doc='peak threshold (CVaR/sum-of-largest)'))

    # N2T hogbelastningsavgift: a SECOND demand charge on the single highest import during
    # hoglasttid (weekdays 06-22, winter months), via the per-hour pEleHighLoadHour mask.
    # vEleHighLoadPeak[m] >= import on every masked hour of month m -> at the optimum it equals
    # that month's highest hoglasttid import (an exact, binary-free max). Months with no masked
    # hour leave it at its zero lower bound, so it bills nothing outside the winter window.
    # Charged in eTotalElePeakCost at pEleRetHighLoadTariff. Built only when the case carries the
    # tariff column (pEleRetHighLoadTariff) and the hoglasttid mask.
    _highload_on = 'pEleRetHighLoadTariff' in model.Par
    def eEleHighLoadPeak(optmodel, p,sc,n,er,m):
        if (_highload_on and model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er]
                and model.Par['pEleRetTariffType'][er] == 'Hourly' and (n,m) in optmodel.n2m
                and model.Par['pEleHighLoadHour'][p,sc,n] > 0.5):
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            return optmodel.vEleHighLoadPeak[p,sc,m,er] >= adjusted_buy
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleHighLoadPeak', Constraint(optmodel.psner, optmodel.moy, rule=eEleHighLoadPeak, doc='N2T hogbelastning peak (highest hoglasttid hour per month)'))

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
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
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
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
            # Peak-hour logic
            return optmodel.vEleDemPeakDay[p,sc,d,er] >= adjusted_buy - model.Par['pEleRetMaximumEnergySell'][er] * (1 - optmodel.vElePeakDayInd[p,sc,d,n,er])
        else:
            return Constraint.Skip
    optmodel.__setattr__('eEleDailyPeakInd_C1', Constraint(optmodel.psdner, rule=eEleDailyPeakInd_C1, doc='daily peak hour indicator'))

    def eEleDailyPeakInd_C2(optmodel, p,sc,d,n,er):
        if model.Par['pParNumberPowerPeaks'] > 0 and model.Par['pEleRetPowerTariff'][er] and model.Par['pEleRetTariffType'][er] == 'Daily' and (n,d) in optmodel.n2d:
            adjusted_buy = _adjusted_import(optmodel, p, sc, n, er)
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

    # Transport mode (TRANSPORT_NET=1): drop the DC Kirchhoff (voltage-angle) equation. On a RADIAL
    # network with unbounded voltage angles it is exactly redundant -- flows are fully determined by
    # the nodal balance -- so removing it is bit-identical while eliminating its ill-conditioned
    # 1/(reactance*TTC) coefficients (the [1e-4, 3e4] matrix range that stalls the barrier). Only safe
    # on radial networks; on meshed networks the angle constraint carries the loop-flow physics.
    _transport_net = os.environ.get('TRANSPORT_NET', '0') == '1'

    def eKirchhoff2ndLaw(optmodel, p,sc,n,ni,nf,cc):
        if not _transport_net and model.Par[('pOptIndBinSingleNode')] == 0 and model.Par['pEleNetInitialPeriod'][ni,nf,cc] <= model.Par['pParEconomicBaseYear'] and model.Par['pEleNetFinalPeriod'][ni,nf,cc] >= model.Par['pParEconomicBaseYear'] and (ni,nf,cc) in model.elea:
            return optmodel.vEleNetFlow[p,sc,n,ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] - (optmodel.vEleNetTheta[p,sc,n,ni] - optmodel.vEleNetTheta[p,sc,n,nf]) / model.Par['pEleNetReactance'][ni,nf,cc] / model.Par['pEleNetTTC'][ni,nf,cc] * 0.1 == 0
        else:
            return Constraint.Skip
    optmodel.__setattr__('eKirchhoff2ndLaw', Constraint(optmodel.psnela, rule=eKirchhoff2ndLaw, doc='Kirchhoff 1st Law'))

    # print if the constraints object len is greater than 0
    if len(optmodel.eKirchhoff2ndLaw) > 0:
        log_time('--- Declaring the Kirchhoff 2nd Law:', StartTime, ind_log=indlog)

    return model