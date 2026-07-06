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


def _round(v):
    """Round a scalar so float noise does not split otherwise-identical units. NaN
    (unset numeric/categorical fields) maps to a single sentinel because NaN != NaN
    would otherwise split two units that are both 'unset' on the same field."""
    try:
        f = float(v)
        return "__nan__" if f != f else round(f, 9)
    except (TypeError, ValueError):
        return v


def _hashable(x, pd):
    """Reduce a per-unit parameter value (scalar / Series / DataFrame / array) to a
    hashable, rounded representation for comparing two units."""
    if isinstance(x, pd.DataFrame):
        return tuple(tuple(_round(v) for v in row) for row in x.values.tolist())
    if isinstance(x, pd.Series):
        return tuple(_round(v) for v in x.tolist())
    if hasattr(x, "tolist"):  # numpy array / scalar
        t = x.tolist()
        return tuple(_round(v) for v in t) if isinstance(t, list) else _round(t)
    if isinstance(x, (list, tuple)):
        return tuple(_round(v) for v in x)
    return _round(x)


def _extract_for_unit(v, g, pd):
    """Pull unit g's slice out of one parameter container (dict / Series / DataFrame),
    or None if the parameter does not carry a value for g."""
    try:
        if isinstance(v, dict):
            return _hashable(v[g], pd) if g in v else None
        if isinstance(v, pd.DataFrame):
            return _hashable(v[g], pd) if g in v.columns else None
        if isinstance(v, pd.Series):
            idx = v.index
            if isinstance(idx, pd.MultiIndex):
                if g in idx.get_level_values(-1):
                    return _hashable(v.xs(g, level=-1), pd)
                return None
            return _hashable(v.loc[g], pd) if g in idx else None
    except Exception:
        return None
    return None


# Computed merit-order warm-start states (not per-unit INPUT parameters): the model pre-commits
# generators in set order until initial demand is met, so two otherwise-identical units can get
# different initial output/UC purely by position. Excluded from the identity signature so identical
# candidates (e.g. two identical wind plants) are still detected and ordered.
_WARMSTART_PARAMS = frozenset({'pEleInitialOutput', 'pEleInitialUC', 'pHydInitialOutput', 'pHydInitialUC'})


def _unit_signature(Par, g, pd):
    """A unit's signature = every per-unit parameter value it carries, in name order.
    Two units with equal signatures are interchangeable (identical in every parameter
    the model reads), so ordering their build is valid symmetry-breaking. Computed
    warm-start states (see _WARMSTART_PARAMS) are excluded -- they are merit-order
    artifacts, not inputs, and identical units may differ there."""
    sig = []
    for name in sorted(Par):
        if name in _WARMSTART_PARAMS:
            continue
        val = _extract_for_unit(Par[name], g, pd)
        if val is not None:
            sig.append((name, val))
    return tuple(sig)


