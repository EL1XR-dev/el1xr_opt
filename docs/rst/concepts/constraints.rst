Constraints
===========
The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

1. Market and Commercial Constraints
------------------------------------
These constraints model the rules for interacting with external markets.

Day-ahead Electricity Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Participation in the day-ahead electricity market is modeled through the next constraints, which ensure that the amount of energy bought from or sold to the market does not exceed predefined limits for each time step and retailer.

Eletricity bought from the market if :math:`\pelemaxmarketbuy_{\traderindex} >= 0.0` («``eEleRetMaxBuy``»)

:math:`\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pelemaxmarketbuy_{\traderindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\traderindex`

Eletricity sold to the market if :math:`\pelemaxmarketsell_{\traderindex} >= 0.0` («``eEleRetMaxSell``»)

:math:`\velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pelemaxmarketsell_{\traderindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\traderindex`

Reserve Electricity Market Participation (to be implemented)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Frequency containment reserves in normal operation (FCR-N)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-N is modeled through the next constraint, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{neg} rp^{FN}_{neg} + \sum_{nes} rc^{FN}_{nes} \leq R^{FN}_{n} \quad \forall n`

Frequency containment reserves in disturbed operation (FCR-D)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-D is modeled through the upward and downward reserve constraints, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{neg} up^{FD}_{neg} + \sum_{nes} uc^{FD}_{nes} \leq UR^{FD}_{n} \quad \forall n`

:math:`\sum_{neg} dp^{FD}_{neg} + \sum_{nes} dc^{FD}_{nes} \leq DR^{FD}_{n} \quad \forall n`

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints starting with ``eElePeak...`` identify the highest power peak within a billing period for tariff calculations. ``eElePeakHourValue`` uses binary variables to select the peak consumption hour.

.. math::
   \velepeakdemand_{\periodindex,\scenarioindex,\text{m,er,peak}} \ge \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} - 100 \cdot \sum_{\text{peak'} < \text{peak}} \velepeakdemandindbin_{\periodindex,\scenarioindex,\timeindex,\text{er,peak'}}

2. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (:math:`\busindexa`) and at every timestep (:math:`\timeindex`), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
Electricity balance of generation and demand («``eElectricityBalance``»)

:math:`\sum_{g\in nd} ep_{neg} - \sum_{es\in nd} ec_{nes} - \sum_{hz\in nd} (ec_{nhz} + ec^{StandBy}_{nhz}) - \sum_{hs\in nd} (ec^{Comp}_{nhs}) + ens_{nnd} + eb_{nnd} - es_{nnd} = ED_{nnd} + \sum_{jc} ef_{nndjc} - \sum_{jc} ef_{njndc} \quad \forall nnd`

Hydrogen Balance
~~~~~~~~~~~~~~~~
Hydrogen balance of generation and demand («``eHydrogenBalance``»)

:math:`\sum_{h\in nd} hp_{nhg} - \sum_{hs\in nd} hc_{nhs} - \sum_{g\in nd} hc_{net} + hns_{nnd} + hb_{nnd} - hs_{nnd} = HD_{nnd} + \sum_{jc} hf_{nndjc} - \sum_{jc} hf_{njndc} \quad \forall nnd`


2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Output and Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~
Total generation of an electricity unit (all except the VRE units) («``eEleTotalOutput``»)

:math:`\frac{ep_{neg}}{\underline{EP}_{neg}} = euc_{neg} + \frac{ep2b_{neg} + URA^{SR}_{n}up^{SR}_{nes} + URA^{TR}_{n}up^{TR}_{nes} - DRA^{SR}_{n}dp^{SR}_{nes} - DRA^{TR}_{n}dp^{TR}_{nes}}{\underline{EP}_{neg}} \quad \forall neg`

Total generation of a hydrogen unit («``eHydTotalOutput``»)

:math:`\frac{hp_{nhg}}{\underline{HP}_{nhg}} = huc_{nhg} + \frac{hp2b_{nhz}}{\underline{HP}_{nhg}} \quad \forall nh`

Total charge of an electricity ESS («``eEleTotalCharge``»)

