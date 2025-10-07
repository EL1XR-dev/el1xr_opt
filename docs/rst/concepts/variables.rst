Variables
=========

The optimization model determines the values of numerous decision variables to minimize the total system cost while satisfying all constraints. These variables represent the physical and economic operations of the energy system. They are defined as `Var` objects in Pyomo within the ``create_variables`` function.

The main variables are indexed by the :doc:`sets <sets>`, primarily by period (:math:`\periodindex`), scenario (:math:`\scenarioindex`), and timestep (:math:`\timeindex`).

They are written in **lowercase** letters.

=========================================================================================================  ==========================================================================================  ========  ===========================================================================
**Symbol**                                                                                                 **Description**                                                                             **Unit**  **oM_ModelFormulation.py**
---------------------------------------------------------------------------------------------------------  ------------------------------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\alpha`                                                                                             Total system cost                                                                           €         «``vTotalSCost``»
:math:`\elemarketcost_{\periodindex,\scenarioindex,\timeindex}`                                            Net cost of electricity market transactions (buying - selling)                              €         «``vTotalEleMCost``»
:math:`\elemarketcostbuy_{\periodindex,\scenarioindex,\timeindex}`                                         Cost of electricity market purchases                                                        €         «``vTotalEleTradeCost``»
:math:`\elemarketcostsell_{\periodindex,\scenarioindex,\timeindex}`                                        Revenue from electricity market sales                                                       €         «``vTotalEleTradeProfit``»
:math:`\hydmarketcost_{\periodindex,\scenarioindex,\timeindex}`                                            Net cost of hydrogen market transactions (buying - selling)                                 €         «``vTotalHydMCost``»
:math:`\hydmarketcostbuy_{\periodindex,\scenarioindex,\timeindex}`                                         Cost of hydrogen market purchases                                                           €         «``vTotalHydTradeCost``»
:math:`\hydmarketcostsell_{\periodindex,\scenarioindex,\timeindex}`                                        Revenue from hydrogen market sales                                                          €         «``vTotalHydTradeProfit``»
:math:`\elegenerationcost_{\periodindex,\scenarioindex,\timeindex}`                                        Total cost of electricity generation                                                        €         «``vTotalEleGCost``»
:math:`\hydgenerationcost_{\periodindex,\scenarioindex,\timeindex}`                                        Total cost of hydrogen generation                                                           €         «``vTotalHydGCost``»
:math:`\carboncost_{\periodindex,\scenarioindex,\timeindex}`                                               Total cost of CO2 emissions                                                                 €         «``vTotalECost``»
:math:`\eleconsumptioncost_{\periodindex,\scenarioindex,\timeindex}`                                       Total cost of electricity consumption (e.g., storage charging)                              €         «``vTotalEleCCost``»
:math:`\hydconsumptioncost_{\periodindex,\scenarioindex,\timeindex}`                                       Total cost of hydrogen consumption (e.g., storage charging)                                 €         «``vTotalHydCCost``»
:math:`\eleunservedenergycost_{\periodindex,\scenarioindex}`                                               Total cost of unserved electricity demand (penalty)                                         €         «``vTotalEleRCost``»
:math:`\hydunservedenergycost_{\periodindex,\scenarioindex}`                                               Total cost of unserved hydrogen demand (penalty)                                            €         «``vTotalHydRCost``»
:math:`\elepeakdemandcost_{\periodindex,\scenarioindex}`                                                   Total cost of electricity peak demand (capacity tariff)                                     €         «``vTotalElePeakCost``»
:math:`\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`                               Electricity bought from the market                                                          kWh       «``vEleBuy``»
:math:`\velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`                              Electricity sold to the market                                                              kWh       «``vEleSell``»
:math:`\vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}`                               Hydrogen bought from the market                                                             kgH2      «``vHydBuy``»
:math:`\vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}`                              Hydrogen sold to the market                                                                 kgH2      «``vHydSell``»
:math:`\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`                                 Electricity output from electricity generator                                               kWh       «``vEleTotalOutput``»
:math:`\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`                                 Hydrogen output from hydrogen generator                                                     kWh       «``vHydTotalOutput``»
:math:`\veleload_{\periodindex,\scenarioindex,\timeindex,\loadindex}`                                      Electricity demand                                                                          kWh       «``vEleDemand``»
:math:`\vhydload_{\periodindex,\scenarioindex,\timeindex,\loadindex}`                                      Hydrogen demand                                                                             kgH2      «``vHydDemand``»
:math:`\veleloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex}`                                  Electricity not served                                                                      kWh       «``vENS``»
:math:`\vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex}`                                  Hydrogen not served                                                                         kgH2      «``vHNS``»
:math:`\velepeakdemand_{\periodindex,\scenarioindex,\monthindex,\traderindex,\peakindex}`                  Electricity peak demand for tariff calculation                                              kW        «``vElePeak``»
:math:`ep_{neg}`                                                                                           Electricity production (discharge if an ESS)                                                GW        «``vEleTotalOutput``»
:math:`ec_{nes}, ec_{nhz}`                                                                                 Electricity consumption of electricity ESS and electrolyzer units                           GW        «``vEleTotalCharge``»
:math:`ep2b_{neg}`                                                                                         Electricity production of the second block (i.e., above the minimum load)                   GW        «``vEleTotalOutput2ndBlock``»
:math:`ec2b_{nes}, ec2b_{nhz}`                                                                             Electricity charge of the second block (i.e., above the minimum charge)                     GW        «``vEleTotalCharge2ndBlock``»
:math:`ep^{\Delta}_{neg}`                                                                                  Electricity production (discharge if an ESS) for market correction                          GW        «``vEleTotalOutputDelta``»
:math:`ec^{\Delta}_{nes}, ec^{\Delta}_{nhz}`                                                               Electricity consumption of electricity ESS and electrolyzer units for market correction     GW        «``vEleTotalChargeDelta``»
:math:`ec^{R+}_{nes}, ec^{R+}_{nhz}`                                                                       Positive ramp of electricity consumption of an ESS and electrolyzer                         GW        «``vEleTotalChargeRampPos``»
:math:`ec^{R-}_{nes}, ec^{R-}_{nhz}`                                                                       Negative ramp of electricity consumption of an ESS and electrolyzer                         GW        «``vEleTotalChargeRampNeg``»
:math:`eei_{nes}`                                                                                          Electricity inflows of an ESS                                                               GWh       «``vEleEnergyInflows``»
:math:`eeo_{nes}`                                                                                          Electricity outflows of an ESS                                                              GWh       «``vEleEnergyOutflows``»
:math:`esi_{nes}`                                                                                          Electricity ESS stored energy (inventory, SoC for batteries)                                GWh       «``vEleInventory``»
:math:`ess_{nes}`                                                                                          Electricity ESS spilled energy                                                              GWh       «``vEleSpillage``»
:math:`hp_{nhg}`                                                                                           Hydrogen production (discharge if an ESS)                                                   kgH2      «``vHydTotalOutput``»
:math:`hc_{nhs}, hc_{neg}`                                                                                 Hydrogen consumption of hydrogen ESS and electricity thermal units                          kgH2      «``vHydTotalCharge``»
:math:`hp2b_{nhg}`                                                                                         Hydrogen production of the second block (i.e., above the minimum load)                      kgH2      «``vHydTotalOutput2ndBlock``»
:math:`hc2b_{nhs}, hc2b_{neg}`                                                                             Hydrogen charge of the second block (i.e., above the minimum charge)                        kgH2      «``vHydTotalCharge2ndBlock``»
:math:`hp^{\Delta}_{nhg}`                                                                                  Hydrogen production (discharge if an ESS) for market correction                             kgH2      «``vHydTotalOutputDelta``»
:math:`hc^{\Delta}_{nhs}, hc^{\Delta}_{neg}`                                                               Hydrogen consumption of hydrogen ESS and electricity thermal units for market correction    kgH2      «``vHydTotalChargeDelta``»
:math:`hei_{nhs}`                                                                                          Hydrogen inflows of an ESS                                                                  GWh       «``vHydEnergyInflows``»
:math:`heo_{nhs}`                                                                                          Hydrogen outflows of an ESS                                                                 GWh       «``vHydEnergyOutflows``»
:math:`hsi_{nhs}`                                                                                          Hydrogen ESS stored energy (inventory, SoC for batteries)                                   GWh       «``vHydInventory``»
:math:`hss_{nhs}`                                                                                          Hydrogen ESS spilled energy                                                                 GWh       «``vHydSpillage``»
:math:`ec^{Comp}_{nhs}`                                                                                    Electricity consumption of a compressor unit to compress hydrogen                           kgH2      «``vHydCompressorConsumption``»
:math:`ec^{StandBy}_{nhz}`                                                                                 Electricity consumption of a electrolyzer unit during the standby mode                      kgH2      «``vHydStandByConsumption``»
:math:`up^{SR}_{neg}, dp^{SR}_{neg}`                                                                       Upward and downward :math:`SR` operating reserves of a generating or ESS unit               GW        «``vEleReserveProd_Up_SR``, ``vEleReserveProd_Down_SR``»
:math:`uc^{SR}_{nes}, dc^{SR}_{nes}`                                                                       Upward and downward :math:`SR` operating reserves of an ESS as a consumption unit           GW        «``vEleReserveCons_Up_SR``, ``vEleReserveCons_Down_SR``»
:math:`up^{TR}_{ωneg}, dp^{TR}_{ωneg}`                                                                     Upward and downward :math:`TR` operating reserves of a generating or ESS unit               GW        «``vEleReserveProd_Up_TR``, ``vEleReserveProd_Down_TR``»
:math:`uc^{TR}_{ωnes}, dc^{TR}_{ωnes}`                                                                     Upward and downward :math:`TR` operating reserves of an ESS as a consumption unit           GW        «``vEleReserveCons_Up_TR``, ``vEleReserveCons_Down_TR``»
:math:`euc_{neg}, esu_{neg}, esd_{neg}`                                                                    Commitment, startup and shutdown of electricity generation unit per load level              {0,1}     «``vGenCommitment``, ``vGenStartup``, ``vGenShutdown``»
:math:`euc^{max}_{neg}`                                                                                    Maximum commitment of electricity generation unit per load level                            {0,1}     «``vGenMaxCommitment``»
:math:`huc_{nhg}`                                                                                          Commitment of hydrogen generation unit per load level                                       {0,1}     «``vHydCommitment``, ``vHydStartup``, ``vHydShutdown``»
:math:`huc^{max}_{nhg}`                                                                                    Maximum commitment of hydrogen generation unit per load level                               {0,1}     «``vHydMaxCommitment``»
:math:`esf_{nes}`                                                                                          Electricity ESS energy functioning per load level, charging or discharging                  {0,1}     «``vEleStorOperat``»
:math:`hsf_{nhs}`                                                                                          Hydrogen ESS energy functioning per load level, charging or discharging                     {0,1}     «``vHydStorOperat``»
:math:`hcf_{nhs}`                                                                                          Hydrogen compressor functioning, off or on                                                  {0,1}     «``vHydCompressorOperat``»
:math:`hsb_{nhg}`                                                                                          Hydrogen electrolyzer StandBy mode, off or on                                               {0,1}     «``vHydStandBy``»
:math:`ef_{nijc}`                                                                                          Electricity transmission flow through a line                                                GW        «``vEleNetFlow``»
:math:`hf_{nijc}`                                                                                          Hydrogen transmission flow through a pipeline                                               kgH2      «``vHydNetFlow``
:math:`theta_{ni}`                                                                                         Voltage angle of a node                                                                     rad       «``vEleNetTheta``»
=========================================================================================================  ==========================================================================================  ========  ===========================================================================

Key Variable Categories
-----------------------

1. Cost and Objective Function Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These are high-level variables used to structure the objective function.

*   ``vTotalSCost``: The main objective function variable, representing the total system cost over the entire horizon [M€].
*   ``vTotalEleGCost``, ``vTotalHydGCost``: Total generation costs for electricity and hydrogen systems, respectively.
*   ``vTotalEleMCost``, ``vTotalHydMCost``: Total costs from trading on the electricity and hydrogen markets.
*   ``vTotalECost``: Total cost of CO2 emissions.
*   ``vTotalEleRCost``, ``vTotalHydRCost``: Total reliability costs (i.e., cost of unserved energy).

2. Market and Trading Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These variables represent interactions with external energy markets.

*   ``vEleBuy`` / ``vEleSell``: Power purchased from or sold to the electricity market [GW].
*   ``vHydBuy`` / ``vHydSell``: Hydrogen purchased from or sold to the hydrogen market [tH2].
*   ``vElePeak``: The peak electricity demand within a billing period (e.g., a month), used to calculate capacity-based tariffs [GW].

3. Generation and Dispatch Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These variables control the output of production units.

*   ``vEleTotalOutput``: The total power output of an electricity generation unit [GW]. This is the primary dispatch variable.
*   ``vHydTotalOutput``: The total output of a hydrogen production unit [tH2].
*   ``vEleTotalOutput2ndBlock`` / ``vHydTotalOutput2ndBlock``: The output of a generator above its minimum stable level. This is used to model piecewise linear production costs.

4. Energy Storage Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^

These variables manage the state and operation of energy storage assets like batteries and hydrogen tanks.

*   ``vEleTotalCharge`` / ``vHydTotalCharge``: The rate of power being consumed to charge a storage unit [GW or tH2].
*   ``vEleInventory`` / ``vHydInventory``: The amount of energy stored in a unit at a given time [GWh or tH2]. This is often called the State of Charge (SoC).
*   ``vEleSpillage`` / ``vHydSpillage``: Energy that is discarded because the storage is full and cannot accept more input [GWh or tH2].
*   ``vEleEnergyInflows`` / ``vEleEnergyOutflows``: Unscheduled or scheduled energy transfers, typically used for assets like hydroelectric reservoirs.

5. Network and Flow Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These variables describe the movement of energy through the electricity and hydrogen grids.

*   ``vEleNetFlow``: The flow of power on a specific transmission line [GW].
*   ``vHydNetFlow``: The flow of hydrogen in a specific pipeline [tH2].
*   ``vEleNetTheta``: The voltage angle at a node in the electricity grid, used for DC power flow calculations.

6. Unit Commitment Variables (Binary)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These are binary (0 or 1) variables that model on/off decisions for dispatchable assets.

*   ``vEleGenCommitment`` / ``vHydGenCommitment``: Indicates if a generator is committed (online) and available for dispatch (1) or offline (0).
*   ``vEleGenStartUp`` / ``vEleGenShutDown``: Indicates if a generator performs a start-up or shut-down action in a given timestep.
*   ``vEleStorOperat`` / ``vHydStorOperat``: A binary variable to prevent simultaneous charging and discharging of a storage unit.
*   ``vEleNetCommit``: Indicates if a transmission line is switched on (1) or off (0).

7. Demand and Reliability Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*   ``vEleDemand`` / ``vHydDemand``: The amount of demand being served. For flexible loads, this can be a variable.
*   ``vEleDemFlex``: The amount of demand shifted in time for flexible loads [GW].
*   ``vENS`` (Energy Not Supplied) / ``vHNS`` (Hydrogen Not Supplied): Slack variables that represent the amount of demand that could not be met. These are heavily penalized in the objective function to ensure they are only non-zero when supply is physically insufficient.

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