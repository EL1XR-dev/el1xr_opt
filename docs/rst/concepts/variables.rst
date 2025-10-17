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
   * - :math:`\marketcost_{\periodindex,\scenarioindex}`
     - Total system component cost
     - €
     - ``vTotalCComponent``
   * - :math:`\marketrevenue_{\periodindex,\scenarioindex}`
     - Total system component revenue
     - €
     - ``vTotalRComponent``
   * - :math:`\elemarketcostgrid_{\periodindex,\scenarioindex}`
     - Total fixed electricity network cost
     - €
     - ``vTotalEleNCost``
   * - :math:`\elemarketcosttax_{\periodindex,\scenarioindex}`
     - Total tax and surcharges electricity cost
     - €
     - ``vTotalEleXCost``
   * - :math:`\elemarketcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable electricity market cost
     - €
     - ``vTotalEleMCost``
   * - :math:`\hydmarketcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable hydrogen market cost
     - €
     - ``vTotalHydMCost``
   * - :math:`\elemaintopercost_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity operational cost
     - €
     - ``vTotalEleOCost``
   * - :math:`\elemaintopercost_{\periodindex,\scenarioindex,\timeindex}`
     - Total hydrogen operational cost
     - €
     - ``vTotalHydOCost``
   * - :math:`\eledegradationcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity degradation cost
     - €
     - ``vTotalEleDCost``
   * - :math:`\hyddegradationcost_{\periodindex,\scenarioindex,\timeindex}`
     - Total hydrogen degradation cost
     - €
     - ``vTotalHydDCost``
   * - :math:`\elemarketrevenuetax_{\periodindex,\scenarioindex}`
     - Total tax electricity revenue
     - €
     - ``vTotalEleXRev``
   * - :math:`\elemarketrevenue_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable electricity market revenue
     - €
     - ``vTotalEleMRev``
   * - :math:`\hydmarketrevenue_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable hydrogen market revenue
     - €
     - ``vTotalHydMRev``
   * - :math:`\elepeakdemandcost_{\periodindex,\scenarioindex}`
     - Total electricity peak cost
     - €
     - ``vTotalElePeakCost``
   * - :math:`\elenetusecost_{\periodindex,\scenarioindex}`
     - Total electricity network usage cost
     - €
     - ``vTotalEleNetUseCost``
   * - :math:`\elecaptariffcost_{\periodindex,\scenarioindex}`
     - Total electricity capacity tariff cost
     - €
     - ``vTotalEleCapTariffCost``
   * - :math:`\elemarketcostDA_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity day-ahead market cost
     - €
     - ``vTotalEleMrkDACost``
   * - :math:`\elemarketcostPPA_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity PPA market cost
     - €
     - ``vTotalEleMrkPPACost``
   * - :math:`\elemarketrevenueDA_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity day-ahead market revenue
     - €
     - ``vTotalEleMrkDARev``
   * - :math:`\elemarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity PPA market revenue
     - €
     - ``vTotalEleMrkPPARev``
   * - :math:`\elemarketrevenueancillary_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity frequency market revenue
     - €
     - ``vTotalEleMrkFrqRev``
   * - :math:`\hydmarketcostPPA_{\periodindex,\scenarioindex,\timeindex}`
     - Total hydrogen PPA market cost
     - €
     - ``vTotalHydMrkPPACost``
   * - :math:`\hydmarketrevenuePPA_{\periodindex,\scenarioindex,\timeindex}`
     - Total hydrogen PPA market revenue
     - €
     - ``vTotalHydMrkPPARev``
   * - :math:`\chi^{VAT^{Ele}}_{\periodindex,\scenarioindex}`
     - Total electricity VAT cost
     - €
     - ``vTotalEleVATCost``
   * - :math:`\rho^{IS^{Ele}}_{\periodindex,\scenarioindex}`
     - Total electricity incentives revenue
     - €
     - ``vTotalEleISRev``
   * - :math:`\chi^{Prod^{Ele}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable electricity production cost
     - €
     - ``vTotalEleGCost``
   * - :math:`\chi^{Prod^{Hyd}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable hydrogen production cost
     - €
     - ``vTotalHydGCost``
   * - :math:`\chi^{CO_2}_{\periodindex,\scenarioindex,\timeindex}`
     - Total electricity emission cost
     - €
     - ``vTotalEleECost``
   * - :math:`\chi^{Cons^{Ele}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable electricity consumption cost
     - €
     - ``vTotalEleCCost``
   * - :math:`\chi^{Cons^{Hyd}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total variable hydrogen consumption cost
     - €
     - ``vTotalHydCCost``
   * - :math:`\chi^{Rel^{Ele}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total system electricity reliability cost
     - €
     - ``vTotalEleRCost``
   * - :math:`\chi^{Rel^{Hyd}}_{\periodindex,\scenarioindex,\timeindex}`
     - Total system hydrogen reliability cost
     - €
     - ``vTotalHydRCost``

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
   * - :math:`\velebuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Electricity bought from the market
     - kW
     - ``vEleBuy``
   * - :math:`\velesell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Electricity sold to the market
     - kW
     - ``vEleSell``
   * - :math:`\vhydbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Hydrogen bought from the market
     - kgH2
     - ``vHydBuy``
   * - :math:`\vhydsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`
     - Hydrogen sold to the market
     - kgH2
     - ``vHydSell``
   * - :math:`\velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}`
     - Electricity peak demand for tariff calculation
     - kW
     - ``vEleDemPeak``
   * - :math:`\vhydpeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}`
     - Hydrogen peak demand for tariff calculation
     - kgH2
     - ``vHydDemPeak``
   * - :math:`\velepeakdemandbin_{\periodindex,\scenarioindex,\timeindex,\traderindex,\peakindex}`
     - Binary indicator for electricity peak demand
     - '{0,1}'
     - ``vElePeakHourInd``
   * - :math:`\vhydpeakdemandbin_{\periodindex,\scenarioindex,\timeindex,\traderindex,\peakindex}`
     - Binary indicator for hydrogen peak demand
     - '{0,1}'
     - ``vHydPeakHourInd``

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
     - kW
     - ``vEleTotalOutput``
   * - :math:`\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Hydrogen output from a generator
     - kgH2
     - ``vHydTotalOutput``
   * - :math:`\veleprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Elec. production above min. stable level
     - kW
     - ``vEleTotalOutput2ndBlock``
   * - :math:`\vhydprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Hyd. production above min. stable level
     - kgH2
     - ``vHydTotalOutput2ndBlock``

**Consumption & Demand**
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\eleconsindex}`
     - Electricity consumption (ESS & electrolyzer)
     - kW
     - ``vEleTotalCharge``
   * - :math:`\vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\hydconsindex}`
     - Hydrogen consumption (ESS & thermal units)
     - kgH2
     - ``vHydTotalCharge``
   * - :math:`\veleconssecondblock_{\periodindex,\scenarioindex,\timeindex,\eleconsindex}`
     - Elec. charge above min. stable level
     - kW
     - ``vEleTotalCharge2ndBlock``
   * - :math:`\vhydconssecondblock_{\periodindex,\scenarioindex,\timeindex,\hydconsindex}`
     - Hyd. charge above min. stable level
     - kgH2
     - ``vHydTotalCharge2ndBlock``
   * - :math:`\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Electricity demand served
     - kW
     - ``vEleDemand``
   * - :math:`\vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Hydrogen demand served
     - kgH2
     - ``vHydDemand``
   * - :math:`\veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Unserved electricity (energy not supplied)
     - kW
     - ``vENS``
   * - :math:`\vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Unserved hydrogen (hydrogen not supplied)
     - kgH2
     - ``vHNS``
   * - :math:`\veledemflex_{\periodindex,\scenarioindex,\timeindex,\demandindex}`
     - Flexible electricity demand
     - kW
     - ``vEleDemFlex``

**Storage**
~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Stored energy in an elec. ESS (State of Charge)
     - kWh
     - ``vEleInventory``
   * - :math:`\vhydinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Stored energy in a hyd. ESS (State of Charge)
     - kgH2
     - ``vHydInventory``
   * - :math:`\veleinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Inflows of an electricity ESS
     - kWh
     - ``vEleEnergyInflows``
   * - :math:`\veleoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Outflows of an electricity ESS
     - kWh
     - ``vEleEnergyOutflows``
   * - :math:`\vhydinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Inflows of a hydrogen ESS
     - kgH2
     - ``vHydEnergyInflows``
   * - :math:`\vhydoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Outflows of a hydrogen ESS
     - kgH2
     - ``vHydEnergyOutflows``
   * - :math:`\velespillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Spilled energy from an electricity ESS
     - kWh
     - ``vEleSpillage``
   * - :math:`\vhydspillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Spilled energy from a hydrogen ESS
     - kgH2
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
     - ``vEleReserveProd_FN``, ``vEleReserveCons_FN``
   * - :math:`\vPupward_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Upwards FCR-D from a producer (gen/ESS)
     - kW
     - ``vEleReserveProd_Up_FD``
   * - :math:`\vPdownward_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Downwards FCR-D from a producer (gen/ESS)
     - kW
     - ``vEleReserveProd_Down_FD``
   * - :math:`\vCupward_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Upwards FCR-D from a consumer (ESS)
     - kW
     - ``vEleReserveCons_Up_FD``
   * - :math:`\vCdownward_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Downwards FCR-D from a consumer (ESS)
     - kW
     - ``vEleReserveCons_Down_FD``

