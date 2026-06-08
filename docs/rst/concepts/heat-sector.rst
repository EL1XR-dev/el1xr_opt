Heat sector
===========

el1xr_opt models a behind-the-meter heat sector alongside electricity and hydrogen.
It is built by ``oM_HeatSector.create_heat_sector`` and is a no-op for cases that
carry no heat data, so electricity/hydrogen-only cases are unchanged.

Scope
-----

The heat sector is **nodal** (one heat balance per node) and behind-the-meter -- there
is no heat network with pipe flows or losses yet (that is the next setting). A node's
heat is supplied by:

- a **heat pump** (``htp``): electricity to heat, ``heat = COP x electricity``. This is
  the cross-sector coupling -- the heat-pump electricity draw is a load on the
  electricity balance.
- a **boiler** (a heat generator that burns fuel),
- a **thermal store** (``hts``): shifts heat in time, with a charge/discharge
  efficiency and an inventory balance,
- **heat-to-power** (``htw``, an ORC / CHP turbine): heat back to electricity. Adding
  it closes the power-heat loop (heat pump alone is power-to-heat only).
- **heat-not-served** (``vHeatNotServed``): an expensive slack so the balance is always
  feasible, priced at ``pHeatNSCost``.

Sets
----

``htd`` heat demands, ``htg`` heat generators (heat pumps and boilers), ``htp`` heat
pumps (a subset of ``htg``), ``htw`` heat-to-power units, ``hts`` thermal stores, with
the node maps ``n2htd`` / ``n2htg`` / ``n2hts`` / ``n2htw``.

Variables
---------

``vHeatOutput`` (generator heat output), ``vHeatPumpElec`` (heat-pump electricity
draw), ``vHeatCharge`` / ``vHeatDischarge`` / ``vHeatInventory`` (thermal store),
``vHeatConsumed`` and ``vHeatToEle`` (heat-to-power), and ``vHeatNotServed``.

Constraints
-----------

- ``eHeatBalance`` -- nodal heat balance: generation + store discharge + heat-pump
  output meet the heat demand (minus heat-not-served).
- ``eHeatPumpCOP`` -- ``vHeatOutput = COP x vHeatPumpElec`` for heat pumps.
- ``eHeatToEle`` -- ``vHeatToEle = efficiency x vHeatConsumed`` for heat-to-power.
- ``eHeatInventory`` -- thermal-store inventory dynamics.

The electricity balance ``eEleBalance`` is coupled to the heat sector: it subtracts the
heat-pump electricity load and adds the heat-to-power injection at each node.

Cost
----

The heat operating cost (heat-not-served penalty plus generator running cost) is added
to the objective, discounted by period and weighted by the load-level duration like the
electricity and hydrogen operating costs. The heat-pump electricity is already priced on
the electricity side, so it is not charged again here.

Loop topology
-------------

- **Power to heat** is an open loop by default (heat pump / boiler; heat is a terminal
  demand). Adding a heat-to-power unit (``htw``) closes the power-heat loop.
- **Hydrogen** is already closed-loop when a case includes both the electrolyser
  (``e2h``) and the fuel cell (``h2e``).

Which loops are active is selected by the conversion units a case includes.

Input tables
------------

A heat-bearing case adds ``oM_Data_HeatGeneration`` (with a ``Type`` column --
HeatPump / Boiler / Heat2Ele / Storage), ``oM_Data_HeatDemand`` and
``oM_Data_VarMaxHeatDemand``. See :doc:`../user-guide/data-and-io`.
