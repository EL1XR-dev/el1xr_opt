Constraints
===========

The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function within the `oM_ModelFormulation.py` module, enforce everything from the laws of physics to the operational limits of individual assets.

The constraints are grouped by their functional area within the model.

1. Market and Commercial Constraints
------------------------------------
These constraints model the rules and limits for interacting with external energy markets.

Maximum Market Buy/Sell
~~~~~~~~~~~~~~~~~~~~~~~
These constraints limit the amount of electricity that can be bought from or sold to the market at any given time, based on predefined limits for each electricity retailer (`er`).

*   **eEleRetMaxBuy**:
    .. math::
       \vEleBuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} \le \pEleRetMaxBuy_{\text{er}}
       \quad \forall (\periodindex, \scenarioindex, \timeindex, \text{er}) \in \psner

*   **eEleRetMaxSell**:
    .. math::
       \vEleSell_{\periodindex,\scenarioindex,\timeindex,\text{er}} \le \pEleRetMaxSell_{\text{er}}
       \quad \forall (\periodindex, \scenarioindex, \timeindex, \text{er}) \in \psner

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints identify the highest power peak within a billing period (`m`) for tariff calculations. This is achieved using "big-M" linearizations.

*   **eElePeakHourValue**: This constraint, along with binary variables ``vElePeakHourInd``, identifies the grid purchase ``vEleBuy`` corresponding to the n-th peak.
*   **eElePeakNumberMonths**: Ensures that for each month and for each peak order (1st, 2nd, etc.), exactly one time step is chosen.

2. Demand-Side Management
-------------------------
These constraints model the ability to shift electricity demand over time for flexible loads.

Flexible Demand Balance
~~~~~~~~~~~~~~~~~~~~~~~
*   **eEleDemandShifted**: First, the actual demand is defined as the original demand profile plus any flexible adjustments.
    .. math::
       \vEleDemand_{p,s,t,ed} = \pVarMaxDemand_{ed,p,s,t} + \vEleDemFlex_{p,s,t,ed}
       \quad \forall (p,s,t,ed)

*   **eEleDemandShiftBalance**: This ensures that for a flexible load `ed`, the total energy consumed over a shifting window of `S_ed` steps is conserved. The constraint is applied at the end of each window.
    .. math::
       \sum_{t' = t - S_{ed} + 1}^{t} \vEleDemand_{p,s,t',ed} = \sum_{t' = t - S_{ed} + 1}^{t} \pVarMaxDemand_{ed,p,s,t'}
       \quad \forall (p,s,t,ed) \text{ if } t \pmod{S_{ed}} = 0

3. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (`nd`) and at every timestep (`t`), energy supply equals energy demand.

*   **eEleBalance**: Enforces the electricity balance at each node.
*   **eHydBalance**: Enforces the hydrogen balance at each node.

**Electricity Balance (`eEleBalance`)**
.. math::
   \sum_{eg \in \text{n2eg}} \vEleTotalOutput_{p,s,t,eg}
   - \sum_{egs \in \text{n2eg}} \vEleTotalCharge_{p,s,t,egs}
   - \sum_{e2h \in \text{n2hg}} \vEleTotalCharge_{p,s,t,e2h}
   + \sum_{er \in \text{n2er}} (\vEleBuy_{p,s,t,er} - \vEleSell_{p,s,t,er})
   + \sum_{(ni,cc) \in \text{lin}} \vEleNetFlow_{p,s,t,ni,nd,cc}
   - \sum_{(nf,cc) \in \text{lout}} \vEleNetFlow_{p,s,t,nd,nf,cc}
   = \sum_{ed \in \text{n2ed}} (\vEleDemand_{p,s,t,ed} - \vENS_{p,s,t,ed})
   \quad \forall (p,s,t,nd)

**Hydrogen Balance (`eHydBalance`)**
.. math::
   \sum_{hg \in \text{n2hg}} \vHydTotalOutput_{p,s,t,hg}
   - \sum_{hgs \in \text{n2hg}} \vHydTotalCharge_{p,s,t,hgs}
   - \sum_{h2e \in \text{n2g}} \vHydTotalCharge_{p,s,t,h2e}
   + \sum_{hr \in \text{n2hr}} (\vHydBuy_{p,s,t,hr} - \vHydSell_{p,s,t,hr})
   + \sum_{(ni,cc) \in \text{hin}} \vHydNetFlow_{p,s,t,ni,nd,cc}
   - \sum_{(nf,cc) \in \text{hout}} \vHydNetFlow_{p,s,t,nd,nf,cc}
   = \sum_{hd \in \text{n2hd}} (\vHydDemand_{p,s,t,hd} - \vHNS_{p,s,t,hd})
   \quad \forall (p,s,t,nd)

4. Energy Storage Systems (ESS)
-------------------------------
These constraints model the detailed behavior of energy storage units.

