Constraints
===========
The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

1. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (``nd``) and at every timestep (``p,sc,n``), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
The core electricity balance equation, ``eEleBalance``, states that the sum of all power generated and imported must equal the sum of all power consumed and exported.

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGE} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nSE} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\text{e2h} \in \text{E2H}} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\text{e2h}} \\
   &- \sum_{\text{nf,cc} \in \text{lout}} \veleflow_{\periodindex,\scenarioindex,\timeindex,\text{nd,nf,cc}}
   + \sum_{\text{ni,cc} \in \text{lin}} \veleflow_{\periodindex,\scenarioindex,\timeindex,\text{ni,nd,cc}} \\
   &+ \sum_{\traderindex \in \nRE} (\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} - \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})
   = \sum_{\loadindex \in \nDE} (\peledem_{\periodindex,\scenarioindex,\timeindex,\loadindex} - \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex})
   \end{aligned}

Hydrogen Balance
~~~~~~~~~~~~~~~~
Similarly, ``eHydBalance`` ensures the conservation of energy for the hydrogen network.

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGH} \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nSH} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\text{h2e} \in \text{H2E}} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\text{h2e}} \\
   &- \sum_{\text{nf,cc} \in \text{hout}} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\text{nd,nf,cc}}
   + \sum_{\text{ni,cc} \in \text{hin}} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\text{ni,nd,cc}} \\
   &+ \sum_{\traderindex \in \nRH} (\vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} - \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex})
   = \sum_{\loadindex \in \nDH} (\phydem_{\periodindex,\scenarioindex,\timeindex,\loadindex} - \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\loadindex})
   \end{aligned}

2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Output and Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~
Constraints like ``eEleMaxOutput2ndBlock`` and ``eEleMaxESSCharge2ndBlock`` ensure that generators and storage units operate within their rated power capacities. For a dispatchable generator, the output is limited by its capacity and commitment status.

*   **Max Output (Dispatchable Generator):** ``eEleMaxOutput2ndBlock``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pmaxpower_{\genindex}} \le \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vshutdownbin_{\periodindex,\scenarioindex,\timeindex+1,\genindex}

*   **Max Charge (Storage):** ``eEleMaxESSCharge2ndBlock``

    .. math::
       \frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pmaxcharge_{\storageindex}} \le \pavailability_{\storageindex}

Ramping Limits
~~~~~~~~~~~~~~
A series of constraints limit how quickly the output or charging rate of an asset can change. For example, ``eEleMaxRampUpOutput`` restricts the increase in a generator's output between consecutive timesteps.

*   **Ramp-Up:** ``eEleMaxRampUpOutput``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} - \veleproduction_{\periodindex,\scenarioindex,\timeindex-1,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \cdot \prampup_{\genindex}} \le \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

*   **Ramp-Down:** ``eEleMaxRampDwOutput``

    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex-1,\genindex} - \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \cdot \prampdown_{\genindex}} \ge -\vcommitbin_{\periodindex,\scenarioindex,\timeindex-1,\genindex} + \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

*   **Commitment State Change:** ``eEleCommitmentStartupShutdown`` links the commitment status of a unit (:math:`\vcommitbin`) to its start-up (:math:`\vstartupbin`) and shut-down (:math:`\vshutdownbin`) decisions.

    .. math::
       \vcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vcommitbin_{\periodindex,\scenarioindex,\timeindex-1,\genindex} = \vstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}

*   **Minimum Up/Down Time:** ``eEleMinUpTime`` and ``eEleMinDownTime`` enforce that once a unit is turned on (or off), it must remain in that state for a minimum number of hours.

    *   ``eEleMinUpTime``:
        .. math::
           \sum_{t'=t-\text{min\_up\_time}}^{t} \vstartupbin_{\periodindex,\scenarioindex,t',\genindex} \le \vcommitbin_{\periodindex,\scenarioindex,t,\genindex}
    *   ``eEleMinDownTime``:
        .. math::
           \sum_{t'=t-\text{min\_down\_time}}^{t} \vshutdownbin_{\periodindex,\scenarioindex,t',\genindex} \le 1 - \vcommitbin_{\periodindex,\scenarioindex,t,\genindex}

3. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

State-of-Charge Balance
~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equation, ``eEleInventory`` for electricity and ``eHydInventory`` for hydrogen, tracks the stored energy level over time.

.. math::
   \begin{aligned}
   \vinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} = &\vinventory_{\periodindex,\scenarioindex,\timeindex-1,\storageindex} \\
   &+ \ptimestepduration \cdot (\eta_{\text{charge}} \cdot \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \frac{1}{\eta_{\text{discharge}}} \cdot \veleproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \\
   &+ \ptimestepduration \cdot (\vinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \voutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}) - \vspillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \end{aligned}

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``eIncompatibilityEleChargeOutflows`` and related constraints prevent a storage unit from charging and discharging in the same timestep, using a binary variable (:math:`\vstoroperatbin`).

*   ``eEleChargingDecision``:
    .. math::
       \frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pmaxcharge_{\storageindex}} \le \vstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}

*   ``eEleDischargingDecision``:
    .. math::
       \frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pmaxpower_{\storageindex}} \le 1 - \vstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}

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
       \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pmaxbuy_{\traderindex}

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints starting with ``eElePeak...`` identify the highest power peak within a billing period for tariff calculations. ``eElePeakHourValue`` uses binary variables to select the peak consumption hour.

.. math::
   \velepeak_{\periodindex,\scenarioindex,\text{m,er,peak}} \ge \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} - 100 \cdot \sum_{\text{peak'} < \text{peak}} \vpeakindicatorbin_{\periodindex,\scenarioindex,\timeindex,\text{er,peak'}}

6. Demand-Side and Reliability Constraints
------------------------------------------
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

7. Electric Vehicle (EV) Modeling
---------------------------------
EVs are modeled as a special class of mobile energy storage with unique constraints.

*   **Minimum Starting Charge**: The ``eEleMinEnergyStartUp`` constraint enforces that an EV must have a minimum state of charge before it can be used for driving.

    .. math::
       \vinventory_{\periodindex,\scenarioindex,\timeindex-1,\text{ev}} \ge 0.8 \cdot \pmaxstorage_{\text{ev}} \quad (\text{if starting trip})

*   **Driving Consumption**: The energy used for driving is modeled as an outflow, ``vEleEnergyOutflows``, which can be fixed or variable depending on the input data.

*   **Economically-Driven Charging**: Charging behavior is an emergent property driven by the objective to minimize costs, influenced by both volumetric (per MWh) and capacity (per MW peak) tariffs. There are no hard constraints forcing charging at specific times.