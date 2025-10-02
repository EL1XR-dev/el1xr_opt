Constraints
===========

The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the `create_constraints` function, enforce everything from the laws of physics to the operational limits of individual assets.

They can be broadly categorized as follows:

1. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (`nd`) and at every timestep (`p,sc,n`), energy supply equals energy demand.

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
Electric vehicles are modeled as a special class of mobile energy storage, identified by the ``model.egv`` set (a subset of ``model.egs``). In addition to the standard energy storage constraints, they are subject to unique logic:

*   ``eEleMinEnergyStartUp``: This constraint ensures that an EV must have a minimum state of charge *before* its availability can change (i.e., before it can be driven away and become unavailable to the grid). This realistically models a user's need for a sufficiently charged vehicle before starting a trip.