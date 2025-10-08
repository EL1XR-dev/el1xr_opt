Constraints
===========

The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function within the `oM_ModelFormulation.py` module, enforce everything from the laws of physics to the operational limits of individual assets.

The constraints are grouped by their functional area within the model.

1. Market and Commercial Constraints
------------------------------------
These constraints model the rules and limits for interacting with external energy markets.

Maximum Market Buy/Sell
~~~~~~~~~~~~~~~~~~~~~~~
*   **eEleRetMaxBuy**: Limits the maximum electricity purchase from a retailer (`er`).
*   **eEleRetMaxSell**: Limits the maximum electricity sale to a retailer (`er`).

.. math::
   \vEleBuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} \le \pEleRetMaxBuy_{\text{er}}
   \quad \forall (\periodindex, \scenarioindex, \timeindex, \text{er}) \in \psner

.. math::
   \vEleSell_{\periodindex,\scenarioindex,\timeindex,\text{er}} \le \pEleRetMaxSell_{\text{er}}
   \quad \forall (\periodindex, \scenarioindex, \timeindex, \text{er}) \in \psner

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints identify the highest power peak within a billing period for tariff calculations.

*   **eElePeakHourValue**: Selects the peak consumption hour using binary variables.
*   **eElePeakHourInd_C1 & C2**: Linearization constraints for the peak indicator.
*   **eElePeakNumberMonths**: Ensures that only one peak is selected per month.

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

Upward operating reserve decision of an ESS when it is consuming and constrained by charging and discharging itself («``eReserveConsChargingDecision_Up``»)

:math:`\frac{uc^{SR}_{nes} + uc^{TR}_{nes}}{\overline{EC}_{nes}} \leq esf_{nes} \quad \forall nes`

Upward operating reserve decision of an ESS when it is producing and constrained by charging and discharging itself («``eReserveProdDischargingDecision_Up``»)

:math:`\frac{up^{SR}_{nes} + up^{TR}_{nes}}{\overline{EP}_{nes}} \leq esf_{nes} \quad \forall nes`

Downward operating reserve decision of an ESS when it is consuming and constrained by charging and discharging itself («``eReserveConsChargingDecision_Dw``»)

:math:`\frac{dc^{SR}_{nes} + dc^{TR}_{nes}}{\overline{EC}_{nes}} \leq 1 - esf_{nes} \quad \forall nes`

Downward operating reserve decision of an ESS when it is producing and constrained by charging and discharging itself («``eReserveProdDischargingDecision_Dw``»)

:math:`\frac{dp^{SR}_{nes} + dp^{TR}_{nes}}{\overline{EP}_{nes}} \leq 1 - esf_{nes} \quad \forall nes`

