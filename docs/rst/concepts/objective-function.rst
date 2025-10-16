.. _objective-function:

Objective Function
==================

The core purpose of the optimization model is to **minimize the total system cost** over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, market transaction costs, and penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo expression ``eTotalSCost``, which minimizes the variable ``vTotalSCost`` (:math:`\alpha`).

.. math::
   \min \alpha

-------------------

Total System Cost
-----------------

The total system cost is the sum of all discounted operational costs across every period (:math:`\periodindex`) and scenario (:math:`\scenarioindex`), plus the non-discounted peak demand costs. The objective function can be expressed as:

.. math::
   \alpha = \sum_{\periodindex \in \nP} \pdiscountrate_{\periodindex} \sum_{\scenarioindex \in \nS} \left( \text{OperationalCosts}_{\periodindex,\scenarioindex} \right) + \sum_{\periodindex \in \nP} \sum_{\scenarioindex \in \nS} \text{PeakDemandCosts}_{\periodindex,\scenarioindex}

where the total operational cost for a given period and scenario is the sum of market, generation, emission, consumption, and reliability costs for both electricity and hydrogen.

This is implemented in the Pyomo constraint ``eTotalTCost``:

.. math::
    \begin{aligned}
    \alpha = &\sum_{\substack{\periodindex \in \nP \\ \scenarioindex \in \nS}} \pdiscountrate_{\periodindex} \Big(
           \marketcost_{\periodindex,\scenarioindex}^{\text{elec}}
         + \marketcost_{\periodindex,\scenarioindex}^{\text{hyd}}
         + \generationcost_{\periodindex,\scenarioindex}^{\text{elec}}
         + \generationcost_{\periodindex,\scenarioindex}^{\text{hyd}} \\
         & \qquad + \emissioncost_{\periodindex,\scenarioindex}
         + \consumptioncost_{\periodindex,\scenarioindex}^{\text{elec}}
         + \consumptioncost_{\periodindex,\scenarioindex}^{\text{hyd}}
         + \reliabilitycost_{\periodindex,\scenarioindex}^{\text{elec}}
         + \reliabilitycost_{\periodindex,\scenarioindex}^{\text{hyd}}
    \Big) \\
    & + \sum_{\substack{\periodindex \in \nP \\ \scenarioindex \in \nS}} \peakdemandcost_{\periodindex,\scenarioindex}^{\text{elec}}
    \end{aligned}

The following sections detail each component of the total cost.

.. _market-costs:

Market-Based Costs and Revenues
-------------------------------

This section covers the costs and revenues from trading electricity and hydrogen in the market.

Electricity Market
~~~~~~~~~~~~~~~~~~
The net cost in the electricity market is the difference between the cost of purchasing electricity and the revenue from selling it. This is defined by the constraint ``eTotalEleMCost``.

*   **Electricity Purchase Costs (``eTotalEleTradeCost``)**: Cost incurred from buying electricity. This includes the energy price, taxes, and other fees.

    .. math::
       \text{TradeCost}_{\periodindex,\scenarioindex,\timeindex}^{\text{elec}} = \sum_{\traderindex \in \nRE} \left( (\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \cdot \pelemarketbuyingratio_{\traderindex} + \text{Fees}_{\traderindex}) \cdot (1 + \text{Tax}_{\traderindex}) \right) \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}

*   **Electricity Sales Revenues (``eTotalEleTradeProfit``)**: Revenue generated from selling electricity.

    .. math::
       \text{TradeProfit}_{\periodindex,\scenarioindex,\timeindex}^{\text{elec}} = \sum_{\traderindex \in \nRE} (\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \cdot \pelemarketsellingratio_{\traderindex} \cdot \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})

Hydrogen Market
~~~~~~~~~~~~~~~
Similarly, the net cost in the hydrogen market is the difference between purchase costs and sales revenues, defined by ``eTotalHydMCost``.

*   **Hydrogen Purchase Costs (``eTotalHydTradeCost``)**:

    .. math::
       \text{TradeCost}_{\periodindex,\scenarioindex,\timeindex}^{\text{hyd}} = \sum_{\traderindex \in \nRH} (\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \cdot \vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex})

