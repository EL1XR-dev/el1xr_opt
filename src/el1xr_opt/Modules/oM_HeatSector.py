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


def create_heat_sector(model, optmodel, indlog):
    """Build the heat-sector sets, variables and constraints.

    Scaffold only: not implemented yet, and not called from the solve pipeline.
    Returns the model unchanged so wiring it in early is a no-op until the
    formulation lands. See the module docstring for the planned scope and the
    heat stems declared in oM_InputSchema (HEAT_DICT_STEMS, HEAT_DATA_STEMS).
    """
    _ = (HEAT_DICT_STEMS, HEAT_DATA_STEMS)  # referenced so the scope stays visible
    return model