ESS Inventory Balance (State-of-Charge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equations track the stored energy level over a cycle of `C_egs` timesteps.

*   **eEleInventory**: For `t > C_egs`, the inventory is the previous cycle's inventory plus the net energy change. For the first cycle (`t = C_egs`), it starts from `pEleInitialInventory`.
    .. math::
       \vEleInventory_{p,s,t,egs} = \vEleInventory_{p,s,t-C_{egs},egs} + \sum_{t'=t-C_{egs}+1}^{t} \pDuration_{p,s,t'} \cdot \left( \vEleEnergyInflows_{\dots,t'} - \vEleEnergyOutflows_{\dots,t'} - \frac{\vEleTotalOutput_{\dots,t'}}{\pEleGenEfficiency_{discharge}} + \pEleGenEfficiency_{charge} \cdot \vEleTotalCharge_{\dots,t'} \right) - \vEleSpillage_{p,s,t,egs}

*   **eHydInventory**: A similar formulation applies to hydrogen storage.

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints prevent a storage unit from charging and discharging in the same timestep using a binary variable `vEleStorOperat`.

*   **eEleChargingDecision**: Allows charging only if the binary is 1.
    .. math::
       \frac{\vEleTotalCharge_{\dots,egs}}{\pEleMaxCharge_{egs}} \le \vEleStorOperat_{\dots,egs} \quad \forall egs

*   **eEleDischargingDecision**: Allows discharging only if the binary is 0.
    .. math::
       \frac{\vEleTotalOutput_{\dots,egs}}{\pEleMaxPower_{egs}} \le 1 - \vEleStorOperat_{\dots,egs} \quad \forall egs

*   **eIncompatibilityEleChargeOutflows**: Prevents simultaneous scheduled outflows and charging.

5. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Total Output and Charge
~~~~~~~~~~~~~~~~~~~~~~~
These constraints define the total output or charge of a unit. The formulation depends on the unit type and its minimum power/charge level (`pMin`).

*   **eEleTotalOutput**: For a unit `egnr` (non-renewable generator):
    - If `pMin = 0`: :math:`\vEleTotalOutput = \vEleTotalOutput2ndBlock`
    - If `pMin > 0` and is a generator: :math:`\vEleTotalOutput = \pEleMinPower \cdot \vEleGenCommitment + \vEleTotalOutput2ndBlock`
    - If `pMin > 0` and is storage: :math:`\vEleTotalOutput = \pEleMinPower \cdot \pVarFixedAvailability + \vEleTotalOutput2ndBlock`

*   **eEleTotalCharge**: A similar logic applies to the total charge for storage and electrolyzers.

Energy Conversion
~~~~~~~~~~~~~~~~~
*   **eAllEnergy2Hyd**: Models electricity-to-hydrogen conversion (electrolyzers).
    .. math::
       \vHydTotalOutput_{p,s,t,e2h} = \frac{\vEleTotalCharge_{p,s,t,e2h}}{\pEleGenProductionFunction_{e2h}} \quad \forall (p,s,t,e2h)

*   **eAllEnergy2Ele**: Models hydrogen-to-electricity conversion (fuel cells).
    .. math::
       \vEleTotalOutput_{p,s,t,h2e} = \vHydTotalCharge_{p,s,t,h2e} \cdot \pEleGenProductionFunction_{h2e} \quad \forall (p,s,t,h2e)

Ramping Limits
~~~~~~~~~~~~~~
These constraints limit how quickly the output or charging rate of an asset can change. The formulation shown is for a generic generator; similar forms exist for charge, discharge, and hydrogen units.

*   **eEleMaxRampUpOutput / eEleMaxRampDwOutput**:
    .. math::
       \vEleTotalOutput2ndBlock_{t} - \vEleTotalOutput2ndBlock_{t-1} \le \pDuration_t \cdot \pEleGenRampUp \cdot (\vEleGenCommitment_{t} - \vEleGenStartUp_{t})

    This relationship is adjusted for the first timestep to use an initial output parameter.

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

*   **eEleCommitmentStartupShutdown**: Links the binary commitment, startup, and shutdown variables. For `t > 1`:
    .. math::
       \vEleGenCommitment_{t} - \vEleGenCommitment_{t-1} = \vEleGenStartUp_{t} - \vEleGenShutDown_{t}
    For `t=1`, `vEleGenCommitment_{t-1}` is replaced by the initial parameter `pEleInitialUC`.

*   **eEleMinUpTime / eEleMinDownTime**: Enforce minimum up and down times. The simplified formulation is:
    .. math::
       \sum_{t' = t - \text{MUT} + 1}^{t} \vEleGenStartUp_{t'} \le \vEleGenCommitment_{t}
    The actual implementation contains more complex indexing to correctly handle initial conditions at the beginning of the simulation horizon.

6. Electric Vehicle (EV) Modeling
---------------------------------
*   **eEleMinEnergyStartUp**: Enforces a minimum SoC before a trip can start. A trip is indicated by the parameter `pVarStartUp` changing from 0 to 1.
    .. math::
       \vEleInventory_{p,s,t-1,ev} \ge 0.8 \cdot \pEleMaxStorage_{ev} \quad \text{if trip starts at t}

*   **eEleTotalMaxChargeConditioned**: Limits the maximum charge based on a fixed availability profile `pVarFixedAvailability`.

7. Network Constraints
----------------------
These constraints model the physics and limits of the electricity grid.

DC Power Flow
~~~~~~~~~~~~~
*   **eKirchhoff2ndLaw**: Implements the DC power flow equation for an AC line.
    .. math::
       \vEleNetFlow_{p,s,t,ni,nf,cc} \cdot \frac{1}{\text{TTC}} - (\vEleNetTheta_{p,s,t,ni} - \vEleNetTheta_{p,s,t,nf}) \cdot \frac{0.1}{\text{X} \cdot \text{TTC}} = 0

8. Bounds on Variables
-----------------------
While not explicitly formulated as constraints here, all decision variables are subject to upper and lower bounds defined during their declaration. These are crucial for ensuring model stability and reflecting physical asset limits. Examples include:

:math:`0 \le \vEleTotalOutput_{\dots,eg} \le \pEleMaxPower_{eg}`
:math:`\pEleMinStorage_{egs} \le \vEleInventory_{\dots,egs} \le \pEleMaxStorage_{egs}`