Constraints
===========
The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

1. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (:math:`\busindexa`) and at every timestep (:math:`\timeindex`), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
The core electricity balance equation, ``eEleBalance``, states that the sum of all power generated and imported must equal the sum of all power consumed and exported.

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGE} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nEE} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\genindex \in \nGHE} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &- \sum_{(\busindexb,\circuitindex) \in \text{lout}_{\busindex}} \veleflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   + \sum_{(\busindexa,\circuitindex) \in \text{lin}_{\busindex}} \veleflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex} \\
   &+ \sum_{\traderindex \in \nRE} (\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} - \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})
   = \sum_{\loadindex \in \nDE} (\veleload_{\periodindex,\scenarioindex,\timeindex,\loadindex} - \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex})  \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex, \busindex \in \nBE
   \end{aligned}

Hydrogen Balance
~~~~~~~~~~~~~~~~
Similarly, ``eHydBalance`` ensures the conservation of energy for the hydrogen network.

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGH} \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nEH} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\genindex \in \nGEH} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &- \sum_{(\busindexb,\circuitindex) \in \text{hout}_{\busindex}} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   + \sum_{(\busindexa,\circuitindex) \in \text{hin}_{\busindex}} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex} \\
   &+ \sum_{\traderindex \in \nRH} (\vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} - \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})
   = \sum_{\loadindex \in \nDH} (\vhydload_{\periodindex,\scenarioindex,\timeindex,\loadindex} - \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex})  \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex, \busindex \in \nBH
   \end{aligned}

2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Output and Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~
Constraints like ``eEleMaxOutput2ndBlock`` and ``eEleMaxESSCharge2ndBlock`` ensure that generators and storage units operate within their rated power capacities. For a dispatchable generator, the output is limited by its capacity and commitment status.

*   **Max Output (Dispatchable Generator):** ``eEleMaxOutput2ndBlock``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}-\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \le \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vshutdownbin_{\periodindex,\scenarioindex,\timeindex+1,\genindex}



*   **Max Charge (Storage):** ``eEleMaxESSCharge2ndBlock``

    .. math::
       \frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}-\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}

Ramping Limits
~~~~~~~~~~~~~~
A series of constraints limit how quickly the output or charging rate of an asset can change. For example, ``eEleMaxRampUpOutput`` restricts the increase in a generator's output between consecutive timesteps.

*   **Ramp-Up:** ``eEleMaxRampUpOutput``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} - \veleproduction_{\periodindex,\scenarioindex,\timeindex-1,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \cdot \prampuprate_{\genindex}} \le \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

*   **Ramp-Down:** ``eEleMaxRampDwOutput``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex-1,\genindex} - \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \cdot \prampdwrate_{\genindex}} \ge -\vcommitbin_{\periodindex,\scenarioindex,\timeindex-1,\genindex} + \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

*   **Commitment State Change:** ``eEleCommitmentStartupShutdown`` links the commitment status of a unit (:math:`\vcommitbin`) to its start-up (:math:`\vstartupbin`) and shut-down (:math:`\vshutdownbin`) decisions.

    .. math::
       \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vcommitbin_{\periodindex,\scenarioindex,\timeindex-1,\genindex} = \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

*   **Minimum Up/Down Time:** ``eEleMinUpTime`` and ``eEleMinDownTime`` enforce that once a unit is turned on (or off), it must remain in that state for a minimum number of hours.

    *   ``eEleMinUpTime``:

        .. math::
           \sum_{\timeindex '=\timeindex-\puptime_{\genindex}}^{\timeindex} \vstartupbin_{\periodindex,\scenarioindex,\timeindex ',\genindex} \le \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

    *   ``eEleMinDownTime``:

        .. math::
           \sum_{\timeindex '=\timeindex-\pdwtime_{\genindex}}^{\timeindex} \vshutdownbin_{\periodindex,\scenarioindex,\timeindex ',\genindex} \le 1 - \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

3. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

State-of-Charge Balance
~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equation, ``eEleInventory`` for electricity and ``eHydInventory`` for hydrogen, tracks the stored energy level over time.

.. math::
   \begin{aligned}
   \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} = &\veleinventory_{\periodindex,\scenarioindex,\timeindex-1,\storageindex} \\
   &+ \ptimestepduration \cdot (\eta_{\text{charge}} \cdot \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \frac{1}{\eta_{\text{discharge}}} \cdot \veleproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \\
   &+ \ptimestepduration \cdot (\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}) - \velespillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \end{aligned}

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``eIncompatibilityEleChargeOutflows`` and related constraints prevent a storage unit from charging and discharging in the same timestep, using a binary variable (:math:`\velestoroperatbin`).

*   ``eEleChargingDecision``:

    .. math::
       \frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\storageindex}} \le \velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}

*   ``eEleDischargingDecision``:

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\storageindex}} \le 1 - \velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}

4. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

DC Power Flow
~~~~~~~~~~~~~
For the electricity grid, ``eKirchhoff2ndLaw`` implements a DC power flow model, relating the power flow on a line to the voltage angles at its connecting nodes.

.. math::
   \frac{\veleflow_{\periodindex,\scenarioindex,\timeindex,\text{ni,nf,cc}}}{\text{TTC}_{\text{ni,nf,cc}}} - \frac{\theta_{\periodindex,\scenarioindex,\timeindex,\text{ni}} - \theta_{\periodindex,\scenarioindex,\timeindex,\text{nf}}}{\text{X}_{\text{ni,nf,cc}} \cdot \text{TTC}_{\text{ni,nf,cc}}} \cdot 0.1 = 0

