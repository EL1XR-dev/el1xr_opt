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
   :label: eq:TotalTCost

   \alpha = \sum_{\periodindex \in \nP} \pdiscountrate_{\periodindex} \sum_{\scenarioindex \in \nS} (C_{\periodindex,\scenarioindex} - R_{\periodindex,\scenarioindex})

where:

* :math:`C_{\periodindex,\scenarioindex}` is the total cost component for a given period and scenario, as defined in :eq:`eq:TotalCComponent`.
* :math:`R_{\periodindex,\scenarioindex}` is the total revenue component for a given period and scenario, as defined in :eq:`eq:TotalRComponent`.

.. math::
   :label: eq:TotalCComponent
   :nowrap:

   \begin{align*}
   C_{p,s} = & \underbrace{C^{grid,e}_{p,s}}_{\text{Network usage}} + \underbrace{C^{tax,e}_{p,s}}_{\text{Surcharges/taxes}} \\
   & + \sum_{n \in \mathcal{T}} \delta_{p,s,n} \left( \underbrace{C^{trade,e}_{p,s,n} + C^{trade,h}_{p,s,n}}_{\text{Market purchases}} + \underbrace{C^{O\&M,e}_{p,s,n} + C^{O\&M,h}_{p,s,n}}_{\text{Generation/consumption}} \right) \\
   & + \underbrace{\sum_{d \in \mathcal{D}} \left( C^{deg,e}_{p,s,d} + C^{deg,h}_{p,s,d} \right)}_{\text{Degradation}}
   \end{align*}

.. math::
   :label: eq:TotalRComponent
   :nowrap:

   \begin{align*}
   R_{p,s} = \underbrace{R^{tax,e}_{p,s}}_{\text{Incentives}} + \sum_{n \in \mathcal{T}} \delta_{p,s,n} \left( \underbrace{R^{trade,e}_{p,s,n} + R^{trade,h}_{p,s,n}}_{\text{Market Sales}} \right)
   \end{align*}

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

Electricity Grid Usage
----------------------
This component models capacity-based and tariffs, and considers the power peak penalization cost.

.. math::
   :label: eq:EleNetGridUsageCost

   C^{grid,e}_{\periodindex,\scenarioindex} = C^{peak,e}_{\periodindex,\scenarioindex} + C^{netuse,e}_{\periodindex,\scenarioindex} + C^{cap,e}_{\periodindex,\scenarioindex}

Peak Power Cost
~~~~~~~~~~~~~~~~
This cost subcomponent is determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs.

The formulation is defined by «``eTotalElePeakCost``».

.. math::
    :label: eq:TotalElePeakCost

    \elepeakdemandcost_{\periodindex,\scenarioindex} = \frac{1}{|\nKE|} \sum_{\traderindex \in \nRE} \ppeakdemandtariff_{\traderindex} \pfactorone \sum_{\monthindex \in \nM} \sum_{\peakindex \in \nKE} \velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex} (1 + \pelemarketmoms_{\traderindex})

Network Usage Cost
~~~~~~~~~~~~~~~~~~
This cost subcomponent captures the expenses associated with using the electricity distribution or transmission network. It is typically based on the amount of energy consumed or injected into the grid over a billing period.
The formulation is defined by «``eTotalEleNetUseCost``».

.. math::
   :label: eq:TotalEleNetUseCost

   \elenetusecost_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \pelemarketnetfee_{\traderindex} \pfactorone \sum_{\timeindex \in \nT} \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} (1 + \pelemarketmoms_{\traderindex})

Capacity Tariff Cost
~~~~~~~~~~~~~~~~~~~~
This cost subcomponent represents fixed charges based on the capacity of the connection to the electricity network. It is usually a monthly fee that depends on the contracted capacity.
The formulation is defined by «``eTotalEleCapTariffCost``».

.. math::
   :label: eq:TotalEleCapTariffCost

   \elecaptariffcost_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \pelemarkettariff_{\traderindex} \pfactorone |\nM| (1 + \pelemarketmoms_{\traderindex})

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.

Market
------
This represents the costs and revenues in the electricity and hydrogen markets.

Electricity Market Costs
~~~~~~~~~~~~~~~~~~~~~~~~
The formulation is defined by «``eEleMarketCost``».

.. math::
   :label: eq:EleMarketCost

   \elemarketcost_{\periodindex,\scenarioindex,\timeindex} = \elemarketcostDA_{\periodindex,\scenarioindex,\timeindex} + \elemarketcostPPA_{\periodindex,\scenarioindex,\timeindex}

