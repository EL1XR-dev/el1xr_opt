Objective Function & Costs
==========================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo constraint ``eTotalSCost``, which minimizes the variable ``vTotalSCost``.

Total System Cost (``vTotalSCost``)
---------------------------------

The total system cost is the sum of all discounted costs across every period (`p`) and scenario (`sc`) in the model horizon. The objective function can be expressed conceptually as:

Total system cost in [Cost-unit] («``eTotalSCost``»)

.. math::
   \min \text{vTotalSCost}

And the total cost is the sum of all operational costs, discounted to present value («``eTotalTCost``»):

:math:`\text{vTotalSCost} = \sum_{p \in P, sc \in SC} \text{DiscountFactor}_{p} \times`
:math:`\text{vTotalEleMCost}_{p,sc} + \text{vTotalHydMCost}_{p,sc} +`
:math:`\text{vTotalEleGCost}_{p,sc} + \text{vTotalHydGCost}_{p,sc} +`
:math:`\text{vTotalECost}_{p,sc} +`
:math:`\text{vTotalEleCCost}_{p,sc} + \text{vTotalHydCCost}_{p,sc} +`
:math:`\text{vTotalEleRCost}_{p,sc} + \text{vTotalHydRCost}_{p,sc} +`
:math:`\text{vTotalElePeakCost}_{p,sc}`

Where:

- **DiscountFactor** is defined as :math:`\frac{1}{(1 + r)^{(t_p / 8760)}}`, where :math:`r` is the annual discount rate (``pParDiscountRate``) and :math:`t_p` is the time in hours from the start of the horizon to the start of period :math:`p`. It is used to convert future costs into present value, accounting for the time value of money.
- **vTotalEleMCost**, **vTotalHydMCost** are the total market costs for electricity and hydrogen, respectively.
- **vTotalEleGCost**, **vTotalHydGCost** are the total generation costs for electricity and hydrogen, respectively.
- **vTotalECost** is the total emission cost.
- **vTotalEleCCost**, **vTotalHydCCost** are the total consumption costs for electricity and hydrogen, respectively.
- **vTotalEleRCost**, **vTotalHydRCost** are the total reliability costs for electricity and hydrogen, respectively.
- **vTotalElePeakCost** is the total power peak cost for electricity.

Key Cost Components
-------------------

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

#.  **Market Costs** (``vTotalEleMCost``, ``vTotalHydMCost``)
    This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

    *   Cost components: ``vTotalEleTradeCost``, ``vTotalHydTradeCost``
    *   Revenue components: ``vTotalEleTradeProfit``, ``vTotalHydTradeProfit``

    #.  **Electricity Purchase** (``vTotalEleTradeCost``): The cost incurred from purchasing electricity from the market.

        :math:`\text{vTotalEleTradeCost} = \sum_{t \in T, n \in N_{EleTrade}}`
        :math:`\text{pEleTradeCost}_{t,n} \times \text{vEleTrade}_{t,n}`

    #.  **Electricity Sales** (``vTotalEleTradeProfit``): The revenue generated from selling electricity to the market.

        :math:`\text{vTotalEleTradeProfit} = \sum_{t \in T, n \in N_{EleTrade}}`
        :math:`\text{pEleTradeProfit}_{t,n} \times \text{vEleTrade}_{t,n}`

    #.  **Hydrogen Purchase (`vTotalHydTradeCost`)**: The cost incurred from purchasing hydrogen from the market.
    #.  **Hydrogen Sales (`vTotalHydTradeProfit`)**: The revenue generated from selling hydrogen to the market.

#.  **Generation Costs (`vTotalEleGCost`, `vTotalHydGCost`)**
    This is the operational cost of running the generation and production assets. It typically includes:
    *   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
    *   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
    *   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

#.  **Emission Costs (`vTotalECost`)**
    This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (`pParCO2Cost`).

#.  **Consumption Costs (`vTotalEleCCost`, `vTotalHydCCost`)**
    This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices.

#.  **Reliability Costs (`vTotalEleRCost`, `vTotalHydRCost`)**
    This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (`pParENSCost`), ensuring the model prioritizes meeting demand.
    *   Associated variables: ``vENS`` (Energy Not Supplied), ``vHNS`` (Hydrogen Not Supplied).

#.  **Peak Demand Costs (`vTotalElePeakCost`)**
    This component models capacity-based tariffs, where costs are determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs.

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.