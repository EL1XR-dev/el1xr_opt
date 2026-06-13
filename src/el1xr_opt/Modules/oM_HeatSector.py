"""Heat sector -- a third energy carrier alongside electricity and hydrogen.

``create_heat_sector`` is wired into ``oM_Sequence.build_model`` (after the
green-hydrogen step) and builds a behind-the-meter heat sector when the case
carries heat data; it is a no-op otherwise, so electricity/hydrogen-only cases
are unchanged.

Scope today -- **home / residential heat**: a building-level, nodal heat demand
met by a heat pump or boiler plus a thermal store, produced and used at the same
node (no heat network yet -- district heating with pipe flows and losses is the
planned next setting). The power-heat loop is open with a heat pump alone and
closed by adding a heat-to-power unit.

Input tables (read by ``load_heat_data``):

  * oM_Dict_HeatGeneration / oM_Data_HeatGeneration (with a ``Type`` column --
    HeatPump / Boiler / Heat2Ele / Storage)
  * oM_Data_HeatDemand / oM_Data_VarMaxHeatDemand

Sets, variables and constraints:

  * sets:        htg (heat generation), htp (heat pumps), htw (heat-to-power),
                 hts (thermal storage), htd (heat demand)
  * variables:   vHeatOutput, vHeatPumpElec, vHeatCharge / vHeatDischarge /
                 vHeatInventory, vHeatConsumed, vHeatToEle, vHeatNotServed
  * constraints: nodal heat balance (eHeatBalance), heat-pump coupling
                 (eHeatPumpCOP), heat-to-power (eHeatToEle), thermal-store
                 inventory (eHeatInventory).

The heat-pump electricity draw and the heat-to-power injection are folded into
the electricity balance, and the heat operating cost (period-discounted,
duration-weighted) into the objective.
"""
from __future__ import annotations

from .oM_InputSchema import HEAT_DATA_STEMS, HEAT_DICT_STEMS


def heat_tables_present(source) -> bool:
    """True if the opened input source carries any heat data table.

    Lets the pipeline detect a heat-bearing case once the formulation exists.
    """
    try:
        stems = set(source.list_data_stems())
    except Exception:
        return False
    return any(stem in stems for stem in HEAT_DATA_STEMS)


