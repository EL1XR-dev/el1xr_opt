"""Heat sector — scaffold (not yet wired into the solve pipeline).

The model today covers electricity and hydrogen. This module marks out where a
third energy carrier, heat, will go, following the same pattern the electricity
and hydrogen sectors already use. It is deliberately a scaffold: the input
schema and the architecture already make room for heat, but the constraints
below are not built yet and the function is not called from oM_Sequence.

Planned scope (three settings, increasing in size):

  * Home / residential heat: a building-level heat demand met by a heat pump or
    boiler plus a thermal store. No heat network — heat is produced and used at
    the same node, like a behind-the-meter battery.
  * District heating: a heat network (pipes with losses) linking central
    production (large heat pumps, CHP, boilers) to demand nodes, mirroring the
    electricity and hydrogen network formulations.

Expected input tables (already listed in oM_InputSchema for forward
compatibility; verify the exact columns against a real heat case before use):

  * oM_Dict_HeatGeneration / HeatDemand / HeatRetail
  * oM_Data_HeatGeneration / HeatDemand / HeatRetail / HeatNetwork
  * oM_Data_VarMaxHeatDemand / VarMinHeatDemand

Intended sets, variables and constraints (by analogy with the existing sectors):

  * sets:        htg (heat generation), hts (thermal storage), htd (heat demand),
                 htr (heat retail), hta (heat network arcs)
  * variables:   vHeatTotalOutput, vHeatTotalCharge, vHeatInventory,
                 vHeatDemand, vHNS (heat not served), vHeatNetFlow
  * constraints: nodal heat balance, thermal-store inventory balance, heat-pump
                 coupling (electricity in -> heat out via COP), network flow
                 limits and losses for district heating.

When implemented, call create_heat_sector(...) from oM_Sequence.routine right
after create_green_hydrogen, and add the heat cost and revenue terms to the
objective components.
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


def create_heat_sector(model, optmodel, indlog='False'):
    """Build the nodal home-heat sector (demand, heat pump, boiler, thermal store).

    Home / behind-the-meter heat: heat is produced and used at the same node (no
    heat network yet). It mirrors the electricity and hydrogen sectors in nodal
    style. It builds only when the case carries heat sets, so calling it on an
    electricity/hydrogen-only model is a no-op (the four validation cases are
    unaffected). Wiring the CSV input pipeline to populate the heat sets is the
    remaining step (see the module docstring and oM_InputSchema heat stems); a case
    can also set the sets/params directly, which is how ``tests/test_heat_sector``
    exercises the formulation.

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
    htd = list(getattr(model, "htd", []) or [])
    htg = list(getattr(model, "htg", []) or [])
    if not htd and not htg:
        return model                                  # no heat case -> no-op
    StartTime = time.time()
    Par = model.Par
    htp = set(getattr(model, "htp", []) or [])        # heat pumps (electricity-driven)
    hts = list(getattr(model, "hts", []) or [])
    levels = list(model.n)

    def _at(node_map, nd):
        return [u for (n2, u) in getattr(model, node_map, []) if n2 == nd]

    setattr(optmodel, "vHeatOutput",
            Var(htg, levels, within=NonNegativeReals,
                bounds=lambda mm, g, n: (0, float(Par["pHeatGenMaxPower"][g]))))
    setattr(optmodel, "vHeatPumpElec", Var(list(htp), levels, within=NonNegativeReals))
    setattr(optmodel, "vHeatCharge", Var(hts, levels, within=NonNegativeReals,
            bounds=lambda mm, s, n: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatDischarge", Var(hts, levels, within=NonNegativeReals,
            bounds=lambda mm, s, n: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatInventory", Var(hts, levels, within=NonNegativeReals,
            bounds=lambda mm, s, n: (0, float(Par["pHeatStoMax"][s]))))
    setattr(optmodel, "vHeatNotServed", Var(htd, levels, within=NonNegativeReals))

    nodes = sorted({nd for (nd, _u) in getattr(model, "n2htd", [])}
                   | {nd for (nd, _u) in getattr(model, "n2htg", [])})

    def _balance(mm, nd, n):
        gens = _at("n2htg", nd)
        stos = _at("n2hts", nd)
        dems = _at("n2htd", nd)
        if not (gens or stos or dems):
            return Constraint.Skip
        # generation + store discharge - store charge + not-served == demand
        supply = (sum(mm.vHeatOutput[g, n] for g in gens)
                  + sum(mm.vHeatDischarge[s, n] - mm.vHeatCharge[s, n] for s in stos)
                  + sum(mm.vHeatNotServed[d, n] for d in dems))
        demand = sum(float(Par["pHeatDemand"][d][n]) for d in dems)
        return supply == demand
    optmodel.eHeatBalance = Constraint(nodes, levels, rule=_balance,
                                       doc="nodal home-heat balance")

    optmodel.eHeatPumpCOP = Constraint(
        list(htp), levels,
        rule=lambda mm, g, n: mm.vHeatOutput[g, n]
        == float(Par["pHeatPumpCOP"][g]) * mm.vHeatPumpElec[g, n],
        doc="heat pump: heat out = COP x electricity in")

    def _inv(mm, s, n):
        prev = (mm.vHeatInventory[s, model.n.prev(n)] if model.n.ord(n) > 1
                else float(Par["pHeatStoInitial"][s]))
        eff = float(Par["pHeatStoEff"][s])      # charging (round-trip) efficiency
        return mm.vHeatInventory[s, n] == prev + eff * mm.vHeatCharge[s, n] - mm.vHeatDischarge[s, n]
    optmodel.eHeatInventory = Constraint(hts, levels, rule=_inv,
                                         doc="thermal store inventory balance")

    optmodel.HeatOperatingCost = (
        sum(float(Par["pHeatNSCost"]) * optmodel.vHeatNotServed[d, n]
            for d in htd for n in levels)
        + sum(float(Par["pHeatGenCost"][g]) * optmodel.vHeatOutput[g, n]
              for g in htg for n in levels))

    log_time('-- Declaring the heat sector:', StartTime, ind_log=indlog)
    return model


def heat_electricity_load(optmodel, node_units, n):
    """Total electricity drawn by the heat pumps at a node in load level ``n``.

    ``node_units`` is the list of heat-pump units at the node. The electricity
    balance adds this as a load so the heat-pump COP coupling closes across sectors.
    Returns 0 when the model has no heat pumps (no heat case)."""
    v = getattr(optmodel, "vHeatPumpElec", None)
    if v is None or not node_units:
        return 0.0
    return sum(v[g, n] for g in node_units if (g, n) in v)
