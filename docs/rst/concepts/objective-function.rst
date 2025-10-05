Objective Function
==================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo constraint ``eTotalSCost``, which minimizes the variable ``vTotalSCost`` (:math:`\alpha`).

The symbos used in the objective function are written in **uppercase** letters as follows:

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_Modelformulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\elemarketcost_{p,sc}`                  Net cost of electricity market transactions (buying - selling)       €         «``vTotalEleMCost``»
:math:`\elemarketcostbuy_{p,sc}`               Cost of electricity market purchases                                 €         «``vTotalEleTradeCost``»
:math:`\elemarketcostsell_{p,sc}`              Revenue from electricity market sales                                €         «``vTotalEleTradeProfit``»
:math:`\hydmarketcost_{p,sc}`                  Net cost of hydrogen market transactions (buying - selling)          €         «``vTotalHydMCost``»
:math:`\hydmarketcostbuy_{p,sc}`               Cost of hydrogen market purchases                                    €         «``vTotalHydTradeCost``»
:math:`\hydmarketcostsell_{p,sc}`              Revenue from hydrogen market sales                                   €         «``vTotalHydTradeProfit``»
:math:`\elegenerationcost_{p,sc}`              Total cost of electricity generation                                 €         «``vTotalEleGCost``»
:math:`\hydgenerationcost_{p,sc}`              Total cost of hydrogen generation                                    €         «``vTotalHydGCost``»
:math:`\carboncost_{p,sc}`                     Total cost of CO2 emissions                                          €         «``vTotalECost``»
:math:`\eleconsumptioncost_{p,sc}`             Total cost of electricity consumption (e.g., storage charging)       €         «``vTotalEleCCost``»
:math:`\hydconsumptioncost_{p,sc}`             Total cost of hydrogen consumption (e.g., storage charging)          €         «``vTotalHydCCost``»
:math:`\eleunservedenergycost_{p,sc}`          Total cost of unserved electricity demand (penalty)                  €         «``vTotalEleRCost``»
:math:`\hydunservedenergycost_{p,sc}`          Total cost of unserved hydrogen demand (penalty)                     €         «``vTotalHydRCost``»
:math:`\elepeakdemandcost_{p,sc}`              Total cost of electricity peak demand (capacity tariff)              €         «``vTotalElePeakCost``»
:math:`\alpha`                                 Total system cost (objective function)                               €         «``vTotalSCost``»
=============================================  ===================================================================  ========  ===========================================================================

Total System Cost
-----------------

The total system cost is the sum of all discounted costs across every period (:math:`\periodindex`) and scenario (:math:`\scenarioindex`) in the model horizon. The objective function can be expressed conceptually as:

Total system cost («``eTotalSCost``»)

.. math::
   \min \alpha

And the total cost is the sum of all operational costs, discounted to present value («``eTotalTCost``»):

.. math::
   \alpha = \sum_{\periodindex \in \nP, \scenarioindex \in \nC} \pdiscountrate_{\periodindex} (\elemarketcost_{p,sc} + \hydmarketcost_{p,sc} + &\elegenerationcost_{p,sc} + \hydgenerationcost_{p,sc} + \carboncost_{p,sc} + \\
            & \eleconsumptioncost_{p,sc} + \hydconsumptioncost_{p,sc} + \eleunservedenergycost_{p,sc} + \hydunservedenergycost_{p,sc} + \elepeakdemandcost_{p,sc})

Key Cost Components
-------------------

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

Market Costs
~~~~~~~~~~~~
(``eTotalEleMCost``, ``eTotalHydMCost``)

This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

*   Cost components: :math:`\elemarketcostbuy`, :math:`\hydmarketcostbuy`
*   Revenue components: :math:`\elemarketcostsell`, :math:`\hydmarketcostsell`

#.  **Electricity Purchase**: The cost incurred from purchasing electricity from the market. This cost is defined by the constraint ``eTotalEleTradeCost`` and includes variable energy costs, taxes, and other fees.

    .. math::
       \elemarketcostbuy_{p,sc,n} = \sum_{\eletraderindex \in nRE} \ptimestepduration_{p,sc,n} (&(\pelebuyprice_{p,sc,n,er} \pelemarketbuyingratio_{er} + \pelemarketcertrevenue_{er} \pfactorone + \pelemarketpassthrough_{er} \pfactorone) \\
       & (1 + \pelemarketmoms_{er} \pfactorone) + \pelemarketnetfee_{er} \pfactorone) \velemarketbuy_{p,sc,n,er}

#.  **Electricity Sales** (``vTotalEleTradeProfit``): The revenue generated from selling electricity to the market. This is defined by the constraint ``eTotalEleTradeProfit``.

    .. math::
       \elemarketcostsell_{p,sc,n} = \sum_{\eletraderindex \in nRE} \ptimestepduration_{p,sc,n} (\pelesellprice_{p,sc,n,er} \pelemarketsellingratio_{er} \velemarketsell_{p,sc,n,er})

#.  **Hydrogen Purchase** (``vTotalHydTradeCost``): The cost incurred from purchasing hydrogen from the market, as defined by ``eTotalHydTradeCost``.

    .. math::
       \text{vTotalHydTradeCost}_{p,sc,n} = \sum_{hr \in HR} \text{pDuration}_{p,sc,n} \times (\text{pVarEnergyCost}_{hr,p,sc,n} \times \text{vHydBuy}_{p,sc,n,hr})

#.  **Hydrogen Sales** (``vTotalHydTradeProfit``): The revenue generated from selling hydrogen to the market, as defined by ``eTotalHydTradeProfit``.

    .. math::
       \text{vTotalHydTradeProfit}_{p,sc,n} = \sum_{hr \in HR} \text{pDuration}_{p,sc,n} \times (\text{pVarEnergyPrice}_{hr,p,sc,n} \times \text{vHydSell}_{p,sc,n,hr})

Generation Costs
~~~~~~~~~~~~~~~~
(`vTotalEleGCost`, `vTotalHydGCost`)

    This is the operational cost of running the generation and production assets. It typically includes:
    *   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
    *   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
    *   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

    The cost is defined by ``eTotalEleGCost`` for electricity and ``eTotalHydGCost`` for hydrogen.

    .. math::
       \text{vTotalEleGCost}_{p,sc,n} = \sum_{eg \in EG} \text{pDuration}_{p,sc,n} \times (
       & \text{pEleGenLinearVarCost}_{eg} \times \text{vEleTotalOutput}_{p,sc,n,eg} + \\
       & \text{pEleGenOMVariableCost}_{eg} \times \text{vEleTotalOutput}_{p,sc,n,eg}) + \\
       & \sum_{egt \in EGT} \text{pDuration}_{p,sc,n} \times (
       \text{pEleGenConstantVarCost}_{egt} \times \text{vEleGenCommitment}_{p,sc,n,egt} + \\
       & \text{pEleGenStartUpCost}_{egt} \times \text{vEleGenStartUp}_{p,sc,n,egt} + \\
       & \text{pEleGenShutDownCost}_{egt} \times \text{vEleGenShutDown}_{p,sc,n,egt})

    .. math::
       \text{vTotalHydGCost}_{p,sc,n} = \sum_{hg \in HG} \text{pDuration}_{p,sc,n} \times (
       & \text{pHydGenLinearVarCost}_{hg} \times \text{vHydTotalOutput}_{p,sc,n,hg} - \\
       & \text{pHydGenOMVariableCost}_{hg} \times \text{vHydTotalOutput}_{p,sc,n,hg}) + \\
       & \sum_{hgt \in HGT} \text{pDuration}_{p,sc,n} \times (
       \text{pHydGenConstantVarCost}_{hgt} \times \text{vHydGenCommitment}_{p,sc,n,hgt} + \\
       & \text{pHydGenStartUpCost}_{hgt} \times \text{vHydGenStartUp}_{p,sc,n,hgt} + \\
       & \text{pHydGenShutDownCost}_{hgt} \times \text{vHydGenShutDown}_{p,sc,n,hgt})

Emission Costs
~~~~~~~~~~~~~~
(`vTotalECost`)

    This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (``pGenCO2EmissionCost``). The formulation is defined by ``eTotalECost``.

    .. math::
       \text{vTotalECost}_{p,sc,n} = \sum_{egt \in EGT} \text{pDuration}_{p,sc,n} \times \text{pGenCO2EmissionCost}_{egt} \times \text{vEleTotalOutput}_{p,sc,n,egt}

Consumption Costs
~~~~~~~~~~~~~~~~~
(`vTotalEleCCost`, `vTotalHydCCost`)

    This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices. These are defined by ``eTotalEleCCost`` and ``eTotalHydCCost``.

    .. math::
       \text{vTotalEleCCost}_{p,sc,n} = \sum_{egs \in EGS} \text{pDuration}_{p,sc,n} \times \text{pEleGenLinearTerm}_{egs} \times \text{vEleTotalCharge}_{p,sc,n,egs}

    .. math::
       \text{vTotalHydCCost}_{p,sc,n} = \sum_{hgs \in HGS} \text{pDuration}_{p,sc,n} \times \text{pHydGenLinearTerm}_{hgs} \times \text{vHydTotalCharge}_{p,sc,n,hgs}

Reliability Costs
~~~~~~~~~~~~~~~~~
(`vTotalEleRCost`, `vTotalHydRCost`)

    This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (``pParENSCost`` or ``pParHNSCost``), ensuring the model prioritizes meeting demand. The associated constraints are ``eTotalEleRCost`` and ``eTotalHydRCost``.
    *   Associated variables: ``vENS`` (Energy Not Supplied), ``vHNS`` (Hydrogen Not Supplied).

    .. math::
       \text{vTotalEleRCost}_{p,sc,n} = \sum_{ed \in ED} \text{pDuration}_{p,sc,n} \times \text{pParENSCost} \times \text{vENS}_{p,sc,n,ed}

    .. math::
       \text{vTotalHydRCost}_{p,sc,n} = \sum_{hd \in HD} \text{pDuration}_{p,sc,n} \times \text{pParHNSCost} \times \text{vHNS}_{p,sc,n,hd}

Electricity Peak Demand Costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(`vTotalElePeakCost`)

    This component models capacity-based tariffs, where costs are determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs. The formulation is defined by ``eTotalElePeakCost``.

    .. math::
       \text{vTotalElePeakCost}_{p,sc} = \frac{1}{|\text{Peaks}|} \sum_{er \in ER} \text{pEleRetTariff}_{er} \times \text{factor1} \times \sum_{m \in \text{moy}} \sum_{\text{peak} \in \text{Peaks}} \text{vElePeak}_{p,sc,m,er,\text{peak}}

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.