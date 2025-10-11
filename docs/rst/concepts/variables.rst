.. _variables:

Variables
=========

The optimization model determines the values of numerous decision variables to minimize the total system cost while satisfying all constraints. These variables represent the physical and economic operations of the energy system. They are defined as `Var` objects in Pyomo within the ``create_variables`` function.

The main variables are indexed by the :doc:`sets <sets>`, primarily by period (:math:`\periodindex`), scenario (:math:`\scenarioindex`), and timestep (:math:`\timeindex`), and are written in **lowercase** letters.

Costs & Objective
-----------------

These high-level variables are used to structure the objective function, representing the total costs and revenues over the entire optimization horizon.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\alpha`
     - Total system cost (the main objective function)
     - €
     - ``vTotalSCost``
   * - :math:`\elemarketcost_{\periodindex,\scenarioindex,\timeindex}`
     - Net cost of electricity market transactions
     - €
     - ``vTotalEleMCost``
   * - :math:`\elemarketcostbuy_{\periodindex,\scenarioindex,\timeindex}`
     - Cost of electricity market purchases
     - €
     - ``vTotalEleTradeCost``
   * - :math:`\elemarketcostsell_{\periodindex,\scenarioindex,\timeindex}`
     - Revenue from electricity market sales
     - €
     - ``vTotalEleTradeProfit``
   * - :math:`\hydmarketcost_{\periodindex,\scenarioindex,\timeindex}`
     - Net cost of hydrogen market transactions
     - €
     - ``vTotalHydMCost``
   * - :math:`\hydmarketcostbuy_{\periodindex,\scenarioindex,\timeindex}`
     - Cost of hydrogen market purchases
     - €
     - ``vTotalHydTradeCost``
   * - :math:`\hydmarketcostsell_{\periodindex,\scenarioindex,\timeindex}`
     - Revenue from hydrogen market sales
     - €
     - ``vTotalHydTradeProfit``
   * - :math:`\elegenerationcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total cost of electricity generation
     - €
     - ``vTotalEleGCost``
   * - :math:`\hydgenerationcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total cost of hydrogen generation
     - €
     - ``vTotalHydGCost``
   * - :math:`\carboncost_{\periodindex,\scenarioindex,\timeindex}`
     - Total cost of CO2 emissions
     - €
     - ``vTotalECost``
   * - :math:`\eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex}`
     - Total cost of electricity consumption
     - €
     - ``vTotalEleCCost``
   * - :math:`\hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex}`
     - Total cost of hydrogen consumption
     - €
     - ``vTotalHydCCost``
   * - :math:`\eleunservedenergycost_{\periodindex,\scenarioindex}`
     - Cost of unserved electricity (reliability penalty)
     - €
     - ``vTotalEleRCost``
   * - :math:`\hydunservedenergycost_{\periodindex,\scenarioindex}`
     - Cost of unserved hydrogen (reliability penalty)
     - €
     - ``vTotalHydRCost``
   * - :math:`\elepeakdemandcost_{\periodindex,\scenarioindex}`
     - Cost of electricity peak demand (capacity tariff)
     - €
     - ``vTotalElePeakCost``

Market & Trading
----------------

These variables represent the interactions with external energy markets.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Electricity bought from the market
     - kWh
     - ``vEleBuy``
   * - :math:`\velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Electricity sold to the market
     - kWh
     - ``vEleSell``
   * - :math:`\vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Hydrogen bought from the market
     - kgH2
     - ``vHydBuy``
   * - :math:`\vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Hydrogen sold to the market
     - kgH2
     - ``vHydSell``
   * - :math:`\velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}`
     - Electricity peak demand for tariff calculation
     - kW
     - ``vElePeak``
   * - :math:`\velepeakdemandindbin_{\periodindex,\scenarioindex,\timeindex,\traderindex,\peakindex}`
     - Binary indicator for electricity peak demand
     - '{0,1}'
     - ``vElePeakHourInd``

Asset Operations (Generation, Storage, and Demand)
--------------------------------------------------

These variables control the physical operation of all assets in the system.

