# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Green-hydrogen temporal matching and electricity PPA settlement for el1xr_opt.
#
# The hourly temporal-matching (additionality) requirement implements the
# renewable-fuels-of-non-biological-origin (RFNBO) rule of EU Delegated
# Regulation 2023/1184: the electricity used to produce "green" hydrogen must be
# covered by renewable generation matched in the same period.
#
# DRAFT FOR REVIEW. Confirm the items marked "REVIEW:" below (matching window,
# PPA cost units, physical vs virtual PPA).

import time
from   pyomo.environ  import Constraint
from  .utils.oM_Utils import log_time


def _option(model, key, default=0):
    """Return an options-table flag, or a default if it is not present."""
    try:
        return int(model.Par[key])
    except (KeyError, TypeError, ValueError):
        return default


def _gen_flag(model, key, unit, default=0):
    """Return a per-unit flag, or a default if the parameter/unit is absent."""
    try:
        return int(model.Par[key][unit])
    except (KeyError, TypeError, ValueError):
        return default


def create_green_hydrogen(model, optmodel, indlog):
    """Add green-hydrogen temporal matching and electricity PPA settlement.

    Two additive features:

    1. **Hourly temporal matching (additionality).** When the option
       ``pParGreenH2Matching`` is set, the electricity drawn by electrolysers in
       each load level must not exceed the renewable generation available to the
       operator in that same load level (own renewable units plus any
       PPA-contracted renewable units). With hourly load levels this is the
       strict hourly RFNBO matching rule.

    2. **Electricity PPA settlement.** The variables ``vTotalEleMrkPPACost`` and
       ``vTotalEleMrkPPARev`` are fixed to zero in ``create_variables``
       (electricity PPA off by default). When renewable units are flagged as
       PPA-contracted (``pEleGenPPA``), this function frees the PPA cost variable
       and defines it as the take-as-produced payment for the contracted
       generation. Hydrogen PPA is already handled in the model.

    PPA-contracted units are renewable generators (subset of ``egr``) that the
    operator pays for at a fixed price; being physical generators they are already
    in the energy balance, so they also count toward the matching pool. If no unit
    is flagged and the matching option is off, this function changes nothing, so
    existing cases are unaffected.

    Run it after ``create_constraints``.
    """
    StartTime = time.time()

    print('-- Declaring green-hydrogen temporal matching and electricity PPA')

    # PPA-contracted renewable generators (subset of the RES units)
    ppa_units = [egr for egr in model.egr if _gen_flag(model, 'pEleGenPPA', egr) == 1]

    # %% Electricity PPA settlement
    # vTotalEleMrkPPACost is referenced by eEleMarketCost but bounded to zero by
    # default. Enable and define it only when PPA units exist.
    if ppa_units:
        def eEleMarketPPACost(optmodel, p, sc, n):
            # free the zero upper bound so the cost can take a positive value
            optmodel.vTotalEleMrkPPACost[p, sc, n].setlb(0.0)
            optmodel.vTotalEleMrkPPACost[p, sc, n].setub(None)
            # REVIEW (units): mirrors the day-ahead market cost (price x quantity,
            # no model.factor1). Confirm against the operating-cost scale.
            return optmodel.vTotalEleMrkPPACost[p, sc, n] == sum(
                model.Par['pEleGenPPAPrice'][egppa] * optmodel.vEleTotalOutput[p, sc, n, egppa] for egppa in ppa_units)
        optmodel.__setattr__('eEleMarketPPACost', Constraint(model.psn, rule=eEleMarketPPACost, doc='electricity PPA take-as-produced cost'))
        # REVIEW (virtual PPA): vTotalEleMrkPPARev stays at zero (physical PPA).
        # For a virtual PPA contract-for-difference, free and define it here too.

    # %% Hourly temporal matching (RFNBO additionality)
    if _option(model, 'pParGreenH2Matching') == 1:
        if len(model.e2h):
            # REVIEW (window): per-load-level matching equals the model time
            # resolution (hourly when load levels are hours). For monthly matching,
            # sum both sides over the months instead of per load level.
            # REVIEW (allocation): this aggregate form lets the same renewable MWh
            # count for both export and electrolyser supply. A strict version adds
            # a renewable-to-electrolyser allocation variable.
            def eGreenH2Matching(optmodel, p, sc, n):
                return (sum(optmodel.vEleTotalCharge[p, sc, n, e2h] for e2h in model.e2h) <=
                        sum(optmodel.vEleTotalOutput[p, sc, n, egr] for egr in model.egr))
            optmodel.__setattr__('eGreenH2Matching', Constraint(model.psn, rule=eGreenH2Matching, doc='hourly renewable temporal matching for green hydrogen'))
        else:
            print('   green-H2 matching requested but no electrolysers (e2h) in the case; skipped')

    log_time('--- Declaring green-hydrogen matching and electricity PPA:', StartTime, ind_log=indlog)

    return model
