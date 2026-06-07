# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Energy-community / virtual-sharing layer for el1xr_opt (Phase 6a).
#
# Lets retailers (members) in the same zone share locally generated electricity
# before importing from / exporting to the grid. "Virtual" sharing: the allocation
# is financial/metering, the existing grid carries the power. This is a linear
# layer added on top of the retail model and is OFF by default, enabled with the
# option flag ``IndBinCommunity`` so existing cases are unchanged.
#
# How it works:
#   * Each member er gets two non-negative variables per period/scenario/load level:
#       vEleShareOut[p,sc,n,er]  energy contributed to the community pool
#       vEleShareIn [p,sc,n,er]  energy received from the community pool
#   * The retail balance (in oM_ModelFormulation.eEleRetNodeBalance) gains
#       + vEleShareIn - vEleShareOut
#     so received energy helps meet demand and contributed energy uses local
#     surplus, exactly like buy/sell but internal to the community.
#   * A per-zone pool-conservation constraint makes sharing lossless and local:
#       sum_{er in zone} vEleShareOut == sum_{er in zone} vEleShareIn   (per p,sc,n)
#
# The benefit is automatic: a kWh shared internally avoids both the retail buy
# mark-up (for the receiver) and the low sell price (for the giver), so whenever
# the buy price exceeds the sell price the optimiser shares surplus instead of
# round-tripping it through the grid, lowering total community cost. The split of
# the savings between members (community pricing) is a settlement question handled
# in Phase 6b; for 6a the total-cost objective already captures the saving.

import time

from pyomo.environ import Var, Constraint, NonNegativeReals
from .utils.oM_Utils import log_time


def community_active(model) -> bool:
    """True if the energy-community layer is enabled for this case."""
    return bool(model.Par.get('pOptIndBinCommunity', 0))


def create_community_variables(model, optmodel, indlog):
    """Create the per-member share variables. No-op (and no vars) when the
    community layer is off, so existing cases are untouched. Must run before
    ``create_constraints`` because the retail balance references these variables.
    """
    if not community_active(model):
        return model
    StartTime = time.time()
    setattr(optmodel, 'vEleShareIn',  Var(optmodel.psner, within=NonNegativeReals,
                                          doc='community energy received by a member [kWh]'))
    setattr(optmodel, 'vEleShareOut', Var(optmodel.psner, within=NonNegativeReals,
                                          doc='community energy contributed by a member [kWh]'))
    log_time('--- Declaring the energy-community variables:', StartTime, ind_log=indlog)
    return model


def create_community_constraints(model, optmodel, indlog):
    """Per-zone pool conservation: contributed energy equals received energy within
    each community (zone), at every period/scenario/load level. Lossless, local
    virtual sharing. No-op when the community layer is off.
    """
    if not community_active(model):
        return model
    StartTime = time.time()

    # zone -> members (retailers), from the existing z2er mapping.
    members = {zn: [er for (z, er) in model.z2er if z == zn] for zn in model.zn}

    def ePool(optmodel, p, sc, n, zn):
        ers = members.get(zn, [])
        if len(ers) < 2:                       # a pool needs at least two members
            return Constraint.Skip
        return (sum(optmodel.vEleShareOut[p, sc, n, er] for er in ers)
                == sum(optmodel.vEleShareIn[p, sc, n, er] for er in ers))

    psnzn = [(p, sc, n, zn) for (p, sc, n) in model.psn for zn in model.zn]
    optmodel.__setattr__('eEleCommunityPool', Constraint(psnzn, rule=ePool,
                         doc='community pool conservation per zone [kWh]'))
    log_time('--- Declaring the energy-community constraints:', StartTime, ind_log=indlog)
    return model
