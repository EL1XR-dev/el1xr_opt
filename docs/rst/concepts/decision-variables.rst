Decision Variables
==================

The optimization model determines the values of numerous decision variables to minimize the total system cost while satisfying all constraints. These variables represent the physical and economic operations of the energy system. They are defined as `Var` objects in Pyomo within the ``create_variables`` function.

The main variables are indexed by the :doc:`model sets <model-sets>`, primarily by period (`p`), scenario (`sc`), and timestep (`n`).

Key Variable Categories
-----------------------

### 1. Cost and Objective Function Variables

These are high-level variables used to structure the objective function.

*   ``vTotalSCost``: The main objective function variable, representing the total system cost over the entire horizon [M€].
*   ``vTotalEleGCost``, ``vTotalHydGCost``: Total generation costs for electricity and hydrogen systems, respectively.
*   ``vTotalEleMCost``, ``vTotalHydMCost``: Total costs from trading on the electricity and hydrogen markets.
*   ``vTotalECost``: Total cost of CO2 emissions.
*   ``vTotalEleRCost``, ``vTotalHydRCost``: Total reliability costs (i.e., cost of unserved energy).

### 2. Market and Trading Variables

These variables represent interactions with external energy markets.

*   ``vEleBuy`` / ``vEleSell``: Power purchased from or sold to the electricity market [GW].
*   ``vHydBuy`` / ``vHydSell``: Hydrogen purchased from or sold to the hydrogen market [tH2].
*   ``vElePeak``: The peak electricity demand within a billing period (e.g., a month), used to calculate capacity-based tariffs [GW].

### 3. Generation and Dispatch Variables

These variables control the output of production units.

*   ``vEleTotalOutput``: The total power output of an electricity generation unit [GW]. This is the primary dispatch variable.
*   ``vHydTotalOutput``: The total output of a hydrogen production unit [tH2].
*   ``vEleTotalOutput2ndBlock`` / ``vHydTotalOutput2ndBlock``: The output of a generator above its minimum stable level. This is used to model piecewise linear production costs.

### 4. Energy Storage Variables

These variables manage the state and operation of energy storage assets like batteries and hydrogen tanks.

*   ``vEleTotalCharge`` / ``vHydTotalCharge``: The rate of power being consumed to charge a storage unit [GW or tH2].
*   ``vEleInventory`` / ``vHydInventory``: The amount of energy stored in a unit at a given time [GWh or tH2]. This is often called the State of Charge (SoC).
*   ``vEleSpillage`` / ``vHydSpillage``: Energy that is discarded because the storage is full and cannot accept more input [GWh or tH2].
*   ``vEleEnergyInflows`` / ``vEleEnergyOutflows``: Unscheduled or scheduled energy transfers, typically used for assets like hydroelectric reservoirs.

### 5. Network and Flow Variables

These variables describe the movement of energy through the electricity and hydrogen grids.

*   ``vEleNetFlow``: The flow of power on a specific transmission line [GW].
*   ``vHydNetFlow``: The flow of hydrogen in a specific pipeline [tH2].
*   ``vEleNetTheta``: The voltage angle at a node in the electricity grid, used for DC power flow calculations.

### 6. Unit Commitment Variables (Binary)

These are binary (0 or 1) variables that model on/off decisions for dispatchable assets.

*   ``vEleGenCommitment`` / ``vHydGenCommitment``: Indicates if a generator is committed (online) and available for dispatch (1) or offline (0).
*   ``vEleGenStartUp`` / ``vEleGenShutDown``: Indicates if a generator performs a start-up or shut-down action in a given timestep.
*   ``vEleStorOperat`` / ``vHydStorOperat``: A binary variable to prevent simultaneous charging and discharging of a storage unit.
*   ``vEleNetCommit``: Indicates if a transmission line is switched on (1) or off (0).

### 7. Demand and Reliability Variables

*   ``vEleDemand`` / ``vHydDemand``: The amount of demand being served. For flexible loads, this can be a variable.
*   ``vEleDemFlex``: The amount of demand shifted in time for flexible loads [GW].
*   ``vENS`` (Energy Not Supplied) / ``vHNS`` (Hydrogen Not Supplied): Slack variables that represent the amount of demand that could not be met. These are heavily penalized in the objective function to ensure they are only non-zero when supply is physically insufficient.