:math:`\frac{ec_{nes}}{\underline{EC}_{nes}} = 1 + \frac{ec2b_{nes} - URA^{SR}_{n}uc^{SR}_{nes} - URA^{TR}_{n}uc^{TR}_{nes} + DRA^{SR}_{n}dc^{SR}_{nes} + DRA^{TR}_{n}dc^{TR}_{nes}}{\underline{EC}_{nes}} \quad \forall nes`

Total charge of a hydrogen unit («``eHydTotalCharge``»)

:math:`\frac{hc_{nhs}}{\underline{HC}_{nhs}} = 1 + \frac{hc2b_{nhs}}{\underline{EC}_{nhs}} \quad \forall nhs`

Energy Conversion
~~~~~~~~~~~~~~~~~
Energy conversion from energy from electricity to hydrogen and vice versa («``eAllEnergy2Ele``, ``eAllEnergy2Hyd``»)

:math:`ep_{neg} = PF_{he} hc_{neg} \quad \forall neg`

:math:`hp_{nhz} \leq PF1_{ehk} +  PF2_{ehk} gc_{nhz} \quad \forall nhz`

Ramping Limits
~~~~~~~~~~~~~~
A series of constraints limit how quickly the output or charging rate of an asset can change. For example, ``eEleMaxRampUpOutput`` restricts the increase in a generator's output between consecutive timesteps.

Maximum ramp up and ramp down for the second block of a non-renewable (thermal, hydro) electricity unit («``eMaxRampUpEleOutput``, ``eMaxRampDwEleOutput``»)

* P. Damcı-Kurt, S. Küçükyavuz, D. Rajan, and A. Atamtürk, “A polyhedral study of production ramping,” Math. Program., vol. 158, no. 1–2, pp. 175–205, Jul. 2016. `10.1007/s10107-015-0919-9 <https://doi.org/10.1007/s10107-015-0919-9>`_

:math:`\frac{- ep2b_{n-\nu,g} - dp^{SR}_{n-\nu,g} - dp^{TR}_{n-\nu,g} + ep2b_{neg} + up^{SR}_{neg} + up^{TR}_{neg}}{DUR_n RU_g} \leq   euc_{neg}      - esu_{neg} \quad \forall neg`

:math:`\frac{- ep2b_{n-\nu,g} + up^{SR}_{n-\nu,g} + up^{TR}_{n-\nu,g} + ep2b_{neg} - dp^{SR}_{neg} - dp^{TR}_{neg}}{DUR_n RD_g} \geq - euc_{n-\nu,g} + esd_{neg} \quad \forall neg`

Maximum ramp down and ramp up for the charge of an electricity ESS («``eMaxRampUpEleCharge``, ``eMaxRampDwEleCharge``»)

:math:`\frac{- ec2b_{n-\nu,es} + dc^{SR}_{n-\nu,es} + dc^{TR}_{n-\nu,es} + ec2b_{nes} - uc^{SR}_{nes} - uc^{TR}_{nes}}{DUR_n RU_es} \geq - 1 \quad \forall nes`

:math:`\frac{- ec2b_{n-\nu,es} - uc^{SR}_{n-\nu,es} - uc^{TR}_{n-\nu,es} + ec2b_{nes} + dc^{SR}_{nes} + dc^{TR}_{nes}}{DUR_n RD_es} \leq   1 \quad \forall nes`

Maximum ramp up and ramp down for the  second block of a hydrogen unit («``eMaxRampUpHydOutput``, ``eMaxRampDwHydOutput``»)

:math:`\frac{- hp2b_{n-\nu,hg} + hp2b_{nhg}}{DUR_n RU_hg} \leq   huc_{nhg}      - hsu_{nhg} \quad \forall nhg`

:math:`\frac{- hp2b_{n-\nu,hg} + hp2b_{nhg}}{DUR_n RD_hg} \geq - huc_{n-\nu,hg} + hsd_{nhg} \quad \forall nhg`

Maximum ramp down and ramp up for the charge of a hydrogen ESS («``eMaxRampUpHydCharge``, ``eMaxRampDwHydCharge``»)

:math:`\frac{- hc2b_{n-\nu,hs} + hc2b_{nhs}}{DUR_n RU_hs} \geq - 1 \quad \forall nhs`