*   **Hydrogen Sales Revenues (``eTotalHydTradeProfit``)**:

    .. math::
       \text{TradeProfit}_{\periodindex,\scenarioindex,\timeindex}^{\text{hyd}} = \sum_{\traderindex \in \nRH} (\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \cdot \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})

.. _operational-costs:

Operational Costs
-----------------

This section details the costs associated with running the system's assets.

Generation and Maintenance Costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These costs cover the operation of generation assets, including variable costs, no-load costs, and start-up/shut-down costs.

*   **Electricity Generation (``eTotalEleGCost``)**:

    .. math::
       \begin{aligned}
       \generationcost_{\periodindex,\scenarioindex,\timeindex}^{\text{elec}} = &\sum_{\genindex \in \nGE} (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
       & + \sum_{\genindex \in \nGENR} (\pfixedcost_{\genindex}\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex}\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex}\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex})
       \end{aligned}

*   **Hydrogen Production (``eTotalHydGCost``)**:

    .. math::
       \begin{aligned}
       \generationcost_{\periodindex,\scenarioindex,\timeindex}^{\text{hyd}} = \sum_{\genindex \in \nGH} \Big(& (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
       & + \pfixedcost_{\genindex}\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex}\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex}\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \Big)
       \end{aligned}

Consumption Costs
~~~~~~~~~~~~~~~~~
This represents the operational costs of energy-consuming assets, such as power used for charging storage devices.

*   **Electricity Consumption (``eTotalEleCCost``)**:

    .. math::
        \consumptioncost_{\periodindex,\scenarioindex,\timeindex}^{\text{elec}} = \sum_{\storageindex \in \nEE} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

*   **Hydrogen Consumption (``eTotalHydCCost``)**:

    .. math::
        \consumptioncost_{\periodindex,\scenarioindex,\timeindex}^{\text{hyd}} = \sum_{\storageindex \in \nEH} \pvariablecost_{\storageindex} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

.. _system-costs:

System-Level Costs
------------------

These costs are related to the overall stability and reliability of the system.

Peak Demand Costs
~~~~~~~~~~~~~~~~~
This cost, defined by ``eTotalElePeakCost``, penalizes high peaks in electricity demand from the grid. It is determined by the highest power peak registered during a billing period (e.g., a month) and is **not discounted**.

.. math::
    \peakdemandcost_{\periodindex,\scenarioindex}^{\text{elec}} = \frac{1}{|\nKE|} \sum_{\traderindex \in \nRE} \ppeakdemandtariff_{\traderindex} \sum_{\monthindex \in \nM} \sum_{\peakindex \in \nKE} \velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}

Emission Costs
~~~~~~~~~~~~~~
This component, defined by ``eTotalECost``, captures the cost of carbon emissions from fossil-fueled generators.

.. math::
    \emissioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\genindex \in \nGENR} \pcarbonprice_{\genindex} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}

Reliability Costs (Energy Not Served)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A penalty cost is applied to any energy demand that cannot be met, ensuring the model prioritizes meeting demand. This is calculated by multiplying the unserved energy by a high "value of lost load" price.

*   **Electricity Not Served (``eTotalEleRCost``)**:

    .. math::
        \reliabilitycost_{\periodindex,\scenarioindex,\timeindex}^{\text{elec}} = \sum_{\demandindex \in \nDE} \ploadsheddingcost_{\demandindex} \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

*   **Hydrogen Not Served (``eTotalHydRCost``)**:

    .. math::
        \reliabilitycost_{\periodindex,\scenarioindex,\timeindex}^{\text{hyd}} = \sum_{\demandindex \in \nDH} \ploadsheddingcost_{\demandindex} \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

.. _degradation-costs:

Future Development: Degradation Costs
-------------------------------------
The model is designed to be extensible. Future versions will incorporate degradation costs for assets like batteries and electrolyzers, which will be added as another component to the total system cost. This will allow for more detailed modeling of long-term asset lifetime and replacement strategies.