Network
-------

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\veleflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}`
     - Electricity flow on a transmission line
     - kW
     - ``vEleNetFlow``
   * - :math:`\vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}`
     - Hydrogen flow in a pipeline
     - kgH2
     - ``vHydNetFlow``
   * - :math:`\theta_{\periodindex,\scenarioindex,\timeindex,\busindex}`
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
   * - :math:`\velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Commitment of an elec. unit
     - '{0,1}'
     - ``vEleGenCommitment``
   * - :math:`\velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Startup of an elec. unit
     - '{0,1}'
     - ``vEleGenStartUp``
   * - :math:`\veleshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Shutdown of an elec. unit
     - '{0,1}'
     - ``vEleGenShutDown``
   * - :math:`\vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Commitment of a hydrogen unit
     - '{0,1}'
     - ``vHydGenCommitment``
   * - :math:`\vhydstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Startup of a hydrogen unit
     - '{0,1}'
     - ``vHydGenStartUp``
   * - :math:`\vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Shutdown of a hydrogen unit
     - '{0,1}'
     - ``vHydGenShutDown``
   * - :math:`\velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Operating state of an elec. ESS (charge/discharge)
     - '{0,1}'
     - ``vEleStorOperat``
   * - :math:`\vhydstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}`
     - Operating state of a hyd. ESS (charge/discharge)
     - '{0,1}'
     - ``vHydStorOperat``
   * - :math:`\velenetcommitbin_{\periodindex,\scenarioindex,\timeindex,\lineindex}`
     - Commitment of an elec. line
     - '{0,1}'
     - ``vEleNetCommit``
   * - :math:`\vhydnetcommitbin_{\periodindex,\scenarioindex,\timeindex,\pipelineindex}`
     - Commitment of a hyd. pipeline
     - '{0,1}'
     - ``vHydNetCommit``

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