**Generation**
~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Electricity output from a generator
     - kWh
     - ``vEleTotalOutput``
   * - :math:`\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Hydrogen output from a generator
     - kgH2
     - ``vHydTotalOutput``
   * - :math:`ep2b_{neg}`
     - Elec. production above min. stable level
     - kW
     - ``vEleTotalOutput2ndBlock``
   * - :math:`hp2b_{nhg}`
     - Hyd. production above min. stable level
     - kgH2
     - ``vHydTotalOutput2ndBlock``
   * - :math:`ep^{\Delta}_{neg}`
     - Elec. production for market correction
     - kW
     - ``vEleTotalOutputDelta``
   * - :math:`hp^{\Delta}_{nhg}`
     - Hyd. production for market correction
     - kgH2
     - ``vHydTotalOutputDelta``

**Consumption & Demand**
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`ec_{nes}, ec_{nhz}`
     - Electricity consumption (ESS & electrolyzer)
     - kW
     - ``vEleTotalCharge``
   * - :math:`hc_{nhs}, hc_{neg}`
     - Hydrogen consumption (ESS & thermal units)
     - kgH2
     - ``vHydTotalCharge``
   * - :math:`ec2b_{nes}, ec2b_{nhz}`
     - Elec. charge above min. stable level
     - kW
     - ``vEleTotalCharge2ndBlock``
   * - :math:`hc2b_{nhs}, hc2b_{neg}`
     - Hyd. charge above min. stable level
     - kgH2
     - ``vHydTotalCharge2ndBlock``
   * - :math:`ec^{\Delta}_{nes}, ec^{\Delta}_{nhz}`
     - Elec. consumption for market correction
     - kW
     - ``vEleTotalChargeDelta``
   * - :math:`hc^{\Delta}_{nhs}, hc^{\Delta}_{neg}`
     - Hyd. consumption for market correction
     - kgH2
     - ``vHydTotalChargeDelta``
   * - :math:`ec^{R+}_{nes}, ec^{R+}_{nhz}`
     - Positive ramp of electricity consumption
     - kW
     - ``vEleTotalChargeRampPos``
   * - :math:`ec^{R-}_{nes}, ec^{R-}_{nhz}`
     - Negative ramp of electricity consumption
     - kW
     - ``vEleTotalChargeRampNeg``
   * - :math:`ec^{Comp}_{nhs}`
     - Elec. consumption of a compressor
     - kgH2
     - ``vHydCompressorConsumption``
   * - :math:`ec^{StandBy}_{nhz}`
     - Elec. consumption of an electrolyzer in standby
     - kgH2
     - ``vHydStandByConsumption``
   * - :math:`\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Electricity demand served
     - kWh
     - ``vEleDemand``
   * - :math:`\vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Hydrogen demand served
     - kgH2
     - ``vHydDemand``
   * - :math:`\veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Unserved electricity (energy not supplied)
     - kWh
     - ``vENS``
   * - :math:`\vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Unserved hydrogen (hydrogen not supplied)
     - kgH2
     - ``vHNS``
   * - :math:`\veledemflex_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Flexible electricity demand
     - kWh
     - ``vEleDemFlex``
   * - :math:`\veleconsumptioncompress_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Electricity consumption of a compressor
     - kWh
     - ``vHydCompressorConsumption``
   * - :math:`\veleconsumptionstandby_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Electricity consumption of an electrolyzer in standby
     - kWh
     - ``vHydStandByConsumption``
   * - :math:`\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Elec. production above min. stable level
     - kW
     - ``vEleTotalOutput2ndBlock``
   * - :math:`\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Hyd. production above min. stable level
     - kgH2
     - ``vHydTotalOutput2ndBlock``
   * - :math:`\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Elec. charge above min. stable level
     - kW
     - ``vEleTotalCharge2ndBlock``
   * - :math:`\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Hyd. charge above min. stable level
     - kgH2
     - ``vHydTotalCharge2ndBlock``

**Storage**
~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`esi_{nes}`
     - Stored energy in an elec. ESS (State of Charge)
     - kWh
     - ``vEleInventory``
   * - :math:`hsi_{nhs}`
     - Stored energy in a hyd. ESS (State of Charge)
     - kWh
     - ``vHydInventory``
   * - :math:`eei_{nes}` / :math:`eeo_{nes}`
     - Inflows/Outflows of an electricity ESS
     - kWh
     - ``vEleEnergyInflows``, ``vEleEnergyOutflows``
   * - :math:`hei_{nhs}` / :math:`heo_{nhs}`
     - Inflows/Outflows of a hydrogen ESS
     - kWh
     - ``vHydEnergyInflows``, ``vHydEnergyOutflows``
   * - :math:`ess_{nes}`
     - Spilled energy from an electricity ESS
     - kWh
     - ``vEleSpillage``
   * - :math:`hss_{nhs}`
     - Spilled energy from a hydrogen ESS
     - kWh
     - ``vHydSpillage``

Ancillary Services
------------------

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`rp^{FN}_{neg}, rc^{FN}_{nes}`
     - FCR from a producer (gen/ESS) or consumer (ESS)
     - kW
     - ``vEleReserveFCR_Prod``, ``vEleReserveFCR_Cons``
   * - :math:`up^{FD}_{neg}, dp^{FD}_{neg}`
     - Up/down FD from a producer (gen/ESS)
     - kW
     - ``vEleReserveProd_Up_FD``, ``vEleReserveProd_Down_FD``
   * - :math:`uc^{FD}_{nes}, dc^{FD}_{nes}`
     - Up/down SR from a consumer (ESS)
     - kW
     - ``vEleReserveCons_Up_FD``, ``vEleReserveCons_Down_FD``

Network
-------

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`ef_{nijc}`
     - Electricity flow on a transmission line
     - kW
     - ``vEleNetFlow``
   * - :math:`hf_{nijc}`
     - Hydrogen flow in a pipeline
     - kgH2
     - ``vHydNetFlow``
   * - :math:`theta_{ni}`
     - Voltage angle at a node (for DC power flow)
     - rad
     - ``vEleNetTheta``