Energy stored for upward operating reserve in consecutive time steps when ESS is consuming («``eReserveConsUpConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (uc^{SR}_{nes} + uc^{TR}_{nes}) \leq \overline{EC}_{nes} - esi_{nes} \quad \forall nes`

Energy stored for downward operating reserve in consecutive time steps when ESS is consuming («``eReserveConsDwConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (dc^{SR}_{nes} + dc^{TR}_{nes}) \leq esi_{nes} - \underline{EC}_{nes} \quad \forall nes`

Energy stored for upward operating reserve in consecutive time steps when ESS is producing («``eReserveProdUpConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (up^{SR}_{nes} + up^{TR}_{nes}) \leq \overline{EP}_{nes} - esi_{nes} \quad \forall nes`

Energy stored for downward operating reserve in consecutive time steps when ESS is producing («``eReserveProdDwConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (dp^{SR}_{nes} + dp^{TR}_{nes}) \leq esi_{nes} - \underline{EP}_{nes} \quad \forall nes`


2. Demand-Side Management and Reliability
-----------------------------------------
These constraints model the ability to shift electricity demand over time and ensure reliability of supply.

Flexible Demand Balance
~~~~~~~~~~~~~~~~~~~~~~~
*   **eEleDemandShifted**: The actual demand is defined as the original demand profile plus any flexible adjustments.
    .. math::
       vEleDemand_{p,s,t,ed} = pVarMaxDemand_{ed,p,s,t} + vEleDemFlex_{p,s,t,ed}
       \quad \forall (p,s,t,ed)

*   **eEleDemandShiftBalance**: This ensures that for a flexible load `ed`, the total energy consumed over a shifting window of `S_ed` steps is conserved. The constraint is applied at the end of each window.
    .. math::
       \sum_{t' = t - S_{ed} + 1}^{t} \vEleDemand_{p,s,t',ed} = \sum_{t' = t - S_{ed} + 1}^{t} \pVarMaxDemand_{ed,p,s,t'}
       \quad \forall (p,s,t,ed) \text{ if } t \pmod{S_{ed}} = 0

Unserved Energy
~~~~~~~~~~~~~~~
The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

Hydrogen Demand Cycle
~~~~~~~~~~~~~~~~~~~~~
*   **eHydDemandCycleTarget**: Ensures that the total hydrogen demand over a specific cycle is met.
    :math:`\sum_{n' = n-\frac{\tau_d}{\nu}}^n DUR_{n'} (hd_{n'nd} - HD_{n'nd}) = 0 \quad \forall nnd, n \in \rho_d`

3. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (:math:`\busindexa`) and at every timestep (:math:`\timeindex`), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
*   **eEleBalance**:
    :math:`\sum_{g\in nd} ep_{neg} - \sum_{es\in nd} ec_{nes} - \sum_{hz\in nd} (ec_{nhz} + ec^{StandBy}_{nhz}) - \sum_{hs\in nd} (ec^{Comp}_{nhs}) + ens_{nnd} + eb_{nnd} - es_{nnd} = ED_{nnd} + \sum_{jc} ef_{nndjc} - \sum_{jc} ef_{njndc} \quad \forall nnd`

Hydrogen Balance
~~~~~~~~~~~~~~~~
*   **eHydBalance**:
    :math:`\sum_{h\in nd} hp_{nhg} - \sum_{hs\in nd} hc_{nhs} - \sum_{g\in nd} hc_{net} + hns_{nnd} + hb_{nnd} - hs_{nnd} = HD_{nnd} + \sum_{jc} hf_{nndjc} - \sum_{jc} hf_{njndc} \quad \forall nnd`

4. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

Inventory  Balance (State-of-Charge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equation, ``eEleInventory`` for electricity and ``eHydInventory`` for hydrogen, tracks the stored energy level over time.

:math:`esi_{n-\frac{\tau_e}{\nu},es} + \sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (eei_{n'es} - eeo_{n'es} - ep_{n'es} + EF_{es} ec_{n'es}) = esi_{nes} + ess_{nes} \quad \forall nes`

:math:`hsi_{n-\frac{\tau_h}{\nu},hs} + \sum_{n' = n-\frac{\tau_h}{\nu}}^n DUR_{n'} (hei_{n'hs} - heo_{n'hs} - hp_{n'hs} + EF_{hs} hc_{n'hs}) = hsi_{nhs} + hss_{nhs} \quad \forall nhs`

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``eIncompatibilityEleChargeOutflows`` and related constraints prevent a storage unit from charging and discharging in the same timestep, using a binary variable (:math:`\velestoroperatbin`).

*   **Electricity Storage**:
    :math:`\frac{ec_{nes}}{\overline{EC}_{nes}} \leq esf_{nes} \quad \forall nes`
    :math:`\frac{ep_{nes}}{\overline{EP}_{nes}} \leq 1 - esf_{nes} \quad \forall nes`

*   **Hydrogen Storage**:
    :math:`\frac{hc_{nhs}}{\overline{HC}_{nhs}} \leq hsf_{nhs} \quad \forall nhs`
    :math:`\frac{hp_{nhs}}{\overline{HP}_{nhs}} \leq 1 - hsf_{nhs} \quad \forall nhs`

Maximum and Minimum Relative Inventory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*   **eMaxInventory2Comm / eMinInventory2Comm**: Constrains the inventory level by the unit's commitment decision.
    :math:`\frac{esi_{nes}}{\overline{EI}_{nes}}  \leq euc_{nes} \quad \forall nes`
    :math:`\frac{hsi_{nhs}}{\overline{HI}_{nhs}}  \leq huc_{nhs} \quad \forall nhs`

Energy Inflows & Outflows
~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints manage scheduled energy flows and link them to commitment status.
*   **eMaxInflows2Commitment / eMinInflows2Commitment**
*   **eMaxEleOutflows2Commitment / eMinEleOutflows2Commitment**
*   **eEleEnergyOutflows**: Ensures total outflows over a defined cycle meet a target.
    :math:`\sum_{n' = n-\frac{\tau_e}{\rho_e}}^n DUR_{n'} (eeo_{n'es} - EEO_{n'es}) = 0 \quad \forall nes, n \in \rho_e`

Incompatibility between Charge and Outflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*   **eIncompatibilityEleChargeOutflows**:
    :math:`\frac{eeo_{nes} + ec2b_{nes}}{\overline{EC}_{nes} - \underline{EC}_{nes}} \leq 1 \quad \forall nes`

5. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Total Output and Charge
~~~~~~~~~~~~~~~~~~~~~~~
These constraints define the total output or charge of a unit as the sum of its base (minimum) level and a dispatchable second block.
*   **eEleTotalOutput**:
    :math:`\frac{ep_{neg}}{\underline{EP}_{neg}} = euc_{neg} + \frac{ep2b_{neg} + URA^{SR}_{n}up^{SR}_{nes} + URA^{TR}_{n}up^{TR}_{nes} - DRA^{SR}_{n}dp^{SR}_{nes} - DRA^{TR}_{n}dp^{TR}_{nes}}{\underline{EP}_{neg}} \quad \forall neg`
*   **eEleTotalCharge**:
    :math:`\frac{ec_{nes}}{\underline{EC}_{nes}} = 1 + \frac{ec2b_{nes} - URA^{SR}_{n}uc^{SR}_{nes} - URA^{TR}_{n}uc^{TR}_{nes} + DRA^{SR}_{n}dc^{SR}_{nes} + DRA^{TR}_{n}dc^{TR}_{nes}}{\underline{EC}_{nes}} \quad \forall nes`

Energy Conversion
~~~~~~~~~~~~~~~~~
*   **eAllEnergy2Ele / eAllEnergy2Hyd**:
    :math:`ep_{neg} = PF_{he} hc_{neg} \quad \forall neg`
    :math:`hp_{nhz} \leq PF1_{ehk} +  PF2_{ehk} gc_{nhz} \quad \forall nhz`

Ramping Limits
~~~~~~~~~~~~~~
These constraints limit how quickly an asset's output or charging rate can change.
*   **eMaxRampUpEleOutput / eMaxRampDwEleOutput**:
    :math:`\frac{- ep2b_{n-\nu,g} - dp^{SR}_{n-\nu,g} - dp^{TR}_{n-\nu,g} + ep2b_{neg} + up^{SR}_{neg} + up^{TR}_{neg}}{DUR_n RU_g} \leq   euc_{neg}      - esu_{neg} \quad \forall neg`
    :math:`\frac{- ep2b_{n-\nu,g} + up^{SR}_{n-\nu,g} + up^{TR}_{n-\nu,g} + ep2b_{neg} - dp^{SR}_{neg} - dp^{TR}_{neg}}{DUR_n RD_g} \geq - euc_{n-\nu,g} + esd_{neg} \quad \forall neg`

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.
*   **eEleCommitmentStartupShutdown**:
    :math:`euc_{neg} - euc_{n-\nu,g} = esu_{neg} - esd_{neg} \quad \forall neg`
*   **eMinUpTimeEle / eMinDownTimeEle**:
    :math:`\sum_{n'=n+\nu-TU_t}^n esu_{n't} \leq     euc_{net} \quad \forall net`
    :math:`\sum_{n'=n+\nu-TD_t}^n esd_{n't} \leq 1 - euc_{net} \quad \forall net`

Second Block Output/Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints limit the output/charge of the dispatchable second block, tying it to the unit's commitment status.
*   **eMaxEleOutput2ndBlock / eMinEleOutput2ndBlock**:
    :math:`\frac{ep2b_{net} + up^{SR}_{net} + up^{TR}_{net}}{\overline{EP}_{net} - \underline{EP}_{net}} \leq euc_{net} \quad \forall net`
*   **eMaxEleESSCharge2ndBlock / eMinEleESSCharge2ndBlock**:
    :math:`\frac{ec2b_{nes} + dc^{SR}_{nes} + dc^{TR}_{nes}}{\overline{EC}_{nes} - \underline{EC}_{nes}} \leq 1 \quad \forall nes`

6. Electric Vehicle (EV) Modeling
---------------------------------
*   **eEleMinEnergyStartUp**: Ensures an EV has a minimum state of charge before a trip.
    .. math::
       \vinventory_{\periodindex,\scenarioindex,\timeindex-1,\text{ev}} \ge 0.8 \cdot \peleesscapacity_{\text{ev}} \quad (\text{if starting trip})

7. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

DC Power Flow
~~~~~~~~~~~~~
*   **eKirchhoff2ndLaw**: Implements a DC power flow model.
    .. math::
       \frac{\veleflow_{\dots,\text{ni,nf,cc}}}{\text{TTC}_{\text{ni,nf,cc}}} - \frac{\theta_{\dots,\text{ni}} - \theta_{\dots,\text{nf}}}{\text{X}_{\text{ni,nf,cc}} \cdot \text{TTC}_{\text{ni,nf,cc}}} \cdot 0.1 = 0

8. Bounds on Variables
-----------------------
To ensure numerical stability and solver efficiency, explicit bounds are placed on all decision variables.

:math:`0 \leq ep_{neg} \leq \overline{EP}_{neg}`
:math:`0 \leq hp_{nhg} \leq \overline{HP}_{nhg}`
:math:`0 \leq ec_{nes} \leq \overline{EC}_{nes}`
:math:`0 \leq ec_{nhz} \leq \overline{EC}_{nhz}`
:math:`0 \leq hc_{nhs} \leq \overline{HC}_{nhs}`
:math:`0 \leq hc_{net} \leq \overline{HC}_{net}`
:math:`0 \leq ep2b_{neg} \leq \overline{EP}_{neg} - \underline{EP}_{neg}`
:math:`0 \leq hp2b_{nhg} \leq \overline{HP}_{nhg} - \underline{HP}_{nhg}`
:math:`0 \leq eeo_{nes} \leq \max(\overline{EP}_{nes},\overline{EC}_{nes})`
:math:`0 \leq heo_{nhs} \leq \max(\overline{HP}_{nhs},\overline{HC}_{nhs})`
:math:`0 \leq up^{SR}_{neg}, dp^{SR}_{neg} \leq \overline{EP}_{neg} - \underline{EP}_{neg}`
:math:`0 \leq up^{TR}_{neg}, dp^{TR}_{neg} \leq \overline{EP}_{neg} - \underline{EP}_{neg}`
:math:`0 \leq uc^{SR}_{nes}, dc^{SR}_{nes} \leq \overline{EC}_{nes} - \underline{EC}_{nes}`
:math:`0 \leq uc^{TR}_{nes}, dc^{TR}_{nes} \leq \overline{EC}_{nes} - \underline{EC}_{nes}`
:math:`0 \leq ec2b_{nes} \leq \overline{EC}_{nes}`
:math:`0 \leq hc2b_{nhs} \leq \overline{HC}_{nhs}`
:math:`\underline{EI}_{nes} \leq  esi_{nes}  \leq \overline{EI}_{nes}`
:math:`\underline{HI}_{nhs} \leq  hsi_{nhs}  \leq \overline{HI}_{nhs}`
:math:`0 \leq  ess_{nes}`
:math:`0 \leq  hss_{nhs}`
:math:`0 \leq ec^{R+}_{nes}, ec^{R-}_{nes} \leq \overline{EC}_{nes}`
:math:`0 \leq ec^{R+}_{nhz}, ec^{R-}_{nhz} \leq \overline{EC}_{nhz}`
:math:`0 \leq ec^{Comp}_{nhs} \leq \overline{EC}_{nhs}`
:math:`0 \leq ec^{StandBy}_{nhz} \leq \overline{EC}_{nhz}`
:math:`-\overline{ENF}_{nijc} \leq  ef_{nij}  \leq \overline{ENF}_{nijc}`
:math:`-\overline{HNF}_{nijc} \leq  hf_{nij}  \leq \overline{HNF}_{nijc}`