*   **Electricity Purchase**: The cost incurred from purchasing electricity from the market. This cost is defined by the constraint «``eTotalEleTradeCost``» and includes variable energy costs, taxes, and other fees.

.. math::
   :label: eq:TotalEleTradeCost

   \elemarketcostDA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} (\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketbuyingratio_{\traderindex} + \pelemarketpassthrough_{\traderindex}) \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} (1 + \pelemarketmoms_{\traderindex})

Electricity Market Revenues
~~~~~~~~~~~~~~~~~~~~~~~~~~~
The formulation is defined by «``eEleMarketRevenue``».

.. math::
   :label: eq:EleMarketRevenue

   \elemarketrevenue_{\periodindex,\scenarioindex,\timeindex} = \elemarketrevenueDA_{\periodindex,\scenarioindex,\timeindex} + \elemarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex} + \elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex}

*   **Electricity Sales**: The revenue generated from selling electricity to the market. This is defined by the constraint ``eEleMarketDayAheadRevenue``.

.. math::
   :label: eq:EleMarketDayAheadRevenue

   \elemarketrevenueDA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} \pelesellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketsellingratio_{\traderindex} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex} (1 + \pelemarketmoms_{\traderindex})

Hydrogen Market Costs
~~~~~~~~~~~~~~~~~~~~~
The formulation is defined by «``eHydMarketCost``».

.. math::
   :label: eq:HydMarketCost

   \hydmarketcost_{\periodindex,\scenarioindex,\timeindex} = \hydmarketcostPPA_{\periodindex,\scenarioindex,\timeindex}

*   **Hydrogen Purchase**: The cost incurred from purchasing hydrogen from the market, as defined by «``eTotalHydTradeCost``».

.. math::
   :label: eq:TotalHydTradeCost

   \hydmarketcostPPA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} \phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}

Hydrogen Market Revenues
~~~~~~~~~~~~~~~~~~~~~~~~~~
The formulation is defined by «``eHydMarketRevenue``».

.. math::
   :label: eq:HydMarketRevenue

   \hydmarketrevenue_{\periodindex,\scenarioindex,\timeindex} = \hydmarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex}

*   **Hydrogen Sales**: The revenue generated from selling hydrogen to the market, as defined by ``eHydMarketDayAheadRevenue``.

.. math::
   :label: eq:HydMarketDayAheadRevenue

   \hydmarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} \phydsellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}

Electricity Grid Services
-------------------------
This component captures revenues from providing ancillary services to the electricity grid, such as frequency regulation, spinning reserves, and voltage support.
The total revenue from ancillary services (:math:`\elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex}`) is defined by the constraint «``eEleMarketFrequencyRevenue``».

.. math::
   :label: eq:EleMarketFrequencyRevenue

   \elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex} = \freqcontdisturbrevenue_{\periodindex,\scenarioindex,\timeindex}

Frequency Containment Reserve for Disturbance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This revenue subcomponent is earned by providing frequency containment reserves to manage disturbances in the grid, as defined by ``eEleMarketFCRDRevenue``.

.. math::
    :label: eq:EleMarketFCRDRevenue

    \freqcontdisturbrevenue_{\periodindex,\scenarioindex,\timeindex} = \sum_{g \in \elecgen} \left( (\pelemarketpriceDUP_{\periodindex,\scenarioindex,\timeindex} \pfactorone \cdot \pelemarketdispatchDU_{\periodindex,\scenarioindex,\timeindex,g} + \pelemarketpriceDDW_{\periodindex,\scenarioindex,\timeindex} \pfactorone \cdot \pelemarketdispatchDW_{\periodindex,\scenarioindex,\timeindex,g}) \cdot (1 + \pelemarketmoms_{\retailerofgen(g)}) \right)

where :math:`Retailer(g)` is the retailer associated with generator :math:`g`.

Taxes and Pass-Throughs
-----------------------
This component accounts for various taxes, surcharges, pass-through costs and incentives associated with electricity market transactions. These can include:

Tax Costs
~~~~~~~~~
The formulation is defined by «``eEleTaxCost``».

.. math::
   :label: eq:EleTaxCost

   C^{tax,e}_{p,s} = \sum_{r \in \mathcal{R}^{e}} \left( \peleretenergytax_{r} F1 (1 + M^{moms,e}_{r}) \sum_{n \in \mathcal{T}} mb^{e}_{p,s,n,r} \right)

Incentives and Certificate Revenues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The formulation is defined by «``eEleTaxISRevenue``».