Binary & Logical
----------------

These binary (0 or 1) variables model on/off decisions, operational states, and logical constraints.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`euc_{neg}, esu_{neg}, esd_{neg}`
     - Commitment, startup, & shutdown of an elec. unit
     - {0,1}
     - ``vGenCommitment``, ``vGenStartup``, ``vGenShutdown``
   * - :math:`euc^{max}_{neg}`
     - Maximum commitment of an elec. unit
     - {0,1}
     - ``vGenMaxCommitment``
   * - :math:`huc_{nhg}`
     - Commitment of a hydrogen unit
     - {0,1}
     - ``vHydCommitment``, ``vHydStartup``, ``vHydShutdown``
   * - :math:`huc^{max}_{nhg}`
     - Maximum commitment of a hydrogen unit
     - {0,1}
     - ``vHydMaxCommitment``
   * - :math:`esf_{nes}`
     - Operating state of an elec. ESS (charge/discharge)
     - {0,1}
     - ``vEleStorOperat``
   * - :math:`hsf_{nhs}`
     - Operating state of a hyd. ESS (charge/discharge)
     - {0,1}
     - ``vHydStorOperat``
   * - :math:`hcf_{nhs}`
     - Operating state of a hydrogen compressor (on/off)
     - {0,1}
     - ``vHydCompressorOperat``
   * - :math:`hsb_{nhg}`
     - Standby mode of an electrolyzer (on/off)
     - {0,1}
     - ``vHydStandBy``
   * - :math:`\vflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}`
     - Electricity flow on a transmission line
     - kW
     - ``vEleNetFlow``
   * - :math:`\vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}`
     - Hydrogen flow in a pipeline
     - kgH2
     - ``vHydNetFlow``
   * - :math:`\vCupward_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Upward reserve from a consumer
     - kW
     - ``vEleReserveCons_Up_FD``
   * - :math:`\vCdownward_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Downward reserve from a consumer
     - kW
     - ``vEleReserveCons_Down_FD``
   * - :math:`\vPupward_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Upward reserve from a producer
     - kW
     - ``vEleReserveProd_Up_FD``
   * - :math:`\vPdownward_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Downward reserve from a producer
     - kW
     - ``vEleReserveProd_Down_FD``
   * - :math:`\velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Commitment of an elec. unit
     - {0,1}
     - ``vGenCommitment``
   * - :math:`\velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Startup of an elec. unit
     - {0,1}
     - ``vGenStartup``
   * - :math:`\vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Shutdown of an elec. unit
     - {0,1}
     - ``vGenShutdown``
   * - :math:`\vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Commitment of a hydrogen unit
     - {0,1}
     - ``vHydCommitment``
   * - :math:`\vhydstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Startup of a hydrogen unit
     - {0,1}
     - ``vHydStartup``
   * - :math:`\vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Shutdown of a hydrogen unit
     - {0,1}
     - ``vHydShutdown``
   * - :math:`\velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Operating state of an elec. ESS (charge/discharge)
     - {0,1}
     - ``vEleStorOperat``
   * - :math:`\vhydstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Operating state of a hyd. ESS (charge/discharge)
     - {0,1}
     - ``vHydStorOperat``
   * - :math:`\vhydcompressbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Operating state of a hydrogen compressor (on/off)
     - {0,1}
     - ``vHydCompressorOperat``

Variable Bounding and Fixing
----------------------------

To improve performance and ensure physical realism, the model applies tight bounds to variables and, in some cases, fixes them entirely during a pre-processing step within the ``create_variables`` function.

**Bounding:**

Each decision variable is bounded using physical and economic parameters provided in the input data. For example, the ``vEleTotalOutput`` of a generator is bounded between 0 and its maximum power capacity (``pEleMaxPower``) for each specific time step. This ensures that the solver only explores a feasible solution space.

**Fixing:**

Variable fixing is a powerful technique used to reduce the complexity of the optimization problem. If a variable's value can be determined with certainty before the solve, it is fixed to that value. This effectively removes it from the set of variables the solver needs to determine. Examples include:

*   **Unavailable Assets**: If a generator has a maximum capacity of zero at a certain time (e.g., due to a planned outage or no renewable resource), its output variable (``vEleTotalOutput``) is fixed to 0 for that time.
*   **Logical Constraints**: If a storage unit has no charging capacity, its charging variable (``vEleTotalCharge``) is fixed to 0.
*   **Reference Values**: The voltage angle (``vEleNetTheta``) of the designated reference node is fixed to 0 to provide a reference for the DC power flow calculation.

**Benefits:**

This strategy of tightly bounding and fixing variables is crucial for the model's performance and scalability. By reducing the number of free variables and constraining the solution space, it:

*   Creates a **tighter model formulation**, which can be solved more efficiently.
*   **Reduces the overall problem size**, leading to faster computation times.
*   Improves the model's **scalability**, allowing it to handle larger and more complex energy systems without a prohibitive increase in solve time.