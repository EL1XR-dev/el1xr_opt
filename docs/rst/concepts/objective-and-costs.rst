Objective Function & Costs
==========================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo constraint ``eTotalTCost``, which minimizes the variable ``vTotalSCost``.

Total System Cost (``vTotalSCost``)
---------------------------------

The total system cost is the sum of all discounted costs across every period (`p`) and scenario (`sc`) in the model horizon. The objective function can be expressed conceptually as:

Objective Function [Cost-unit] («``eTotalMCost``»)
.. math::
   \min vTotalSCost

:math:`vTotalSCost «``eTotalMCost``»= \sum_{p \in P, sc \in SC} \text{DiscountFactor}_{p} \times \text{vTotalEleMCost}_{p,sc}`

Where:
- **OperationalCosts** include all costs related to running the system, such as fuel, maintenance, market purchases, and emissions.
- **DiscountFactor** brings future costs back to their present value, accounting for the time value of money.

Key Cost Components
-------------------

The total operational cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

1.  **Market Costs (`vTotalEleMCost`, `vTotalHydMCost`)**
    This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

    *   Cost components: ``vTotalEleTradeCost``, ``vTotalHydTradeCost``
    *   Revenue components: ``vTotalEleTradeProfit``, ``vTotalHydTradeProfit``

2.  **Generation Costs (`vTotalEleGCost`, `vTotalHydGCost`)**
    This is the operational cost of running the generation and production assets. It typically includes:
    *   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
    *   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
    *   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

3.  **Emission Costs (`vTotalECost`)**
    This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (`pParCO2Cost`).

4.  **Consumption Costs (`vTotalEleCCost`, `vTotalHydCCost`)**
    This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices.

5.  **Reliability Costs (`vTotalEleRCost`, `vTotalHydRCost`)**
    This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (`pParENSCost`), ensuring the model prioritizes meeting demand.
    *   Associated variables: ``vENS`` (Energy Not Supplied), ``vHNS`` (Hydrogen Not Supplied).

6.  **Peak Demand Costs (`vTotalElePeakCost`)**
    This component models capacity-based tariffs, where costs are determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs.

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.