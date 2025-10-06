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

:math:`\alpha = \sum_{\periodindex \in \nP} \pdiscountrate_{\periodindex}
\sum_{\scenarioindex \in \nS} \elepeakdemandcost_{\periodindex,\scenarioindex}
\!+\! \sum_{\timeindex \in \nT} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex}
( \elemarketcost_{\periodindex,\scenarioindex,\timeindex}
\!+\! \hydmarketcost_{\periodindex,\scenarioindex,\timeindex}
\!+\! \elegenerationcost_{\periodindex,\scenarioindex,\timeindex}`

:math:`\!+\! \carboncost_{\periodindex,\scenarioindex,\timeindex}
\!+\! \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex}
\!+\! \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} \\
\!+\! \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex}
\!+\! \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex} )`

Key Cost Components
-------------------
The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

Market Costs
~~~~~~~~~~~~
This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

*   Cost components: :math:`\elemarketcostbuy`, :math:`\hydmarketcostbuy`
*   Revenue components: :math:`\elemarketcostsell`, :math:`\hydmarketcostsell`

Electricity Market Costs
^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleMCost``».

:math:`\elemarketcost_{\periodindex,\scenarioindex,\timeindex} = \elemarketcostbuy_{\periodindex,\scenarioindex,\timeindex} - \elemarketcostsell_{\periodindex,\scenarioindex,\timeindex}`

#.  **Electricity Purchase**: The cost incurred from purchasing electricity from the market. This cost is defined by the constraint «``eTotalEleTradeCost``» and includes variable energy costs, taxes, and other fees.

    .. math::
       \elemarketcostbuy_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} (&(\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketbuyingratio_{\traderindex} + \pelemarketcertrevenue_{\traderindex} \pfactorone + \pelemarketpassthrough_{\traderindex} \pfactorone) \\
       & (1 + \pelemarketmoms_{\traderindex} \pfactorone) + \pelemarketnetfee_{\traderindex} \pfactorone) \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}

#.  **Electricity Sales**: The revenue generated from selling electricity to the market. This is defined by the constraint ``eTotalEleTradeProfit``.

    .. math::
       \elemarketcostsell_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRE} (\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \pelemarketsellingratio_{\traderindex} \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})

Hydrogen Market Costs
^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydMCost``».

:math:`\hydmarketcost_{\periodindex,\scenarioindex,\timeindex} = \hydmarketcostbuy_{\periodindex,\scenarioindex,\timeindex} - \hydmarketcostsell_{\periodindex,\scenarioindex,\timeindex}`

#.  **Hydrogen Purchase**: The cost incurred from purchasing hydrogen from the market, as defined by ``eTotalHydTradeCost``.

    .. math::
       \hydmarketcostbuy_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} (\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex})

#.  **Hydrogen Sales**: The revenue generated from selling hydrogen to the market, as defined by ``eTotalHydTradeProfit``.

    .. math::
       \hydmarketcostsell_{\periodindex,\scenarioindex,\timeindex} = \sum_{\traderindex \in \nRH} (\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\traderindex} \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})

Generation Costs
~~~~~~~~~~~~~~~~
This is the operational cost of running the generation and production assets. It typically includes:
*   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
*   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
*   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

The cost is defined by ``eTotalEleGCost`` for electricity and ``eTotalHydGCost`` for hydrogen.

Electricity Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleGCost``».

.. math::
   \begin{aligned}
   \elegenerationcost_{\periodindex,\scenarioindex,\timeindex}
   = &\sum_{\genindex \in \nGE}
      \Big(
           \pvariablecost_{\genindex}\,\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pmaintenancecost_{\genindex}\,\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
      \Big) \\
   &
      + \sum_{\genindex \in \nGENR}
      \Big(
           \pfixedcost_{\genindex}\,\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         \!+\! \pstartupcost_{\genindex}\,\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         \!+\! \pshutdowncost_{\genindex}\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
      \Big)
   \end{aligned}

Hydrogen Generation Costs
^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydGCost``».

.. math::
   \begin{aligned}
   \hydgenerationcost_{\periodindex,\scenarioindex,\timeindex}
   = \sum_{\genindex \in \nGH}
      \Big(&
           \pvariablecost_{\genindex}\,\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pmaintenancecost_{\genindex}\,\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}\\
   &
         + \pfixedcost_{\genindex}\,\vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pstartupcost_{\genindex}\,\vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
         + \pshutdowncost_{\genindex}\,\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
      \Big)
   \end{aligned}

Emission Costs
~~~~~~~~~~~~~~
This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (:math:`\pcarbonprice_{\genindex}`).
The formulation is defined by «``eTotalECost``».


.. math::
    \carboncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\genindex \in \nGENR} \pcarbonprice_{\genindex} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}

Consumption Costs
~~~~~~~~~~~~~~~~~
This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices.

Electricity Consumption Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleCCost``».

.. math::
    \eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEE} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

Hydrogen Consumption Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydCCost``».

.. math::
    \hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\storageindex \in \nEH} \pvariablecost_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}

Reliability Costs
~~~~~~~~~~~~~~~~~
This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (``pParENSCost`` or ``pParHNSCost``), ensuring the model prioritizes meeting demand.
*   Associated variables: ``vENS`` (Energy Not Served), ``vHNS`` (Hydrogen Not Served).

Electricity Energy-not-served Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalEleRCost``».

.. math::
    \eleunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\loadindex \in \nDE} \ploadsheddingcost_{\loadindex} \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex}

Hydrogen Energy-not-served Costs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The formulation is defined by «``eTotalHydRCost``».

.. math::
    \hydunservedenergycost_{\periodindex,\scenarioindex,\timeindex} = \sum_{\loadindex \in \nDH} \ploadsheddingcost_{\loadindex} \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex}

Electricity Peak Demand Costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This component models capacity-based tariffs, where costs are determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs.
The formulation is defined by «``eTotalElePeakCost``».

.. math::
    \elepeakdemandcost_{\periodindex,\scenarioindex} = \frac{1}{|\nKE|} \sum_{\traderindex \in \nRE} \ppeakdemandtariff_{\traderindex} \pfactorone \sum_{\monthindex \in \nM} \sum_{\peakindex \in \nKE} \velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.