:math:`\frac{- hc2b_{n-\nu,hs} + hc2b_{nhs}}{DUR_n RD_hs} \leq   1 \quad \forall nhs`

Maximum ramp up and ramp down for the outflows of a hydrogen ESS («``eMaxRampUpHydOutflows``, ``eMaxRampDwHydOutflows``»)

:math:`\frac{- heo_{n-\nu,hs} + heo_{nhs}}{DUR_n RU_hs} \leq   1 \quad \forall nhs`

:math:`\frac{- heo_{n-\nu,hs} + heo_{nhs}}{DUR_n RD_hs} \geq - 1 \quad \forall nhs`

Ramp up and ramp down for the provision of demand to the hydrogen customers («``eMaxRampUpHydDemand``, ``eMaxRampDwHydDemand``»)

:math:`\frac{- hd_{n-\nu,nd} + hd_{nnd}}{DUR_n RU_nd} \leq   1 \quad \forall nnd`

:math:`\frac{- hd_{n-\nu,nd} + hd_{nnd}}{DUR_n RD_nd} \geq - 1 \quad \forall nnd`

Differences between electricity consumption of two consecutive hours [GW] («``eEleConsumptionDiff``»)

:math:`-ec_{n-\nu,es} + ec_{nes} = RC^{+}_{hz} - RC^{-}_{hz}`

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

Logical relation between commitment, startup and shutdown status of a committed electricity unit (all except the VRE units) [p.u.] («``eEleCommitmentStartupShutdown``»)
Initial commitment of the units is determined by the model based on the merit order loading, including the VRE and ESS units.

:math:`euc_{neg} - euc_{n-\nu,g} = esu_{neg} - esd_{neg} \quad \forall neg`

Maximum commitment of an electricity unit (all except the VRE units) [p.u.] («``eEleMaxCommitment``»)

:math:`euc_{neg} \leq sum_{n' = n-\nu-TU_t}^n euc^{max}_{n't} \quad \forall neg`

Logical relation between commitment, startup and shutdown status of a committed hydrogen unit [p.u.] («``eHydCommitmentStartupShutdown``»)

:math:`huc_{nhg} - huc_{n-\nu,hg} = hsu_{nhg} - hsd_{nhg} \quad \forall nhg`

Minimum up time and down time of thermal unit [h] («``eMinUpTimeEle``, ``eMinDownTimeEle``»)

- D. Rajan and S. Takriti, “Minimum up/down polytopes of the unit commitment problem with start-up costs,” IBM, New York, Technical Report RC23628, 2005. https://pdfs.semanticscholar.org/b886/42e36b414d5929fed48593d0ac46ae3e2070.pdf

:math:`\sum_{n'=n+\nu-TU_t}^n esu_{n't} \leq     euc_{net} \quad \forall net`

:math:`\sum_{n'=n+\nu-TD_t}^n esd_{n't} \leq 1 - euc_{net} \quad \forall net`

Minimum up time and down time of hydrogen unit [h] («``eMinUpTimeHyd``, ``eMinDownTimeHyd``»)

:math:`\sum_{n'=n+\nu-TU_h}^n hsu_{n'hg} \leq     huc_{nhg} \quad \forall nhg`

:math:`\sum_{n'=n+\nu-TD_h}^n hsd_{n'hg} \leq 1 - huc_{nhg} \quad \forall nhg`

Decision variable of the operation of the compressor conditioned by the on/off status variable of itself [GWh] («``eCompressorOperStatus``»)

:math:`ec^{Comp}_{nhs} \geq hp_{nhz}/\overline{HP}_{nhz} \overline{EC}^{comp}_{nhs} - 1e-3 (1 - hcf_{nhs}) \quad \forall nhs`

Decision variable of the operation of the compressor conditioned by the status of energy of the hydrogen tank [kgH2] («``eCompressorOperInventory``»)

:math:`hsi_{nhs} \leq \underline{HI}_{nhs} + (\overline{HI}_{nhs} - \underline{HI}_{nhs}) hcf_{nhs} \quad \forall nhs`

