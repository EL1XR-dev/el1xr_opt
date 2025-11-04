Objective Function
==================
The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

The main objective function is defined by the Pyomo constraint «``eTotalSCost``», which minimizes the variable «``vTotalSCost``» (:math:`\totalcost`).

Total System Cost
-----------------
The total system cost is the sum of all discounted costs minus revenues across every period (:math:`\periodindex`) and scenario (:math:`\scenarioindex`) in the model horizon. The objective function is defined by the constraint «``eTotalTCost``»:

.. math::
   \totalcost = \sum_{\periodindex \in \nP} \pdiscountfactor_{\periodindex} (\text{vTotalCComponent}_{\periodindex,\scenarioindex} - \text{vTotalRComponent}_{\periodindex,\scenarioindex})

where:

*   :math:`\totalcost` (``vTotalSCost``) is the total system cost.
*   :math:`\pdiscountfactor_{\periodindex}` is the discount factor for each period.
*   :math:`\text{vTotalCComponent}_{\periodindex,\scenarioindex}` represents the total cost component for a given period and scenario.
*   :math:`\text{vTotalRComponent}_{\periodindex,\scenarioindex}` represents the total revenue component for a given period and scenario.

The cost and revenue components are further broken down as follows:

**Cost Component Breakdown** (``eTotalCComponent``):

.. math::
   \begin{aligned}
   \text{vTotalCComponent}_{\periodindex,\scenarioindex} = & \underbrace{\elemarketcostgrid_{\periodindex,\scenarioindex}}_{\text{System-Level}} + \underbrace{\elemarketcosttax_{\periodindex,\scenarioindex}}_{\text{System-Level}} \\
   & + \sum_{\timeindex \in \nT} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \left( \underbrace{\elemarketcost_{\periodindex,\scenarioindex,\timeindex} + \hydmarketcost_{\periodindex,\scenarioindex,\timeindex}}_{\text{Market}} \right. \\
   & \left. + \underbrace{\elemaintopercost_{\periodindex,\scenarioindex,\timeindex} + \hydmaintopercost_{\periodindex,\scenarioindex,\timeindex}}_{\text{Operational}} \right. \\
   & \left. + \underbrace{\eledegradationcost_{\periodindex,\scenarioindex,\timeindex} + \hyddegradationcost_{\periodindex,\scenarioindex,\timeindex}}_{\text{Degradation}} \right)
   \end{aligned}

**Revenue Component Breakdown** (``eTotalRComponent``):

.. math::
   \begin{aligned}
   \text{vTotalRComponent}_{\periodindex,\scenarioindex} = & \underbrace{\elemarketrevenuetax_{\periodindex,\scenarioindex}}_{\text{System-Level}} \\
   & + \sum_{\timeindex \in \nT} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \left( \underbrace{\elemarketrevenue_{\periodindex,\scenarioindex,\timeindex} + \hydmarketrevenue_{\periodindex,\scenarioindex,\timeindex}}_{\text{Market}} \right)
   \end{aligned}

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs. The following sections provide a detailed explanation of each cost and revenue component.

Cost Components
---------------

System-Level Costs
~~~~~~~~~~~~~~~~~~
System-level costs are those that are not tied to a specific time step within the simulation but are calculated for each period and scenario.

**Electricity Network Cost** (``vTotalEleNCost``)

This component represents the costs associated with the electricity grid usage, including peak power costs, network usage fees, and capacity tariffs. It is defined by the constraint «``eNetGridUsageCost``»:

.. math::
   \elemarketcostgrid_{\periodindex,\scenarioindex} = \elepeakdemandcost_{\periodindex,\scenarioindex} + \elenetusecost_{\periodindex,\scenarioindex} + \elecaptariffcost_{\periodindex,\scenarioindex}

*   **Peak Power Cost** (``vTotalElePeakCost``): This cost is determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs. It is defined by «``eTotalElePeakCost``».

    .. math::
       \elepeakdemandcost_{\periodindex,\scenarioindex} = \frac{1}{|\nKE|} \sum_{\traderindex \in \nRE} \ppeakdemandtariff_{\traderindex} \pfactorone \left( \sum_{\monthindex \in \nM} \sum_{\peakindex \in \nKE} \velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex} \right) (1 + \pelemarketmoms_{\traderindex})

*   **Network Usage Cost** (``vTotalEleNetUseVarCost``): This cost captures the expenses associated with using the electricity distribution or transmission network, typically based on the amount of energy consumed. It is defined by «``eTotalEleNetUseCost``».

    .. math::
       \elenetusecost_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \left( \pelemarketnetfee_{\traderindex} \pfactorone \sum_{\timeindex \in \nT} \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \right) (1 + \pelemarketmoms_{\traderindex})

