# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Investment (capacity-sizing) layer for el1xr_opt.
#
# The capacity-expansion formulation follows the generation and storage
# investment approach of the openTEPES model:
#   A. Ramos, E. F. Alvarez, S. Lumbreras, "openTEPES: Open-source Transmission
#   and Generation Expansion Planning," SoftwareX 18 (2022) 101070.
#   https://doi.org/10.1016/j.softx.2022.101070
#
# DRAFT FOR REVIEW. Before solving with this layer, confirm the items marked
# "REVIEW:" below (cost interpretation, units, electrolyser input coupling).

import time
from   pyomo.environ  import Var, Constraint, Binary, UnitInterval, NonNegativeReals
from  .utils.oM_Utils import log_time


def create_investment(model, optmodel, indlog):
    """Add the capacity-sizing (investment) layer to the model.

    Candidate units are those with a positive investment cost. In this model the
    generator sets already include storage, so the candidates are collected in
    ``egc`` (electricity, includes BESS and fuel cells) and ``hgc`` (hydrogen,
    includes electrolysers and hydrogen storage); ``egsc`` and ``hgsc`` are the
    storage subsets. For each candidate the model chooses a build fraction in
    ``[0, 1]`` (or a binary build decision); the usable capacity is the nameplate
    capacity times that fraction. The annualized build cost enters the objective
    through ``vTotalICost``.

    This function is additive: it introduces new variables and constraints plus a
    single extra term in the objective. It does not modify any existing operating
    constraint. Run it after ``create_variables`` and before
    ``create_objective_function`` so that ``vTotalICost`` exists when the total
    system cost is assembled.
    """
    StartTime = time.time()

    print('-- Declaring investment (capacity-sizing) layer')

    # Always create the total investment-cost variable so the objective can use
    # it even when there are no candidate units.
    # Audit C38: the unit label was [MEUR], but vTotalICost is added directly to the [EUR]
    # operating-cost components in eTotalSCost (no unit conversion), so it must be in the same
    # unit -- EUR (whatever native currency the data uses; the demo prints SEK). Label fixed.
    setattr(optmodel, 'vTotalICost', Var(within=NonNegativeReals, doc='total annualized investment cost [EUR]'))

    if not len(model.egc) and not len(model.hgc):
        optmodel.vTotalICost.fix(0.0)
        log_time('--- Declaring the investment layer (no candidate units):', StartTime, ind_log=indlog)
        return model

    # %% Build-decision variables (fraction of nameplate built, in [0, 1])
    setattr(optmodel, 'vEleGenInvest', Var(model.egc, within=UnitInterval, doc='electricity candidate build fraction [0,1]'))
    setattr(optmodel, 'vHydGenInvest', Var(model.hgc, within=UnitInterval, doc='hydrogen    candidate build fraction [0,1]'))

    # Make the decision binary (all-or-nothing build) for units flagged for it.
    for egc in model.egc:
        try:
            if model.Par['pEleGenBinaryInvestment'][egc] == 1:
                optmodel.vEleGenInvest[egc].domain = Binary
        except (KeyError, TypeError):
            pass
    for hgc in model.hgc:
        try:
            if model.Par['pHydGenBinaryInvestment'][hgc] == 1:
                optmodel.vHydGenInvest[hgc].domain = Binary
        except (KeyError, TypeError):
            pass

    # Optional lower/upper bounds on the build fraction, if provided in the data.
    for egc in model.egc:
        try:
            optmodel.vEleGenInvest[egc].setlb(model.Par['pEleGenInvestmentLo'][egc])
        except (KeyError, TypeError):
            pass
        try:
            optmodel.vEleGenInvest[egc].setub(model.Par['pEleGenInvestmentUp'][egc])
        except (KeyError, TypeError):
            pass
    for hgc in model.hgc:
        try:
            optmodel.vHydGenInvest[hgc].setlb(model.Par['pHydGenInvestmentLo'][hgc])
        except (KeyError, TypeError):
            pass
        try:
            optmodel.vHydGenInvest[hgc].setub(model.Par['pHydGenInvestmentUp'][hgc])
        except (KeyError, TypeError):
            pass

    # %% Capacity coupling: an unbuilt candidate has zero usable capacity.
    # These are extra caps on top of the existing nameplate bounds, so they are
    # purely additive (no existing constraint is changed). With a build fraction
    # of 1 the existing nameplate bound binds; with 0 the unit is forced to zero.
    psnegc  = [(p, sc, n, egc ) for (p, sc, n) in model.psn for egc  in model.egc ]
    psnegsc = [(p, sc, n, egsc) for (p, sc, n) in model.psn for egsc in model.egsc]
    psnhgc  = [(p, sc, n, hgc ) for (p, sc, n) in model.psn for hgc  in model.hgc ]
    psnhgsc = [(p, sc, n, hgsc) for (p, sc, n) in model.psn for hgsc in model.hgsc]
    # candidate electrolysers (e2h units that are investment candidates): their
    # design variable is the ELECTRICITY input, so the build decision must cap it.
    e2hc    = [g for g in model.e2h if g in model.hgc]
    psne2hc = [(p, sc, n, g) for (p, sc, n) in model.psn for g in e2hc]

    # Electricity candidate output (generators, fuel cells, storage discharge).
    def eEleInvestMaxOutput(optmodel, p, sc, n, egc):
        return optmodel.vEleTotalOutput[p, sc, n, egc] <= model.Par['pEleMaxPower'][egc][p, sc, n] * optmodel.vEleGenInvest[egc]
    optmodel.__setattr__('eEleInvestMaxOutput', Constraint(psnegc, rule=eEleInvestMaxOutput, doc='candidate electricity output limited by build decision'))

    # Electricity candidate storage: charge power and stored energy.
    def eEleInvestMaxCharge(optmodel, p, sc, n, egsc):
        return optmodel.vEleTotalCharge[p, sc, n, egsc] <= model.Par['pEleMaxCharge'][egsc][p, sc, n] * optmodel.vEleGenInvest[egsc]
    optmodel.__setattr__('eEleInvestMaxCharge', Constraint(psnegsc, rule=eEleInvestMaxCharge, doc='candidate electricity charge limited by build decision'))

    def eEleInvestMaxInventory(optmodel, p, sc, n, egsc):
        return optmodel.vEleInventory[p, sc, n, egsc] <= model.Par['pEleMaxStorage'][egsc][p, sc, n] * model.factor1 * optmodel.vEleGenInvest[egsc]
    optmodel.__setattr__('eEleInvestMaxInventory', Constraint(psnegsc, rule=eEleInvestMaxInventory, doc='candidate electricity storage energy limited by build decision'))

    # Hydrogen candidate output (electrolysers, hydrogen generators, storage discharge).
    def eHydInvestMaxOutput(optmodel, p, sc, n, hgc):
        return optmodel.vHydTotalOutput[p, sc, n, hgc] <= model.Par['pHydMaxPower'][hgc][p, sc, n] * optmodel.vHydGenInvest[hgc]
    optmodel.__setattr__('eHydInvestMaxOutput', Constraint(psnhgc, rule=eHydInvestMaxOutput, doc='candidate hydrogen output limited by build decision'))

    # Hydrogen candidate storage: stored energy. factor1 converts the storage-energy
    # units, matching eEleInvestMaxInventory and the hydrogen inventory variable bound.
    def eHydInvestMaxInventory(optmodel, p, sc, n, hgsc):
        return optmodel.vHydInventory[p, sc, n, hgsc] <= model.Par['pHydMaxStorage'][hgsc][p, sc, n] * model.factor1 * optmodel.vHydGenInvest[hgsc]
    optmodel.__setattr__('eHydInvestMaxInventory', Constraint(psnhgsc, rule=eHydInvestMaxInventory, doc='candidate hydrogen storage energy limited by build decision'))

    # Candidate electrolyser electricity input. An electrolyser (e2h) converts
    # electricity to hydrogen at vHydTotalOutput == vEleTotalCharge / ProductionFunction
    # (eAllEnergy2Hyd), so its production is set by the ELECTRICITY input, not the
    # hydrogen-output nameplate. Sizing it only through the output cap above leaves the
    # electricity input fixed at its operating bound, so building a larger unit buys
    # no extra production. Cap the electricity input by the build decision too, so the
    # input capacity (the real design variable) scales with the investment.
    def eHydInvestMaxCharge(optmodel, p, sc, n, e2hc):
        return optmodel.vEleTotalCharge[p, sc, n, e2hc] <= model.Par['pHydMaxCharge'][e2hc][p, sc, n] * optmodel.vHydGenInvest[e2hc]
    optmodel.__setattr__('eHydInvestMaxCharge', Constraint(psne2hc, rule=eHydInvestMaxCharge, doc='candidate electrolyser electricity input limited by build decision'))

    # Candidate hydrogen storage: hydrogen charge (inflow into the store). Like the
    # electricity storage charge cap (eEleInvestMaxCharge), an unbuilt candidate store
    # must not be able to absorb hydrogen at nameplate (and spill it for free); cap the
    # charge by the build decision too (C21a).
    def eHydInvestMaxStorageCharge(optmodel, p, sc, n, hgsc):
        return optmodel.vHydTotalCharge[p, sc, n, hgsc] <= model.Par['pHydMaxCharge'][hgsc][p, sc, n] * optmodel.vHydGenInvest[hgsc]
    optmodel.__setattr__('eHydInvestMaxStorageCharge', Constraint(psnhgsc, rule=eHydInvestMaxStorageCharge, doc='candidate hydrogen storage charge limited by build decision'))

    # %% Total investment cost
    # Unit scaling: model.factor1 is the conversion factor that lets the model work
    # at either utility (MWh) or local/home (kWh) scale. It is applied to the
    # capacities (MaximumPower, MaximumCharge, ...) and to the per-energy operating
    # costs. The investment cost pays for capacity whose operation scales with
    # factor1, so it is scaled by factor1 too. This keeps the build-versus-operate
    # trade-off invariant under the unit choice, and means FixedInvestmentCost is
    # entered in the same native units as the rest of the data.
    # pEleGenInvestCost / pHydGenInvestCost are the annualized fixed cost of the
    # FULL nameplate unit (FixedInvestmentCost * FixedChargeRate), so with a build
    # fraction in [0,1] the cost of a partially built unit is the simple product.
    # Asserted convention (audit C38): this factor1 multiplication is only dimensionally
    # consistent because EVERY objective term (operating costs and this investment cost) is
    # scaled by factor1, so factor1 acts as a single global objective scalar that does not
    # change the argmin -- the build-vs-operate trade-off stays invariant under the unit
    # choice. This holds at the shipped default factor1 == 1 (where it is a no-op); a
    # factor1 != 1 regression test is the documented follow-up.
    #
    # Period weighting: operating costs enter the objective weighted by
    # pDiscountFactor[p] per period (eTotalTCost). The annualized investment cost
    # recurs in every modeled period, so it is weighted by the sum of the period
    # discount factors. This puts investment on the same discounted, period-weighted
    # footing as operation, matching the openTEPES treatment, so the build/operate
    # trade-off is consistent for any modeled horizon.
    period_weight = sum(model.Par['pDiscountFactor'][p] for p in model.p)

    def eTotalICost(optmodel):
        return optmodel.vTotalICost == period_weight * model.factor1 * (
            sum(model.Par['pEleGenInvestCost'][egc] * optmodel.vEleGenInvest[egc] for egc in model.egc) +
            sum(model.Par['pHydGenInvestCost'][hgc] * optmodel.vHydGenInvest[hgc] for hgc in model.hgc))
    optmodel.__setattr__('eTotalICost', Constraint(rule=eTotalICost, doc='total period-weighted investment cost'))

    log_time('--- Declaring the investment (capacity-sizing) layer:', StartTime, ind_log=indlog)

    return model
