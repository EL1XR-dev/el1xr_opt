Constraints
===========

The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

They can be broadly categorized as follows:

1. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (``nd``) and at every timestep (``p,sc,n``), energy supply equals energy demand.

*   ``eEleBalance``: The core electricity balance equation. It states that the sum of all power generated and imported must equal the sum of all power consumed and exported.
*   ``eHydBalance``: The equivalent balance equation for the hydrogen network.

2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

*   **Output and Charge Limits**: Constraints like ``eEleMaxOutput2ndBlock`` and ``eEleMaxESSCharge2ndBlock`` ensure that generators and storage units operate within their rated power capacities.
*   **Ramping Limits**: A series of constraints (e.g., ``eEleMaxRampUpOutput``, ``eEleMaxRampDwCharge``) limit how quickly the output or charging rate of an asset can change from one timestep to the next.
*   **Unit Commitment Logic**: For dispatchable assets, these constraints model the on/off decisions.
    *   ``eEleCommitmentStartupShutdown``: Links the commitment status of a unit to its start-up and shut-down decisions.
    *   ``eEleMinUpTime`` / ``eEleMinDownTime``: Enforce that once a unit is turned on (or off), it must remain in that state for a minimum number of hours.

3. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

*   ``eEleInventory`` / ``eHydInventory``: The core state-of-charge (SoC) balancing equation. It tracks the stored energy level over time, accounting for charging, discharging, and self-discharge/losses.
*   ``eIncompatibilityEleChargeOutflows``: Prevents a storage unit from charging and discharging in the same timestep.

4. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

*   ``eKirchhoff2ndLaw``: For the electricity grid, this implements a DC power flow model, relating the power flow on a line to the voltage angles at its connecting nodes.
*   **Flow Limits**: The ``vEleNetFlow`` and ``vHydNetFlow`` variables are bounded by the thermal or physical capacity of the lines and pipelines.

5. Market and Commercial Constraints
------------------------------------
These constraints model the rules for interacting with external markets.

*   ``eEleRetMaxBuy`` / ``eEleRetMaxSell``: Limit the amount of energy that can be bought from or sold to the market.
*   **Peak Demand Calculation**: A set of constraints starting with ``eElePeak...`` are used to identify the highest power peak within a billing period for tariff calculations.

6. Demand-Side and Reliability Constraints
------------------------------------------
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: While not a constraint itself, the model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The bounds on these variables (0 to total demand) combined with their high penalty cost in the objective function act as a soft constraint to meet demand whenever possible.

7. Electric Vehicle (EV) Modeling
---------------------------------
Electric vehicles are modeled as a special class of mobile energy storage, identified by the ``model.egv`` set (a subset of ``model.egs``). They are subject to standard storage dynamics but with unique constraints and economic drivers that reflect their dual role as both a transportation tool and a potential grid asset.

**Key Modeling Concepts:**

*   **Fixed Nodal Connection**: Each EV is assumed to have a fixed charging point at a specific node (``nd``). All its interactions with the grid (charging and vehicle-to-grid discharging) occur at this single location. This means the EV's charging load (``vEleTotalCharge``) is directly added to the demand side of that node's ``eEleBalance`` constraint, while any discharging (``vEleTotalOutput``) is added to the supply side.

*   **Minimum Starting Charge**: The ``eEleMinEnergyStartUp`` constraint enforces a realistic user behavior: an EV must have a minimum state of charge *before* it can be considered "available" to leave its charging station (i.e., before its availability for grid services can change). This ensures the model doesn't fully drain the battery for grid purposes if the user needs it for a trip.

*   **Driving Consumption (``vEleEnergyOutflows``)**: The energy used for driving is modeled as an outflow from the battery. This can be configured in two ways, offering modeling flexibility:
    *   **Fixed Consumption**: By setting the upper and lower bounds of the outflow to the same value in the input data (e.g., ``pEleMinOutflows`` and ``pEleMaxOutflows``), driving patterns can be treated as a fixed, pre-defined schedule. This is useful for modeling commuters with predictable travel needs.
    *   **Variable Consumption**: Setting different upper and lower bounds allows the model to optimize the driving schedule. This can represent flexible travel plans, uncertain trip lengths, or scenarios where the timing of a trip is part of the optimization problem.

*   **Economic-Driven Charging (Tariff Response)**: The model does not use direct constraints to force EV charging at specific times. Instead, charging behavior is an *emergent property* driven by the objective to minimize total costs. This optimization is influenced by two main types of tariffs:
    *   **Volumetric Tariffs**: The total cost of purchasing energy from the grid (``vTotalEleTradeCost``) includes not just the wholesale energy price but also volumetric network fees (e.g., ``pEleRetnetavgift``). This means the model is incentivized to charge when the *all-in price per MWh* is lowest.
    *   **Capacity Tariffs**: The ``vTotalElePeakCost`` component of the objective function penalizes high monthly power peaks from the grid.

    Since EV charging (``vEleTotalCharge``) increases the total load at a node, the model will naturally schedule it during hours when the combination of volumetric and potential capacity costs is lowest. This interaction between the nodal balance, the cost components, and the objective function creates an economically rational "smart charging" behavior.