*   **Capacity Tariff Cost** (``vTotalEleNetUseFixCost``): This represents fixed charges based on the capacity of the connection to the electricity network. It is defined by «``eTotalEleNetUseFixCost``».

    .. math::
       \elecaptariffcost_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \pelemarkettariff_{\traderindex} \pfactorone \left( \sum_{\monthindex \in \nM} 1 \right) (1 + \pelemarketmoms_{\traderindex})

**Electricity Tax Cost** (``vTotalEleXCost``)

This component accounts for various taxes and surcharges associated with electricity market transactions. It is defined by the constraint «``eEleTaxCost``»:

.. math::
   \elemarketcosttax_{\periodindex,\scenarioindex} = \elemarketcostVAT_{\periodindex,\scenarioindex}

*   **Energy Tax Cost** (``vTotalEleEnergyTaxCost``): This is the cost of energy taxes on electricity purchases, defined by «``eEleTaxEnergyCost``».

    .. math::
       \elemarketcostVAT_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \left( \pelemarketmoms_{\traderindex} \pfactorone \sum_{\timeindex \in \nT} \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \right) (1 + \pelemarketmoms_{\traderindex})

Market Costs
~~~~~~~~~~~~
Market costs represent the expenses incurred from purchasing electricity and hydrogen from the respective markets.

**Electricity Market Cost** (``vTotalEleMCost``)

The total cost of electricity purchased from the market is defined by the constraint «``eEleMarketCost``»:

.. math::
   \elemarketcost_{\periodindex,\scenarioindex,\timeindex} = \elemarketcostDA_{\periodindex,\scenarioindex,\timeindex} + \elemarketcostPPA_{\periodindex,\scenarioindex,\timeindex}

*   **Day-Ahead Market Cost** (``vTotalEleMrkDACost``): The cost of electricity purchased from the day-ahead market, defined by «``eTotalEleTradeCost``».

    .. math::
       \elemarketcostDA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} (\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketbuyingratio_{\traderindex} + \pelemarketpassthrough_{\traderindex}) \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}

*   **PPA Market Cost** (``vTotalEleMrkPPACost``): The cost of electricity purchased through Power Purchase Agreements (PPAs).

**Hydrogen Market Cost** (``vTotalHydMCost``)

The total cost of hydrogen purchased from the market is defined by the constraint «``eHydMarketCost``»:

.. math::
   \hydmarketcost_{\periodindex,\scenarioindex,\timeindex} = \hydmarketcostPPA_{\periodindex,\scenarioindex,\timeindex}

*   **PPA Market Cost** (``vTotalHydMrkPPACost``): The cost of hydrogen purchased through PPAs, defined by «``eTotalHydTradeCost``».

    .. math::
       \hydmarketcostPPA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} \phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}

Operational Costs
~~~~~~~~~~~~~~~~~
Operational costs are the expenses associated with running the generation and production assets.

**Electricity Operation and Maintenance Cost** (``vTotalEleOCost``)

This component includes all operational costs for electricity assets, defined by «``eEleOpMaintCost``»:

.. math::
   \elemaintopercost_{\periodindex,\scenarioindex,\timeindex} = \elegenerationcost_{\periodindex,\scenarioindex,\timeindex} + \eleemissioncost_{\periodindex,\scenarioindex,\timeindex} + \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex} + \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex}

*   **Generation Cost** (``vTotalEleGCost``): The cost of electricity generation, including variable, no-load, start-up, and shut-down costs. Defined by «``eTotalEleGCost``».

    .. math::
       \begin{aligned}
       \elegenerationcost_{\periodindex,\scenarioindex,\timeindex} = & \sum_{\genindex \in \nGE} (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
       & + \sum_{\genindex \in \nGENR} (\pfixedcost_{\genindex} \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex} \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex} \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex})
       \end{aligned}

*   **Emission Cost** (``vTotalEleECost``): The cost of CO2 emissions from fossil-fueled generators, defined by «``eTotalECost``».

    .. math::
       \eleemissioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\genindex \in \nGENR} \pcarbonprice_{\genindex} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}

*   **Consumption Cost** (``vTotalEleCCost``): The cost of power used to charge energy storage devices, defined by «``eTotalEleCCost``».

    .. math::
       \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEE} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