.. math::
   :label: eq:EleTaxISRevenue

   \elemarketrevenuetax_{\periodindex,\scenarioindex} = \sum_{\traderindex \in \nRE} \pelemarketcertrevenue_{\traderindex} \pfactorone \sum_{\timeindex \in \nT} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}

Operation and Maintenance
-------------------------
This is the operational cost of running the generation and production assets. It typically includes:

*   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
*   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
*   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

The cost is defined by ``eEleOpMaintCost`` for electricity and ``eHydOpMaintCost`` for hydrogen.

.. math::
   :label: eq:EleOpMaintCost

   \elemaintopercost_{\periodindex,\scenarioindex,\timeindex} = \elegenerationcost_{\periodindex,\scenarioindex,\timeindex} + \carboncost_{\periodindex,\scenarioindex,\timeindex} + \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex} + \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex}

.. math::
   :label: eq:HydOpMaintCost

   \hydmaintopercost_{\periodindex,\scenarioindex,\timeindex} = \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex} + \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} + \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex}

Generation
~~~~~~~~~~

Electricity Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleGCost``».

.. math::
   :label: eq:TotalEleGCost
   :nowrap:

   \begin{align}
   \elegenerationcost_{\periodindex,\scenarioindex,\timeindex} = &\sum_{\genindex \in \nGE} (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &+ \sum_{\genindex \in \nGENR} (\pfixedcost_{\genindex} \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex} \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex} \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex})
   \end{align}

Hydrogen Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydGCost``».

.. math::
   :label: eq:TotalHydGCost
   :nowrap:

   \begin{align}
   \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex} = &\sum_{\genindex \in \nGH} (\pvariablecost_{\genindex} + \pmaintenancecost_{\genindex}) \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &+ \sum_{\genindex \in \nGH} (\pfixedcost_{\genindex} \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pstartupcost_{\genindex} \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} + \pshutdowncost_{\genindex} \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex})
   \end{align}

Emission Costs
~~~~~~~~~~~~~~
This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (:math:`\pcarbonprice_{\genindex}`).
The formulation is defined by «``eTotalECost``».


.. math::
   :label: eq:TotalECost

   \carboncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\genindex \in \nGENR} \pcarbonprice_{\genindex} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}

Consumption
~~~~~~~~~~~
This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices.

Electricity Consumption Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleCCost``».

.. math::
   :label: eq:TotalEleCCost

   \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEE} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

Hydrogen Consumption Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydCCost``».

.. math::
   :label: eq:TotalHydCCost

   \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEH} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

Reliability
~~~~~~~~~~~
This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (:math:`\ploadsheddingcost_{\demandindex}`), ensuring the model prioritizes meeting demand.
*   Associated variables: :math:`\veleloadshed` (Electricity Not Served), :math:`\vhydloadshed` (Hydrogen Not Served).

Electricity Energy-not-served Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleRCost``».

.. math::
   :label: eq:TotalEleRCost

   \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\demandindex \in \nDE} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \ploadsheddingcost_{\demandindex} \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

Hydrogen Energy-not-served Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydRCost``».

.. math::
   :label: eq:TotalHydRCost

   \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\demandindex \in \nDH} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \ploadsheddingcost_{\demandindex} \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}

Degradation
-----------
This component models the degradation cost of electricity storage units, which is a function of the depth of discharge (DoD).

.. math::
   :label: eq:TotalEleDCost

   C^{deg,e}_{\periodindex,\scenarioindex,\dayindex} = \sum_{\storageindex \in \nEE} \sum_{i \in \mathcal{I}^{DoD}} C_{i,\storageindex} \cdot DoD_{i,\storageindex}

Here:

- :math:`\mathcal{I}^{DoD}` is the set of predefined depth-of-discharge (DoD) intervals (e.g., shallow, medium, deep discharge), over which the index :math:`i` ranges. The definition of these intervals is provided in the model data or parameter section.
- :math:`C_{i,\storageindex}` is the degradation cost coefficient for storage unit :math:`\storageindex` and DoD interval :math:`i`. This coefficient represents the cost impact per unit of energy discharged within the :math:`i`-th DoD range.
- :math:`DoD_{i,\storageindex}` is the amount of energy discharged from storage unit :math:`\storageindex` in the :math:`i`-th DoD range during the period, scenario, and day considered.
.. math::
   :label: eq:TotalHydDCost

   C^{deg,h}_{\periodindex,\scenarioindex,\dayindex} = 0

   .. note::

      Hydrogen storage degradation costs are set to zero in this model. This is an intentional simplification, as hydrogen storage degradation is either negligible, not supported by the current implementation, or may be considered in future model extensions.
