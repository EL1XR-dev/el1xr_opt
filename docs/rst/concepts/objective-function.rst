Objective Function
==================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo constraint «``eTotalSCost``», which minimizes the variable «``vTotalSCost``» (:math:`\alpha`).

Total System Cost
-----------------

The total system cost is the sum of all discounted costs across every period (:math:`\periodindex`) and scenario (:math:`\scenarioindex`) in the model horizon. The objective function can be expressed conceptually as:

Total system cost («``eTotalSCost``»)

.. math::
   \min \alpha

And the total cost is the sum of all operational costs, discounted to present value («``eTotalTCost``»):

.. math::
   \begin{aligned}
   \alpha
   = \sum_{\periodindex \in \nP} \pdiscountrate_{\periodindex}
      \sum_{\scenarioindex \in \nS} \elepeakdemandcost_{\periodindex,\scenarioindex} \sum_{\timeindex \in \nT}
      (&
        \elemarketcost_{\periodindex,\scenarioindex,\timeindex}
      + \hydmarketcost_{\periodindex,\scenarioindex,\timeindex}
      + \elegenerationcost_{\periodindex,\scenarioindex,\timeindex}
      + \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex}
      + \carboncost_{\periodindex,\scenarioindex,\timeindex} \\
      &\qquad
      + \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex}
      + \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex}
      + \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex}
      + \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex}
      )
   \end{aligned}

Key Cost Components
-------------------

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

Market Costs
~~~~~~~~~~~~
(«``eTotalEleMCost``», «``eTotalHydMCost``»)

This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

*   Cost components: :math:`\elemarketcostbuy`, :math:`\hydmarketcostbuy`
*   Revenue components: :math:`\elemarketcostsell`, :math:`\hydmarketcostsell`

#.  **Electricity Purchase**: The cost incurred from purchasing electricity from the market. This cost is defined by the constraint «``eTotalEleTradeCost``» and includes variable energy costs, taxes, and other fees.

    .. math::
       \elemarketcostbuy_{\periodindex,\scenarioindex,\timeindex} = \sum_{\eletraderindex \in \nRE} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} (&(\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex} \pelemarketbuyingratio_{\eletraderindex} + \pelemarketcertrevenue_{\eletraderindex} \pfactorone + \pelemarketpassthrough_{\eletraderindex} \pfactorone) \\
       & (1 + \pelemarketmoms_{\eletraderindex} \pfactorone) + \pelemarketnetfee_{\eletraderindex} \pfactorone) \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}

#.  **Electricity Sales**: The revenue generated from selling electricity to the market. This is defined by the constraint ``eTotalEleTradeProfit``.

    .. math::
       \elemarketcostsell_{\periodindex,\scenarioindex,\timeindex} = \sum_{\eletraderindex \in \nRE} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} (\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex} \pelemarketsellingratio_{\eletraderindex} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\eletraderindex})

#.  **Hydrogen Purchase**: The cost incurred from purchasing hydrogen from the market, as defined by ``eTotalHydTradeCost``.

    .. math::
       \hydmarketcostbuy_{\periodindex,\scenarioindex,\timeindex} = \sum_{\hydtraderindex \in \nRH} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} (\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} \vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex})

#.  **Hydrogen Sales**: The revenue generated from selling hydrogen to the market, as defined by ``eTotalHydTradeProfit``.

    .. math::
       \hydmarketcostsell_{\periodindex,\scenarioindex,\timeindex} = \sum_{\hydtraderindex \in \nRH} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} (\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex})

Generation Costs
~~~~~~~~~~~~~~~~
(``eTotalEleGCost``, ``eTotalHydGCost``)

This is the operational cost of running the generation and production assets. It typically includes:
*   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
*   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
*   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

The cost is defined by ``eTotalEleGCost`` for electricity and ``eTotalHydGCost`` for hydrogen.

Electricity Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. math::
   \begin{aligned}
   &\elegenerationcost_{\periodindex,\scenarioindex,\timeindex}
   = \sum_{\genindex \in \nGE}
      \ptimestepduration_{\periodindex,\scenarioindex,\timeindex}\,
      \Big(
           \pvariablecost_{\genindex}\,\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pmaintenancecost_{\genindex}\,\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
      \Big) \\
   &\quad
      + \sum_{\genindex \in \nGENR}
      \ptimestepduration_{\periodindex,\scenarioindex,\timeindex}\,
      \Big(
           \pfixedcost_{\genindex}\,\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pstartupcost_{\genindex}\,\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pshutdowncost_{\genindex}
      \Big)
   \end{aligned}

Hydrogen Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^

.. math::
   \begin{aligned}
   \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex}
   = \sum_{\genindex \in \nGH}
      \ptimestepduration_{\periodindex,\scenarioindex,\timeindex}\,
      \Big(&
           \pvariablecost_{\genindex}\,\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pmaintenancecost_{\genindex}\,\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}\\
   &\quad
         + \pfixedcost_{\genindex}\,\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pstartupcost_{\genindex}\,\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pshutdowncost_{\genindex}\,\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
      \Big)
   \end{aligned}

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