StandBy status of the electrolyzer conditioning its electricity consumption («``eEleStandBy_consumption_UpperBound``, ``eEleStandBy_consumption_LowerBound``»)

:math:`ec^{StandBy}_{nhz} \geq \overline{EC}_{nhz} hsf_{nhz} \quad \forall nhz`

:math:`ec^{StandBy}_{nhz} \leq \overline{EC}_{nhz} hsf_{nhz} \quad \forall nhz`

StandBy status of the electrolyzer conditioning its hydrogen production («``eHydStandBy_production_UpperBound``, ``eHydStandBy_production_LowerBound``»)

:math:`ec^{StandBy}_{nhz} \geq \overline{EC}_{nhz} (1 - hsf_{nhz}) \quad \forall nhz`

:math:`ec^{StandBy}_{nhz} \leq \underline{EC}_{nhz} (1 - hsf_{nhz}) \quad \forall nhz`

Avoid transition status from off to StandBy of the electrolyzer («``eHydAvoidTransitionOff2StandBy``»)

:math:`hsf_{nhz} \leq huc_{nhz} \quad \forall nhz`

3. Energy Storage Dynamics
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

Electricity Storage Charge/Discharge Incompatibility

:math:`\frac{ec_{nes}}{\overline{EC}_{nes}} \leq esf_{nes} \quad \forall nes`

:math:`\frac{ep_{nes}}{\overline{EP}_{nes}} \leq 1 - esf_{nes} \quad \forall nes`

Hydrogen Storage Charge/Discharge Incompatibility

:math:`\frac{hc_{nhs}}{\overline{HC}_{nhs}} \leq hsf_{nhs} \quad \forall nhs`

:math:`\frac{hp_{nhs}}{\overline{HP}_{nhs}} \leq 1 - hsf_{nhs} \quad \forall nhs`

Maximum and Minimum Relative Inventory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The relative inventory of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the maximum capacity («``eMaxInventory2Comm``, ``eMinInventory2Comm``»)

:math:`\frac{esi_{nes}}{\overline{EI}_{nes}}  \leq euc_{nes} \quad \forall nes`

:math:`\frac{esi_{nes}}{\underline{EI}_{nes}} \geq euc_{nes} \quad \forall nes`

:math:`\frac{hsi_{nhs}}{\overline{HI}_{nhs}}  \leq huc_{nhs} \quad \forall nhs`

:math:`\frac{hsi_{nhs}}{\underline{HI}_{nhs}} \geq huc_{nhs} \quad \forall nhs`


Energy Inflows
~~~~~~~~~~~~~~
Energy inflows of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the inflows data («``eMaxInflows2Commitment``, ``eMinInflows2Commitment``»)

:math:`\frac{eei_{nes}}{EEI_{nes}} \leq euc_{nes} \quad \forall nes`

:math:`\frac{hei_{nhs}}{HEI_{nhs}} \leq huc_{nhs} \quad \forall nhs`

Energy Outflows
~~~~~~~~~~~~~~~
Relationship between electricity outflows and commitment of the units («``eMaxEleOutflows2Commitment``, ``eMinEleOutflows2Commitment``»)

:math:`\frac{eeo_{nes}}{\overline{EEO}_{nes}} \leq euc_{nes} \quad \forall nes`

:math:`\frac{eeo_{nes}}{\underline{EEO}_{nes}} \geq euc_{nes} \quad \forall nes`

Relationship between hydrogen outflows and commitment of the units («``eMaxHydOutflows2Commitment``, ``eMinHydOutflows2Commitment``»)

:math:`\frac{heo_{nhs}}{\overline{HEO}_{nhs}} \leq huc_{nhs} \quad \forall nhs`

:math:`\frac{heo_{nhs}}{\underline{HEO}_{nhs}} \geq huc_{nhs} \quad \forall nhs`

ESS electricity outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) must be satisfied («``eEleEnergyOutflows``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\rho_e}}^n DUR_{n'} (eeo_{n'es} - EEO_{n'es}) = 0 \quad \forall nes, n \in \rho_e`

ESS hydrogen minimum and maximum outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) must be satisfied («``eHydMinEnergyOutflows``, ``eHydMaxEnergyOutflows``»)