*   **Reliability Cost** (``vTotalEleRCost``): A penalty for unserved electricity demand, defined by «``eTotalEleRCost``».

    .. math::
       \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\demandindex \in \nDE} \ploadsheddingcost_{\demandindex} \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

**Hydrogen Operation and Maintenance Cost** (``vTotalHydOCost``)

This component includes all operational costs for hydrogen assets, defined by «``eHydOpMaintCost``»:

.. math::
   \hydmaintopercost_{\periodindex,\scenarioindex,\timeindex} = \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex} + \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} + \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex}

*   **Generation Cost** (``vTotalHydGCost``): The cost of hydrogen production, defined by «``eTotalHydGCost``».

    .. math::
       \begin{aligned}
       \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex} = & \sum_{\genindex \in \nGH} (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
       & + \sum_{\genindex \in \nGH} (\pfixedcost_{\genindex} \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex} \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex} \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex})
       \end{aligned}

*   **Consumption Cost** (``vTotalHydCCost``): The cost of energy used for hydrogen storage, defined by «``eTotalHydCCost``».

    .. math::
       \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEH} \pvariablecost_{\storageindex} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

*   **Reliability Cost** (``vTotalHydRCost``): A penalty for unserved hydrogen demand, defined by «``eTotalHydRCost``».

    .. math::
       \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\demandindex \in \nDH} \ploadsheddingcost_{\demandindex} \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

Degradation Costs
~~~~~~~~~~~~~~~~~
This component is currently under development and will be used to model the degradation costs of assets over their lifetime.

**Electricity Degradation Cost** (``vTotalEleDCost``)

*Currently, this variable is fixed at zero.*

**Hydrogen Degradation Cost** (``vTotalHydDCost``)

*Currently, this variable is fixed at zero.*

Revenue Components
------------------

System-Level Revenues
~~~~~~~~~~~~~~~~~~~~~
System-level revenues are those that are not tied to a specific time step within the simulation but are calculated for each period and scenario.

**Electricity Tax Revenue** (``vTotalEleXRev``)

This component accounts for various incentives and tax benefits associated with electricity market transactions. It is defined by the constraint «``eEleTaxRevenue``»:

.. math::
   \elemarketrevenuetax_{\periodindex,\scenarioindex} = \elemarketrevenueincentive_{\periodindex,\scenarioindex}

*   **Incentive and Certificate Revenue** (``vTotalEleISRev``): This is the revenue from incentives and certificates on electricity sales, defined by «``eEleTaxISRevenue``».

    .. math::
       \elemarketrevenueincentive_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \pelemarketcertrevenue_{\traderindex} \pfactorone \sum_{\timeindex \in \nT} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}

Market Revenues
~~~~~~~~~~~~~~~
Market revenues represent the income generated from selling electricity and hydrogen to the respective markets.

**Electricity Market Revenue** (``vTotalEleMRev``)

The total revenue from electricity sold to the market is defined by the constraint «``eEleMarketRevenue``»:

.. math::
   \elemarketrevenue_{\periodindex,\scenarioindex,\timeindex} = \elemarketrevenueDA_{\periodindex,\scenarioindex,\timeindex} + \elemarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex} + \elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex}

*   **Day-Ahead Market Revenue** (``vTotalEleMrkDARev``): The revenue from electricity sold in the day-ahead market, defined by «``eEleMarketDayAheadRevenue``».

    .. math::
       \elemarketrevenueDA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} \pelesellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketsellingratio_{\traderindex} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}

*   **PPA Market Revenue** (``vTotalEleMrkPPARev``): The revenue from electricity sold through Power Purchase Agreements (PPAs).
*   **Frequency Market Revenue** (``vTotalEleMrkFrqRev``): The revenue from providing frequency regulation services to the grid, defined by «``eEleMarketFrequencyRevenue``».

    .. math::
       \elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex} = \sum_{\genindex \in \nG} (\pelefcrdupprice_{\periodindex,\scenarioindex,\timeindex} \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pelefcrddwprice_{\periodindex,\scenarioindex,\timeindex} \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex,\genindex})

**Hydrogen Market Revenue** (``vTotalHydMRev``)

The total revenue from hydrogen sold to the market is defined by the constraint «``eHydMarketRevenue``»:

.. math::
   \hydmarketrevenue_{\periodindex,\scenarioindex,\timeindex} = \hydmarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex}

*   **PPA Market Revenue** (``vTotalHydMrkPPARev``): The revenue from hydrogen sold through PPAs, defined by «``eHydMarketPPAsRevenue``».

    .. math::
       \hydmarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} \phydsellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}