Flow Limits
~~~~~~~~~~~
The ``vEleNetFlow`` and ``vHydNetFlow`` variables are bounded by the thermal or physical capacity of the lines and pipelines. This is typically implemented as a variable bound.

5. Market and Commercial Constraints
------------------------------------
These constraints model the rules for interacting with external markets.

*   ``eEleRetMaxBuy`` / ``eEleRetMaxSell``: Limit the amount of energy that can be bought from or sold to the market.

    .. math::
       \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pelemaxmarketbuy_{\traderindex}

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints starting with ``eElePeak...`` identify the highest power peak within a billing period for tariff calculations. ``eElePeakHourValue`` uses binary variables to select the peak consumption hour.

.. math::
   \velepeakdemand_{\periodindex,\scenarioindex,\text{m,er,peak}} \ge \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} - 100 \cdot \sum_{\text{peak'} < \text{peak}} \velepeakdemandindbin_{\periodindex,\scenarioindex,\timeindex,\text{er,peak'}}


Reserve Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Frequency containment reserves in normal operation (FCR-N)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-N is modeled through the next constraint, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{neg} rp^{FN}_{neg} + \sum_{nes} rc^{FN}_{nes} \leq R^{FN}_{n} \quad \forall n`

Frequency containment reserves in disturbed operation (FCR-D)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-D is modeled through the upward and downward reserve constraints, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{neg} up^{FD}_{neg} + \sum_{nes} uc^{FD}_{nes} \leq UR^{FD}_{n} \quad \forall n`

:math:`\sum_{neg} dp^{FD}_{neg} + \sum_{nes} dc^{FD}_{nes} \leq DR^{FD}_{n} \quad \forall n`

Operating reserves from energy storage systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Operating reserves from ESS can only be if enought energy is available for discharging

:math:`RA^{FN}_{n}rp^{FN}_{nes} + URA^{FD}_{n}up^{FD}_{nes} \leq \frac{                      esi_{nes}}{DUR_{n}} \quad \forall nes`

:math:`RA^{FN}_{n}rp^{FN}_{nes} + DRA^{FD}_{n}dp^{FD}_{nes} \leq \frac{\overline{EI}_{nes} - esi_{nes}}{DUR_{n}} \quad \forall nes`

or for charging

:math:`RA^{FN}_{n}rc^{FN}_{nes} + URA^{FD}_{n}uc^{FD}_{nes} \leq \frac{\overline{EI}_{nes} - esi_{nes}}{DUR_{n}} \quad \forall nes`

:math:`RA^{FN}_{n}rc^{FN}_{nes} + DRA^{FD}_{n}dc^{FD}_{nes} \leq \frac{                      esi_{nes}}{DUR_{n}} \quad \forall nes`

6. Demand-Side and Reliability Constraints
------------------------------------------
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

7. Electric Vehicle (EV) Modeling
---------------------------------
Electric vehicles are modeled as a special class of mobile energy storage, identified by the ``model.egv`` set (a subset of ``model.egs``). They are subject to standard storage dynamics but with unique constraints and economic drivers that reflect their dual role as both a transportation tool and a potential grid asset.

**Key Modeling Concepts:**

*   **Fixed Nodal Connection**: Each EV is assumed to have a fixed charging point at a specific node (``nd``). All its interactions with the grid (charging and vehicle-to-grid discharging) occur at this single location. This means the EV's charging load (``vEleTotalCharge``) is directly added to the demand side of that node's ``eEleBalance`` constraint, while any discharging (``vEleTotalOutput``) is added to the supply side.

*   **Minimum Starting Charge**: The ``eEleMinEnergyStartUp`` constraint enforces a realistic user behavior: an EV must have a minimum state of charge *before* it can be considered "available" to leave its charging station (i.e., before its availability for grid services can change). This ensures the model doesn't fully drain the battery for grid purposes if the user needs it for a trip.

    .. math::
       \vinventory_{\periodindex,\scenarioindex,\timeindex-1,\text{ev}} \ge 0.8 \cdot \peleesscapacity_{\text{ev}} \quad (\text{if starting trip})

*   **Driving Consumption (``vEleEnergyOutflows``)**: The energy used for driving is modeled as an outflow from the battery. This can be configured in two ways, offering modeling flexibility:

    *   **Fixed Consumption**: By setting the upper and lower bounds of the outflow to the same value in the input data (e.g., ``pEleMinOutflows`` and ``pEleMaxOutflows``), driving patterns can be treated as a fixed, pre-defined schedule. This is useful for modeling commuters with predictable travel needs.
    *   **Variable Consumption**: Setting different upper and lower bounds allows the model to optimize the driving schedule. This can represent flexible travel plans, uncertain trip lengths, or scenarios where the timing of a trip is part of the optimization problem.

*   **Economic-Driven Charging (Tariff Response)**: The model does not use direct constraints to force EV charging at specific times. Instead, charging behavior is an *emergent property* driven by the objective to minimize total costs. This optimization is influenced by two main types of tariffs:

    *   **Volumetric Tariffs**: The total cost of purchasing energy from the grid (``vTotalEleTradeCost``) includes not just the wholesale energy price but also volumetric network fees (e.g., ``pEleRetnetavgift``). This means the model is incentivized to charge when the *all-in price per MWh* is lowest.
    *   **Capacity Tariffs**: The ``vTotalElePeakCost`` component of the objective function penalizes high monthly power peaks from the grid.

    Since EV charging (``vEleTotalCharge``) increases the total load at a node, the model will naturally schedule it during hours when the combination of volumetric and potential capacity costs is lowest. This interaction between the nodal balance, the cost components, and the objective function creates an economically rational "smart charging" behavior.