:math:`\sum_{n' = n-\frac{\tau_h}{\rho_h}}^n DUR_{n'} (heo_{n'hs} - HEO_{n'hs}) \geq 0 \quad \forall nhs, n \in \rho_h`

:math:`\sum_{n' = n-\frac{\tau_h}{\rho_h}}^n DUR_{n'} (heo_{n'hs} - HEO_{n'hs}) \leq 0 \quad \forall nhs, n \in \rho_h`

Incompatibility between charge and outflows use of an electricity ESS [p.u.] («``eIncompatibilityEleChargeOutflows``»)

:math:`\frac{eeo_{nes} + ec2b_{nes}}{\overline{EC}_{nes} - \underline{EC}_{nes}} \leq 1 \quad \forall nes`

Incompatibility between charge and outflows use of a hydrogen ESS [p.u.] («``eIncompatibilityHydChargeOutflows``»)

:math:`\frac{heo_{nhs} + hc2b_{nhs}}{\overline{HC}_{nhs} - \underline{HC}_{nhs}} \leq 1 \quad \forall nhs`

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

Second block of a committed electric generator providing reserves
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Maximum and minimum electricity generation of the second block of a committed unit (all except the VRE and ESS units) [p.u.] («``eMaxEleOutput2ndBlock``, ``eMinEleOutput2ndBlock``»)

* D.A. Tejada-Aranego, S. Lumbreras, P. Sánchez-Martín, and A. Ramos "Which Unit-Commitment Formulation is Best? A Systematic Comparison" IEEE Transactions on Power Systems 35 (4):2926-2936 Jul 2020 `10.1109/TPWRS.2019.2962024 <https://doi.org/10.1109/TPWRS.2019.2962024>`_

* C. Gentile, G. Morales-España, and A. Ramos "A tight MIP formulation of the unit commitment problem with start-up and shut-down constraints" EURO Journal on Computational Optimization 5 (1), 177-201 Mar 2017. `10.1007/s13675-016-0066-y <https://doi.org/10.1007/s13675-016-0066-y>`_

* G. Morales-España, A. Ramos, and J. Garcia-Gonzalez "An MIP Formulation for Joint Market-Clearing of Energy and Reserves Based on Ramp Scheduling" IEEE Transactions on Power Systems 29 (1): 476-488, Jan 2014. `10.1109/TPWRS.2013.2259601 <https://doi.org/10.1109/TPWRS.2013.2259601>`_

* G. Morales-España, J.M. Latorre, and A. Ramos "Tight and Compact MILP Formulation for the Thermal Unit Commitment Problem" IEEE Transactions on Power Systems 28 (4): 4897-4908, Nov 2013. `10.1109/TPWRS.2013.2251373 <https://doi.org/10.1109/TPWRS.2013.2251373>`_

:math:`\frac{ep2b_{net} + up^{SR}_{net} + up^{TR}_{net}}{\overline{EP}_{net} - \underline{EP}_{net}} \leq euc_{net} \quad \forall net`

:math:`\frac{ep2b_{net} - dp^{SR}_{net} - dp^{TR}_{net}}{\overline{EP}_{net} - \underline{EP}_{net}} \geq 0         \quad \forall net`

Maximum and minimum hydrogen generation of the second block of a committed unit [p.u.] («``eMaxHydOutput2ndBlock``, ``eMinHydOutput2ndBlock``»)

:math:`\frac{hp2b_{nhg}}{\overline{HP}_{nhg} - \underline{HP}_{nhg}} \leq huc_{nhg} \quad \forall nhg`

:math:`\frac{hp2b_{nhg}}{\overline{HP}_{nhg} - \underline{HP}_{nhg}} \geq 0         \quad \forall nhg`

Maximum and minimum discharge of the second block of an electricity ESS [p.u.] («``eMaxEleESSOutput2ndBlock``, ``eMinEleESSOutput2ndBlock``»)

:math:`\frac{ep2b_{nes} + up^{SR}_{nes} + up^{TR}_{nes}}{\overline{EP}_{nes} - \underline{EP}_{nes}} \leq 1 \quad \forall nes`