def load_heat_data(model, dir_name, case_name):
    """Read the heat input tables and populate the heat sets and parameters on the
    model. No-op (returns False) when the case carries no heat tables, so the four
    validation cases are unaffected. The minimal schema:

      * oM_Data_HeatGeneration -- index = unit; columns Node, Type
        (HeatPump | Boiler | Heat2Ele | Storage), MaximumPower, Cost, COP,
        Efficiency, MaxStorage, StoEff, InitialStorage.
      * oM_Data_HeatDemand -- index = demand unit; column Node.
      * oM_Data_VarMaxHeatDemand -- (period, scenario, load level) index; one
        column per heat-demand unit, the heat demand at that step.

    Heat-not-served cost is taken from the Parameter table (pParHeatNSCost) or a
    high default.
    """
    from .oM_InputSource import resolve_source
    src = resolve_source(dir_name, case_name)
    try:
        if not heat_tables_present(src):
            return False
        gen = src.read_data("HeatGeneration")
        dem = src.read_data("HeatDemand")
        vmd = src.read_data("VarMaxHeatDemand")
    finally:
        src.close()

    Par = model.Par
    for key in ("pHeatGenMaxPower", "pHeatGenCost", "pHeatPumpCOP", "pHeatToEleMaxHeat",
                "pHeatToEleEff", "pHeatStoMax", "pHeatStoEff", "pHeatStoInitial", "pHeatDemand"):
        Par.setdefault(key, {})
    htg, htp, htw, hts = [], [], [], []
    n2htg, n2hts, n2htw = [], [], []
    for u, row in gen.iterrows():
        typ = str(row["Type"]).strip().lower()
        node = str(row["Node"])
        if typ in ("heatpump", "boiler"):
            htg.append(u)
            n2htg.append((node, u))
            Par["pHeatGenMaxPower"][u] = float(row["MaximumPower"])
            Par["pHeatGenCost"][u] = float(row.get("Cost", 0.0) or 0.0)
            if typ == "heatpump":
                htp.append(u)
                Par["pHeatPumpCOP"][u] = float(row["COP"])
        elif typ in ("heat2ele", "orc", "chp"):
            htw.append(u)
            n2htw.append((node, u))
            Par["pHeatToEleMaxHeat"][u] = float(row["MaximumPower"])
            Par["pHeatToEleEff"][u] = float(row["Efficiency"])
        elif typ in ("storage", "store", "thermalstore"):
            hts.append(u)
            n2hts.append((node, u))
            Par["pHeatStoMax"][u] = float(row["MaxStorage"])
            Par["pHeatStoEff"][u] = float(row.get("StoEff", 1.0) or 1.0)
            Par["pHeatStoInitial"][u] = float(row.get("InitialStorage", 0.0) or 0.0)
    htd, n2htd = [], []
    for d, row in dem.iterrows():
        htd.append(d)
        n2htd.append((str(row["Node"]), d))
        Par["pHeatDemand"][d] = {idx: float(vmd.loc[idx, d])
                                 for idx in vmd.index if d in vmd.columns}
    Par.setdefault("pHeatNSCost", float(Par.get("pParHeatNSCost", 1000.0)))

    model.htd, model.htg, model.htp, model.htw, model.hts = htd, htg, htp, htw, hts
    model.n2htd, model.n2htg, model.n2hts, model.n2htw = n2htd, n2htg, n2hts, n2htw
    return True