def _identical_groups(Par, candidates):
    """Partition candidate units into groups that are identical in ALL per-unit
    parameters. Singletons are dropped (nothing to order). Any unit whose signature
    cannot be built/hashed gets a unique key, so it is never grouped (fail-safe: a
    non-identical pair is never ordered)."""
    import pandas as pd
    sig = {}
    for i, g in enumerate(candidates):
        try:
            s = _unit_signature(Par, g, pd)
            hash(s)
            sig[g] = s
        except Exception:
            sig[g] = ("__nogroup__", i)
    groups = {}
    for g in candidates:
        groups.setdefault(sig[g], []).append(g)
    return [grp for grp in groups.values() if len(grp) > 1]


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
    # Audit C38: vTotalICost is added directly to the operating-cost components in eTotalSCost
    # (no unit conversion), so it must be in the same money unit. The model is currency-agnostic:
    # every objective term is in the input data's native currency (the demo data is SEK). All the
    # money doc-tags read [money] rather than a specific currency for this reason.
    setattr(optmodel, 'vTotalICost', Var(within=NonNegativeReals, doc='total annualized investment cost [money]'))

    if not len(model.egc) and not len(model.hgc) and not len(model.hgcompc):
        optmodel.vTotalICost.fix(0.0)
        log_time('--- Declaring the investment layer (no candidate units):', StartTime, ind_log=indlog)
        return model

    # %% Build-decision variables (fraction of nameplate built, in [0, 1])
    setattr(optmodel, 'vEleGenInvest', Var(model.egc, within=UnitInterval, doc='electricity candidate build fraction [0,1]'))
    setattr(optmodel, 'vHydGenInvest', Var(model.hgc, within=UnitInterval, doc='hydrogen    candidate build fraction [0,1]'))
    # Compressor build fraction (sized independently of the tank charge port it shares a store
    # with). Empty when no unit carries a CompressorInvestCost, so default cases are unchanged.
    setattr(optmodel, 'vHydCompInvest', Var(model.hgcompc, within=UnitInterval, doc='hydrogen compressor candidate build fraction [0,1]'))

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
    # Compressor build decision reuses the storage unit's binary-investment flag (Phase 1).
    for hgs in model.hgcompc:
        try:
            if model.Par['pHydGenBinaryInvestment'][hgs] == 1:
                optmodel.vHydCompInvest[hgs].domain = Binary
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

    # %% Symmetry-breaking across identical candidate units (opt-in, LP-preserving).
    # Interchangeable candidates -- e.g. two identical electrolyser modules AEL_01/AEL_02 --
    # create a permutation symmetry: any optimal build can be relabelled across the twins, so
    # the LP relaxation is degenerate and the barrier stalls (the root of the FCR-N-only case
    # defeating the barrier). Chaining the build fractions in a fixed order,
    # vInvest[u_i] >= vInvest[u_{i+1}], removes the symmetry WITHOUT changing the optimal
    # objective (identical units are exchangeable, so a sorted build is always attainable).
    # Gated by pOptIndBinSymmetryBreaking (default 0 -> no constraint, existing cases
    # byte-unchanged). Units are grouped only when ALL their per-unit parameters match, so a
    # non-identical pair is never ordered.
    if int(model.Par.get('pOptIndBinSymmetryBreaking', 0)) == 1:
        def _add_symmetry_order(var, candidates, tag):
            pairs = []
            for grp in _identical_groups(model.Par, candidates):
                ordered = sorted(grp)
                pairs.extend(zip(ordered, ordered[1:]))
            if not pairs:
                return
            optmodel.__setattr__(
                f'eSymmetry{tag}',
                Constraint(list(pairs), rule=lambda om, a, b: var[a] >= var[b],
                           doc=f'symmetry-breaking build order for identical {tag} candidates'))
            print(f'-- Symmetry-breaking: ordered {len(pairs)} identical {tag} candidate '
                  f'pair(s): {list(pairs)}')
        _add_symmetry_order(optmodel.vEleGenInvest,  list(model.egc),     'EleGen')
        _add_symmetry_order(optmodel.vHydGenInvest,  list(model.hgc),     'HydGen')
        _add_symmetry_order(optmodel.vHydCompInvest, list(model.hgcompc), 'HydComp')

    # %% Capacity coupling: an unbuilt candidate has zero usable capacity.
    # These are extra caps on top of the existing nameplate bounds, so they are
    # purely additive (no existing constraint is changed). With a build fraction
    # of 1 the existing nameplate bound binds; with 0 the unit is forced to zero.
    psnegc  = [(p, sc, n, egc ) for (p, sc, n) in model.psn for egc  in model.egc ]
    psnegsc = [(p, sc, n, egsc) for (p, sc, n) in model.psn for egsc in model.egsc]
    psnhgc  = [(p, sc, n, hgc ) for (p, sc, n) in model.psn for hgc  in model.hgc ]
    psnhgsc = [(p, sc, n, hgsc) for (p, sc, n) in model.psn for hgsc in model.hgsc]
    psnhgcompc = [(p, sc, n, hgs) for (p, sc, n) in model.psn for hgs in model.hgcompc]
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

    # Candidate hydrogen compressor: the charge flow into the store (whose compression draws
    # electricity, pHydGenMaxCompressorConsumption x vHydTotalCharge in the electricity balance)
    # is limited by the BUILT compressor throughput. This sits alongside the tank charge-port cap
    # above; the binding one wins, so a large tank can be paired with a small (cheaper, slower)
    # compressor or vice versa. The nameplate is a quantity, so it is multiplied by factor1 at use
    # (matching eHydInvestMaxInventory / the pHydMaxStorage scale-at-use pattern).
    def eHydInvestMaxCompressor(optmodel, p, sc, n, hgcompc):
        return optmodel.vHydTotalCharge[p, sc, n, hgcompc] <= model.Par['pHydGenCompressorNameplate'][hgcompc] * model.factor1 * optmodel.vHydCompInvest[hgcompc]
    optmodel.__setattr__('eHydInvestMaxCompressor', Constraint(psnhgcompc, rule=eHydInvestMaxCompressor, doc='candidate hydrogen compressor throughput limited by build decision'))

    # Compressor build tied to its tank build. A compressor raises the hydrogen to the
    # tank's storage pressure and injects it, so building a compressor only makes sense if
    # the tank it feeds is built. When that tank is ITSELF an investment candidate, the
    # compressor build fraction cannot exceed the tank build fraction (no compressor on a
    # tank that was not built). The coupling is only added when the tank is a candidate
    # (hgcompc unit also in hgc); a compressor sitting on an existing tank, or feeding a
    # standalone high-pressure demand, keeps its own free build decision -- there is no
    # blanket "no tank => no compressor" rule, since high-pressure delivery (tube-trailer,
    # refuelling, pipeline injection) can need compression without on-site storage.
    hgcompc_with_candidate_tank = [hgs for hgs in model.hgcompc if hgs in model.hgc]
    def eHydCompInvestLink(optmodel, hgs):
        return optmodel.vHydCompInvest[hgs] <= optmodel.vHydGenInvest[hgs]
    optmodel.__setattr__('eHydCompInvestLink', Constraint(hgcompc_with_candidate_tank, rule=eHydCompInvestLink, doc='compressor build cannot exceed the build of the candidate tank it feeds'))

    # %% Commitment coupling: a committable candidate can be on only if it is built.
    # The unit-commitment binary (and its start-up / shut-down) is otherwise free of the
    # build decision. The reserve-headroom rows for a committable unit are gated by the
    # commitment, not by the build fraction, so a partially built unit -- or, when its
    # minimum power is zero, an unbuilt-but-committed unit -- could hold operating reserve on
    # second-block capacity it never built (the same phantom-capacity leak fixed for storage
    # reserve, but on the generation side). Tie the commitment to the build fraction so an
    # unbuilt unit cannot commit and a fractionally built one commits at most its built share;
    # the start-up and shut-down transitions are bounded the same way for consistency in the
    # min-up/down and ramp rows. Only committable candidates are covered: electricity thermal
    # units (egt) and hydrogen scheduled units / electrolysers (hgt, e2h). Storage is excluded
    # -- it uses its own charge/discharge mode binaries, already bounded by the invested power
    # through the energy caps above. With a build fraction of 1 every bound is slack, so a
    # fully built or non-candidate unit is unchanged.
    ele_uc_cand = [g for g in model.egc if g in model.egt]
    hyd_uc_cand = [g for g in model.hgc if g in model.hgt or g in model.e2h]
    psn_ele_uc  = [(p, sc, n, g) for (p, sc, n) in model.psn for g in ele_uc_cand]
    psn_hyd_uc  = [(p, sc, n, g) for (p, sc, n) in model.psn for g in hyd_uc_cand]

    def eEleInvestCommitment(optmodel, p, sc, n, g):
        return optmodel.vEleGenCommitment[p, sc, n, g] <= optmodel.vEleGenInvest[g]
    optmodel.__setattr__('eEleInvestCommitment', Constraint(psn_ele_uc, rule=eEleInvestCommitment, doc='candidate electricity unit can commit only up to its build fraction'))

    def eEleInvestStartUp(optmodel, p, sc, n, g):
        return optmodel.vEleGenStartUp[p, sc, n, g] <= optmodel.vEleGenInvest[g]
    optmodel.__setattr__('eEleInvestStartUp', Constraint(psn_ele_uc, rule=eEleInvestStartUp, doc='candidate electricity unit can start up only up to its build fraction'))

    def eEleInvestShutDown(optmodel, p, sc, n, g):
        return optmodel.vEleGenShutDown[p, sc, n, g] <= optmodel.vEleGenInvest[g]
    optmodel.__setattr__('eEleInvestShutDown', Constraint(psn_ele_uc, rule=eEleInvestShutDown, doc='candidate electricity unit can shut down only up to its build fraction'))

    def eHydInvestCommitment(optmodel, p, sc, n, g):
        return optmodel.vHydGenCommitment[p, sc, n, g] <= optmodel.vHydGenInvest[g]
    optmodel.__setattr__('eHydInvestCommitment', Constraint(psn_hyd_uc, rule=eHydInvestCommitment, doc='candidate hydrogen unit can commit only up to its build fraction'))

    def eHydInvestStartUp(optmodel, p, sc, n, g):
        return optmodel.vHydGenStartUp[p, sc, n, g] <= optmodel.vHydGenInvest[g]
    optmodel.__setattr__('eHydInvestStartUp', Constraint(psn_hyd_uc, rule=eHydInvestStartUp, doc='candidate hydrogen unit can start up only up to its build fraction'))

    def eHydInvestShutDown(optmodel, p, sc, n, g):
        return optmodel.vHydGenShutDown[p, sc, n, g] <= optmodel.vHydGenInvest[g]
    optmodel.__setattr__('eHydInvestShutDown', Constraint(psn_hyd_uc, rule=eHydInvestShutDown, doc='candidate hydrogen unit can shut down only up to its build fraction'))

    # %% Grid-connection capacity investment (industrial VPP; opt-in via pParEleConnInvestCost>0).
    # An industrial VPP builds its own grid connection up to the point of common coupling
    # (transformer, switchgear, cable) -- real project capex the DSO does not bear. Size ONE
    # bidirectional connection capacity that must cover both the import (electrolyser load,
    # battery charge) and the export (wind, battery / fuel-cell discharge) at each retail node,
    # and pay its annualized per-kW capex. The effekttariff prices ongoing peak USE; this prices
    # the connection CAPEX and makes the connection size an endogenous trade-off with the asset
    # builds. Default off (parameter absent or 0), so cases without it are byte-unchanged. The
    # cost coefficient carries 1/factor1 (a 'Cost' Parameter) and multiplies the extensive
    # capacity, so the product is unit-invariant like the other operating-cost terms.
    conn_cost = float(model.Par.get('pParEleConnInvestCost', 0.0) or 0.0)
    optmodel._conn_active = conn_cost > 0.0
    if optmodel._conn_active:
        setattr(optmodel, 'vEleConnCap', Var(within=NonNegativeReals, doc='invested grid-connection capacity [kW, factor1-scaled like other powers]'))
        # Grid exchange physically occurs at the electricity reference (slack) node: the model couples
        # vEleImport/vEleExport to the retail buy/sell there and fixes them to zero at every other node.
        # So the connection must bound import/export at the reference node (not the retailer node -- the
        # two coincide only when the retailer sits on the reference node).
        conn_nodes = sorted(model.endrf) or sorted({model.Par['pEleRetNode'][er] for er in model.er})
        psn_conn = [(p, sc, n, nd) for (p, sc, n) in model.psn for nd in conn_nodes]

        def eEleConnImport(optmodel, p, sc, n, nd):
            return optmodel.vEleImport[p, sc, n, nd] <= optmodel.vEleConnCap
        optmodel.__setattr__('eEleConnImport', Constraint(psn_conn, rule=eEleConnImport, doc='grid import bounded by the invested connection capacity'))

        def eEleConnExport(optmodel, p, sc, n, nd):
            return optmodel.vEleExport[p, sc, n, nd] <= optmodel.vEleConnCap
        optmodel.__setattr__('eEleConnExport', Constraint(psn_conn, rule=eEleConnExport, doc='grid export bounded by the invested connection capacity'))

        # Reserve delivery/settlement option: the BASELINE day-ahead position must also fit the
        # invested connection (a position beyond deliverable capacity cannot be scheduled). This
        # is what stops a down-activation bid from being "delivered" by scheduling a baseline
        # export above the physical cap and absorbing own curtailed generation instead.
        if int(model.Par.get('pOptIndReserveDeliverySettlement', 0)) == 1:
            def eEleConnBuyBase(optmodel, p, sc, n, er):
                return optmodel.vEleBuyBase[p, sc, n, er] <= optmodel.vEleConnCap
            optmodel.__setattr__('eEleConnBuyBase', Constraint(model.psner, rule=eEleConnBuyBase, doc='baseline buy position bounded by the invested connection capacity'))

            def eEleConnSellBase(optmodel, p, sc, n, er):
                return optmodel.vEleSellBase[p, sc, n, er] <= optmodel.vEleConnCap
            optmodel.__setattr__('eEleConnSellBase', Constraint(model.psner, rule=eEleConnSellBase, doc='baseline sell position bounded by the invested connection capacity'))

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
    # Audit C38: the investment cost is a money LUMP SUM (annualized FixedInvestmentCost x a
    # dimensionless build fraction in [0,1]) -- it has no factor1-scaled quantity, so it is NOT
    # multiplied by factor1 (factor1 is now a true unit conversion: extensive quantities x
    # factor1, per-quantity prices / factor1, fixed/lump-sum/ratio terms unscaled, leaving the
    # optimum invariant; verified by test_factor1_invariant). The build/operate trade-off is
    # therefore consistent under any unit scale.
    #
    # Period weighting: operating costs enter the objective weighted by
    # pDiscountFactor[p] per period (eTotalTCost). The annualized investment cost
    # recurs in every modeled period, so it is weighted by the sum of the period
    # discount factors. This puts investment on the same discounted, period-weighted
    # footing as operation, matching the openTEPES treatment, so the build/operate
    # trade-off is consistent for any modeled horizon.
    period_weight = sum(model.Par['pDiscountFactor'][p] for p in model.p)

    def eTotalICost(optmodel):
        # Grid-connection capex (annualized, per invested kW of connection capacity); 0 when the
        # feature is off. Recurs each period like the asset capex, so it is period-weighted too.
        conn_term = (conn_cost * optmodel.vEleConnCap) if getattr(optmodel, '_conn_active', False) else 0.0
        return optmodel.vTotalICost == period_weight * (
            sum(model.Par['pEleGenInvestCost'][egc] * optmodel.vEleGenInvest[egc] for egc in model.egc) +
            sum(model.Par['pHydGenInvestCost'][hgc] * optmodel.vHydGenInvest[hgc] for hgc in model.hgc) +
            sum(model.Par['pHydGenCompressorInvestCost'][hgs] * optmodel.vHydCompInvest[hgs] for hgs in model.hgcompc) +
            conn_term)
    optmodel.__setattr__('eTotalICost', Constraint(rule=eTotalICost, doc='total period-weighted investment cost'))

    log_time('--- Declaring the investment (capacity-sizing) layer:', StartTime, ind_log=indlog)

    return model