:math:`\frac{ep2b_{nes} - dp^{SR}_{nes} - dp^{TR}_{nes}}{\overline{EP}_{nes} - \underline{EP}_{nes}} \geq 0 \quad \forall nes`

Maximum and minimum discharge of the second block of a hydrogen ESS [p.u.] («``eMaxHydESSOutput2ndBlock``, ``eMinHydESSOutput2ndBlock``»)

:math:`\frac{hp2b_{nhs}}{\overline{HP}_{nhs} - \underline{HP}_{nhs}} \leq 1 \quad \forall nhs`

:math:`\frac{hp2b_{nhs}}{\overline{HP}_{nhs} - \underline{HP}_{nhs}} \geq 0 \quad \forall nhs`

Maximum and minimum charge of the second block of an electricity ESS [p.u.] («``eMaxEleESSCharge2ndBlock``, ``eMinEleESSCharge2ndBlock``»)

:math:`\frac{ec2b_{nes} + dc^{SR}_{nes} + dc^{TR}_{nes}}{\overline{EC}_{nes} - \underline{EC}_{nes}} \leq 1 \quad \forall nes`

:math:`\frac{ec2b_{nes} - uc^{SR}_{nes} - uc^{TR}_{nes}}{\overline{EC}_{nes} - \underline{EC}_{nes}} \geq 0 \quad \forall nes`

Maximum and minimum charge of the second block of a hydrogen unit due to the energy conversion [p.u.] («``eMaxEle2HydCharge2ndBlock``, ``eMinEle2HydCharge2ndBlock``»)

:math:`\frac{ec2b_{nhz} + dc^{SR}_{nhz} + dc^{TR}_{nhz}}{\overline{EC}_{nhz}} \leq 1 \quad \forall nhz`

:math:`\frac{ec2b_{nhz} - uc^{SR}_{nhz} - uc^{TR}_{nhz}}{\overline{EC}_{nhz}} \geq 0 \quad \forall nhz`

Maximum and minimum charge of the second block of a hydrogen ESS [p.u.] («``eMaxHydESSCharge2ndBlock``, ``eMinHydESSCharge2ndBlock``»)

:math:`\frac{hc2b_{nhs}}{\overline{HC}_{nhs} - \underline{HC}_{nhs}} \leq 1 \quad \forall nhs`

:math:`\frac{hc2b_{nhs}}{\overline{HC}_{nhs} - \underline{HC}_{nhs}} \geq 0 \quad \forall nhs`

4. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

DC Power Flow
~~~~~~~~~~~~~
For the electricity grid, ``eKirchhoff2ndLaw`` implements a DC power flow model, relating the power flow on a line to the voltage angles at its connecting nodes.

.. math::
   \frac{\veleflow_{\periodindex,\scenarioindex,\timeindex,\text{ni,nf,cc}}}{\text{TTC}_{\text{ni,nf,cc}}} - \frac{\theta_{\periodindex,\scenarioindex,\timeindex,\text{ni}} - \theta_{\periodindex,\scenarioindex,\timeindex,\text{nf}}}{\text{X}_{\text{ni,nf,cc}} \cdot \text{TTC}_{\text{ni,nf,cc}}} \cdot 0.1 = 0

6. Demand-Side and Reliability Constraints
------------------------------------------
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

Demand Shifting Balance
~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand shifting balance if :math:`\peledemflexible_{\eledemindex} == 1.0` and :math:`\peledemshiftedsteps_{\eledemindex} > 0.0` («``eEleDemandShiftBalance``»)

:math:`\sum_{\timeindex ' = \timeindex-\peledemshiftedsteps_{\demandindex}}^n DUR_{n'} (\veledemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex} - \peledemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex}) = 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex`

Share of Flexible Demand
~~~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand share of total demand if :math:`\peledemflexible_{\eledemindex} == 1.0` and :math:`\peledemshiftedsteps_{\eledemindex} > 0.0` («``eEleDemandShifted``»)

:math:`\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} = \peledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} + \veledemflex_{\periodindex,\scenarioindex,\timeindex,\demandindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex`

Cycle target for demand
~~~~~~~~~~~~~~~~~~~~~~~
Hydrogen demand cycle target («``eHydDemandCycleTarget``»)