def create_heat_sector(model, optmodel, indlog='False', dir_name=None, case_name=None):
    """Build the nodal home-heat sector (demand, heat pump, boiler, thermal store).

    Home / behind-the-meter heat: heat is produced and used at the same node (no
    heat network yet). It mirrors the electricity and hydrogen sectors in nodal
    style. It builds only when the case carries heat sets, so calling it on an
    electricity/hydrogen-only model is a no-op (the four validation cases are
    unaffected). When ``dir_name`` / ``case_name`` are given it reads the case's heat
    tables via :func:`load_heat_data` (the CSV pipeline, used by ``oM_Sequence``); a
    case can also set the sets/params directly, which is how ``tests/test_heat_sector``
    exercises the formulation. Coupling into the electricity balance (heat-pump load,
    heat-to-power output) and the objective (heat operating cost) is done by the
    callers, so this runs before ``create_constraints`` in the build.

    Expected on ``model`` when a heat case is present:
      * sets   ``htd`` (heat demands), ``htg`` (heat generators), ``htp`` (the heat
               pumps, a subset of ``htg`` driven by electricity), ``hts`` (thermal
               stores), ``n`` (load levels), and the node maps ``n2htd`` / ``n2htg``
               / ``n2hts`` giving the (node, unit) membership.
      * params in ``model.Par``: ``pHeatDemand[htd][n]``, ``pHeatGenMaxPower[htg]``,
               ``pHeatGenCost[htg]`` (per heat unit, e.g. boiler fuel),
               ``pHeatPumpCOP[htp]``, ``pHeatStoMax[hts]``, ``pHeatStoEff[hts]``,
               ``pHeatStoInitial[hts]``, ``pHeatNSCost``, ``pDuration[n]``.

    It creates, on ``optmodel``: ``vHeatOutput`` (per generator), ``vHeatPumpElec``
    (electricity drawn by each heat pump -- the cross-sector coupling), ``vHeatCharge``
    / ``vHeatInventory`` (thermal store), ``vHeatNotServed``; and the constraints
    ``eHeatBalance`` (nodal), ``eHeatPumpCOP`` (heat = COP x electricity),
    ``eHeatInventory`` (store dynamics). The heat operating cost (heat-not-served
    plus generator running cost) is exposed as ``optmodel.HeatOperatingCost`` so the
    caller can add it to the objective; the heat-pump electricity load at a node is
    available from :func:`heat_electricity_load` for the electricity balance.
    """
    import time
    from pyomo.environ import Var, Constraint, NonNegativeReals
    from .utils.oM_Utils import log_time

    _ = (HEAT_DICT_STEMS, HEAT_DATA_STEMS)
    # read the heat tables from the case when a path is given (the CSV pipeline);
    # tests set the heat sets directly and pass no path.
    if dir_name is not None and case_name is not None and not getattr(model, "htd", None):
        load_heat_data(model, dir_name, case_name)
    htd = list(getattr(model, "htd", []) or [])
    htg = list(getattr(model, "htg", []) or [])
    if not htd and not htg:
        return model                                  # no heat case -> no-op
    StartTime = time.time()
    Par = model.Par
    htp = list(getattr(model, "htp", []) or [])        # heat pumps (electricity-driven)
    htw = list(getattr(model, "htw", []) or [])        # heat-to-power units (ORC/CHP)
    hts = list(getattr(model, "hts", []) or [])
    levels = list(model.n)

    # Audit C40: a power -> heat-pump (COP) -> heat -> heat-to-power (efficiency) -> power
    # loop produces net electricity whenever COP x efficiency >= 1. A heat pump's COP is
    # normally > 1 (it moves free ambient heat the model does not account for), so the loop
    # can be a perpetual-motion source that makes the LP unbounded. Warn when the data allows
    # it (a store in the loop only adds StoEff <= 1, so COP x efficiency is the worst case).
    if htp and htw:
        max_cop = max((float(Par["pHeatPumpCOP"][g]) for g in htp), default=0.0)
        max_eff = max((float(Par["pHeatToEleEff"][w]) for w in htw), default=0.0)
        if max_cop * max_eff >= 1.0:
            print(f"WARNING (C40): a power-heat-power loop is representable (max COP {max_cop} x "
                  f"max heat-to-power efficiency {max_eff} = {max_cop * max_eff:.3f} >= 1); the "
                  f"model may be unbounded. Ensure COP x efficiency < 1 or that the loop cannot close.")
    # all time-varying quantities are indexed by (period, scenario, load level),
    # like the electricity and hydrogen sectors. psn is the model's (p, sc, n) list.
    psn = list(getattr(model, "psn", None)
               or [(p, sc, n) for (p, sc) in getattr(model, "ps", []) for n in levels])

    def _idx(units):
        return [(p, sc, n, u) for (p, sc, n) in psn for u in units]

    def _at(node_map, nd):
        return [u for (n2, u) in getattr(model, node_map, []) if n2 == nd]

    # period discount factor and load-level duration (default 1.0 when unset, as in the
    # standalone tests). Used by both the inventory balance and the operating cost so a
    # representative load level that stands in for several hours is treated consistently.
    disc = Par.get("pDiscountFactor", {})
    dur = Par.get("pDuration", {})

    def _d(p):
        try:
            return float(disc[p])
        except (KeyError, TypeError):
            return 1.0

    def _dur(p, sc, n):
        try:
            return float(dur[p, sc, n])
        except (KeyError, TypeError):
            return 1.0

    setattr(optmodel, "vHeatOutput", Var(_idx(htg), within=NonNegativeReals,
            bounds=lambda mm, p, sc, n, g: (0, float(Par["pHeatGenMaxPower"][g]))))
    setattr(optmodel, "vHeatPumpElec", Var(_idx(htp), within=NonNegativeReals))
    # Audit C40 (documented limitation): charge/discharge are bounded by the store's ENERGY
    # capacity (pHeatStoMax) used as a power rating -- there is no separate charge/discharge
    # power-rating parameter in the heat schema, and there is no binary mutual-exclusivity
    # forcing charge XOR discharge. Simultaneous charge+discharge is never beneficial under
    # StoEff < 1 (it only loses energy), so it does not occur at the optimum; a dedicated
    # power-rating parameter and a mutual-exclusivity binary are the follow-up (schema/MIP).
    setattr(optmodel, "vHeatCharge", Var(_idx(hts), within=NonNegativeReals,
            bounds=lambda mm, p, sc, n, s: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatDischarge", Var(_idx(hts), within=NonNegativeReals,
            bounds=lambda mm, p, sc, n, s: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatInventory", Var(_idx(hts), within=NonNegativeReals,
            bounds=lambda mm, p, sc, n, s: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatNotServed", Var(_idx(htd), within=NonNegativeReals))
    # heat-to-power (the analogue of the hydrogen fuel cell): consumes heat, makes
    # electricity. Present only when the case has htw units; it is what closes the
    # power<->heat loop (heat pump = power->heat, this = heat->power).
    setattr(optmodel, "vHeatConsumed", Var(_idx(htw), within=NonNegativeReals,
            bounds=lambda mm, p, sc, n, w: (0, float(Par["pHeatToEleMaxHeat"][w]))))
    setattr(optmodel, "vHeatToEle", Var(_idx(htw), within=NonNegativeReals))

    # Audit C40: include thermal-store nodes (n2hts) in the balance node list. A node with
    # only a store (no demand/generation/heat-to-power) was previously omitted, so its store
    # charge/discharge entered no balance and was free.
    nodes = sorted({nd for (nd, _u) in getattr(model, "n2htd", [])}
                   | {nd for (nd, _u) in getattr(model, "n2htg", [])}
                   | {nd for (nd, _u) in getattr(model, "n2htw", [])}
                   | {nd for (nd, _u) in getattr(model, "n2hts", [])})
    bal_idx = [(p, sc, n, nd) for (p, sc, n) in psn for nd in nodes]

    def _balance(mm, p, sc, n, nd):
        gens = _at("n2htg", nd)
        stos = _at("n2hts", nd)
        dems = _at("n2htd", nd)
        h2ps = _at("n2htw", nd)
        if not (gens or stos or dems or h2ps):
            return Constraint.Skip
        # generation + store discharge - store charge + not-served
        #   == fixed demand + heat-to-power consumption
        supply = (sum(mm.vHeatOutput[p, sc, n, g] for g in gens)
                  + sum(mm.vHeatDischarge[p, sc, n, s] - mm.vHeatCharge[p, sc, n, s] for s in stos)
                  + sum(mm.vHeatNotServed[p, sc, n, d] for d in dems))
        demand = (sum(float(Par["pHeatDemand"][d][(p, sc, n)]) for d in dems)
                  + sum(mm.vHeatConsumed[p, sc, n, w] for w in h2ps))
        return supply == demand
    optmodel.eHeatBalance = Constraint(bal_idx, rule=_balance, doc="nodal home-heat balance")

    optmodel.eHeatToEle = Constraint(
        _idx(htw),
        rule=lambda mm, p, sc, n, w: mm.vHeatToEle[p, sc, n, w]
        == float(Par["pHeatToEleEff"][w]) * mm.vHeatConsumed[p, sc, n, w],
        doc="heat-to-power: electricity out = efficiency x heat in")

    optmodel.eHeatPumpCOP = Constraint(
        _idx(htp),
        rule=lambda mm, p, sc, n, g: mm.vHeatOutput[p, sc, n, g]
        == float(Par["pHeatPumpCOP"][g]) * mm.vHeatPumpElec[p, sc, n, g],
        doc="heat pump: heat out = COP x electricity in")

    def _inv(mm, p, sc, n, s):
        prev = (mm.vHeatInventory[p, sc, model.n.prev(n), s] if model.n.ord(n) > 1
                else float(Par["pHeatStoInitial"][s]))
        eff = float(Par["pHeatStoEff"][s])      # charging (round-trip) efficiency
        # the charge/discharge are powers, so weight them by the load-level duration to
        # accumulate energy -- matching the electricity/hydrogen inventory balances and
        # the (duration-weighted) heat operating cost. (eHeatBalance stays a power
        # balance, with no duration, like eEleBalance.)
        return (mm.vHeatInventory[p, sc, n, s]
                == prev + _dur(p, sc, n) * (eff * mm.vHeatCharge[p, sc, n, s]
                                            - mm.vHeatDischarge[p, sc, n, s]))
    optmodel.eHeatInventory = Constraint(_idx(hts), rule=_inv,
                                         doc="thermal store inventory balance")

    # Audit C40: cap heat-not-served by the demand it stands for, so it cannot exceed the
    # demand and act as a free paid sink (mirrors the hydrogen eHydNotServedCap, C41).
    def _ns_cap(mm, p, sc, n, d):
        return mm.vHeatNotServed[p, sc, n, d] <= float(Par["pHeatDemand"][d].get((p, sc, n), 0.0))
    optmodel.eHeatNotServedCap = Constraint(_idx(htd), rule=_ns_cap,
                                            doc="heat not-served bounded by demand (C40)")

    # Audit C40: terminal condition for the thermal store. The rolling balance starts from
    # pHeatStoInitial and leaves the final inventory free, so the initial stock is a free
    # energy supply the horizon can drain. Require the final inventory to be at least the
    # initial stock, so the starting energy is not consumed for free (the electricity store
    # gets the analogous tie via its cycle-time-step inventory; the heat store had none).
    def _inv_terminal(mm, p, sc, s):
        return mm.vHeatInventory[p, sc, model.n.last(), s] >= float(Par["pHeatStoInitial"][s])
    optmodel.eHeatInventoryTerminal = Constraint(
        [(p, sc, s) for (p, sc) in getattr(model, "ps", []) for s in hts],
        rule=_inv_terminal, doc="thermal store terminal condition: final inventory >= initial (C40)")

    # heat operating cost (heat-not-served + generator running cost), discounted by
    # period and weighted by the load-level duration like the electricity and hydrogen
    # operating costs (the "psn" cost kind), so a representative load level standing in
    # for several hours is costed for all of them (using the _d / _dur helpers defined
    # above). The heat-pump electricity is already costed on the electricity side, so it
    # is not counted again here.
    optmodel.HeatOperatingCost = (
        sum(_d(p) * _dur(p, sc, n) * float(Par["pHeatNSCost"]) * optmodel.vHeatNotServed[p, sc, n, d]
            for (p, sc, n) in psn for d in htd)
        + sum(_d(p) * _dur(p, sc, n) * float(Par["pHeatGenCost"][g]) * optmodel.vHeatOutput[p, sc, n, g]
              for (p, sc, n) in psn for g in htg))

    log_time('-- Declaring the heat sector:', StartTime, ind_log=indlog)
    return model


def heat_electricity_load(optmodel, node_units, p, sc, n):
    """Total electricity drawn by the heat pumps at a node in (period, scenario,
    load level). ``node_units`` is the list of heat-pump units at the node. The
    electricity balance adds this as a load so the heat-pump COP coupling closes
    across sectors. Returns 0 when the model has no heat pumps (no heat case)."""
    v = getattr(optmodel, "vHeatPumpElec", None)
    if v is None or not node_units:
        return 0.0
    return sum(v[p, sc, n, g] for g in node_units if (p, sc, n, g) in v)


def heat_to_power_output(optmodel, node_units, p, sc, n):
    """Electricity produced by the heat-to-power units at a node in (period,
    scenario, load level) -- the analogue of the hydrogen fuel cell's electricity
    output. The electricity balance adds this as generation, closing the
    power<->heat loop. Returns 0 when the model has no heat-to-power units."""
    v = getattr(optmodel, "vHeatToEle", None)
    if v is None or not node_units:
        return 0.0
    return sum(v[p, sc, n, g] for g in node_units if (p, sc, n, g) in v)