:math:`\sum_{n' = n-\frac{\tau_d}{\nu}}^n DUR_{n'} (hd_{n'nd} - HD_{n'nd}) = 0 \quad \forall nnd, n \in \rho_d`

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


8. Bounds on Variables
-----------------------
To ensure numerical stability and solver efficiency, bounds are placed on key decision variables. For example, the state-of-charge variables for storage units are bounded between zero and their maximum capacity.

:math:`0 \leq ep_{neg}                               \leq \overline{EP}_{neg}                              \quad \forall neg`

:math:`0 \leq hp_{nhg}   \leq \overline{HP}_{nhg}                                                          \quad \forall nhg`

:math:`0 \leq ec_{nes}  \leq \overline{EC}_{nes}                                                           \quad \forall nes`

:math:`0 \leq ec_{nhz}  \leq \overline{EC}_{nhz}                                                           \quad \forall nhz`

:math:`0 \leq hc_{nhs}   \leq \overline{HC}_{nhs}                                                          \quad \forall nhs`

:math:`0 \leq hc_{net}   \leq \overline{HC}_{net}                                                          \quad \forall net`

:math:`0 \leq ep2b_{neg} \leq \overline{EP}_{neg} - \underline{EP}_{neg}                                   \quad \forall neg`

:math:`0 \leq hp2b_{nhg} \leq \overline{HP}_{nhg} - \underline{HP}_{nhg}                                   \quad \forall nh`

:math:`0 \leq eeo_{nes} \leq \max(\overline{EP}_{nes},\overline{EC}_{nes})                                 \quad \forall nes`

:math:`0 \leq heo_{nhs} \leq \max(\overline{HP}_{nhs},\overline{HC}_{nhs})                                 \quad \forall nhs`

:math:`0 \leq up^{SR}_{neg}, dp^{SR}_{neg}  \leq \overline{EP}_{neg} - \underline{EP}_{neg}                \quad \forall neg`

:math:`0 \leq up^{TR}_{neg}, dp^{TR}_{neg}  \leq \overline{EP}_{neg} - \underline{EP}_{neg}                \quad \forall neg`

:math:`0 \leq uc^{SR}_{nes}, dc^{SR}_{nes} \leq \overline{EC}_{nes} - \underline{EC}_{nes}                 \quad \forall nes`

:math:`0 \leq uc^{TR}_{nes}, dc^{TR}_{nes} \leq \overline{EC}_{nes} - \underline{EC}_{nes}                 \quad \forall nes`

:math:`0 \leq ec2b_{nes}  \leq \overline{EC}_{nes}                                                         \quad \forall nes`

:math:`0 \leq hc2b_{nhs}  \leq \overline{HC}_{nhs}                                                         \quad \forall nhs`

:math:`\underline{EI}_{nes} \leq  esi_{nes}  \leq \overline{EI}_{nes}                                      \quad \forall nes`

:math:`\underline{HI}_{nhs} \leq  hsi_{nhs}  \leq \overline{HI}_{nhs}                                      \quad \forall nhs`

:math:`0 \leq  ess_{nes}                                                                                   \quad \forall nes`

:math:`0 \leq  hss_{nhs}                                                                                   \quad \forall nhs`

:math:`0 \leq ec^{R+}_{nes}, ec^{R-}_{nes} \leq \overline{EC}_{nes}                                        \quad \forall nes`

:math:`0 \leq ec^{R+}_{nhz}, ec^{R-}_{nhz} \leq \overline{EC}_{nhz}                                        \quad \forall nhz`

:math:`0 \leq ec^{Comp}_{nhs} \leq \overline{EC}_{nhs}                                                     \quad \forall nhs`

:math:`0 \leq ec^{StandBy}_{nhz} \leq \overline{EC}_{nhz}                                                  \quad \forall nhz`

:math:`-\overline{ENF}_{nijc} \leq  ef_{nij}  \leq \overline{ENF}_{nijc}                                   \quad \forall nijc`

:math:`-\overline{HNF}_{nijc} \leq  hf_{nij}  \leq \overline{HNF}_{nijc}                                   \quad \forall nijc`