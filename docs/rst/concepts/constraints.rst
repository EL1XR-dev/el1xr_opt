Constraints
===========
The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

1. Market and Commercial Constraints
------------------------------------
These constraints model the rules for interacting with external markets. And the economic trading is shown in the next figure.

.. image:: /../img/Market_interaction.png
   :scale: 30%
   :align: center

Day-ahead Electricity Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Participation in the day-ahead electricity market is modeled through the next constraints, which ensure that the amount of energy bought from or sold to the market does not exceed predefined limits for each time step and retailer.

Eletricity bought from the market («``eEleRetMaxBuy``»)

If :math:`\pelemaxmarketbuy_{\traderindex} >= 0.0`

:math:`\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pelemaxmarketbuy_{\traderindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\traderindex`

Eletricity sold to the market («``eEleRetMaxSell``»)

If :math:`\pelemaxmarketsell_{\traderindex} >= 0.0`

:math:`\velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex} \le \pelemaxmarketsell_{\traderindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\traderindex`

Reserve Electricity Market Participation (to be implemented)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Frequency containment reserves in normal operation (FCR-N)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-N is modeled through the next constraint, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{\periodindex,\scenarioindex,\timeindex,\genindex} rp^{FN}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \sum_{\periodindex,\scenarioindex,\timeindex,\storageindex} rc^{FN}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq R^{FN}_{n} \quad \forall n`

Frequency containment reserves in disturbed operation (FCR-D)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-D is modeled through the upward and downward reserve constraints, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

:math:`\sum_{\periodindex,\scenarioindex,\timeindex,\genindex} up^{FD}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \sum_{\periodindex,\scenarioindex,\timeindex,\storageindex} uc^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq UR^{FD}_{n} \quad \forall n`

:math:`\sum_{\periodindex,\scenarioindex,\timeindex,\genindex} dp^{FD}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \sum_{\periodindex,\scenarioindex,\timeindex,\storageindex} dc^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq DR^{FD}_{n} \quad \forall n`

Peak Demand Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints starting with ``eElePeak...`` identify the highest power peak within a billing period for tariff calculations. ``eElePeakHourValue`` uses binary variables to select the peak consumption hour.

.. math::
   \velepeakdemand_{\periodindex,\scenarioindex,\text{m,er,peak}} \ge \velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\text{er}} \!-\! 100 \cdot \sum_{\text{peak'} < \text{peak}} \velepeakdemandindbin_{\periodindex,\scenarioindex,\timeindex,\text{er,peak'}}

2. Energy Balance
-----------------
These are the most fundamental constraints, ensuring that at every node (:math:`\busindexa`) and at every timestep (:math:`\timeindex`), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
It is represented by («``eElectricityBalance``») as follows:

.. math::

   \begin{aligned}
   &\sum_{\genindex \in \nGE_{\busindex}} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \!-\! \sum_{\storageindex \in \nEE_{\busindex}} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \!-\! \sum_{\genindex \in \nGHE_{\busindex}} (\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \!+\! \veleconsumptionstandby_{\periodindex,\scenarioindex,\timeindex,\genindex}) \\
   &- \sum_{\storageindex \in \nEH_{\busindex}} (\veleconsumptioncompress_{\periodindex,\scenarioindex,\timeindex,\storageindex})
   \!+\! \sum_{\traderindex \in \nRE_{\busindex}}(\velemarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex}
   \!-\! \velemarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}) \\
   &= \sum_{\demandindex \in \nDE_{\busindex}}(\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}
   \!-\! \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex})
   \!+\! \sum_{\busindexb,\circuitindex} \vflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   \!-\! \sum_{\busindexa,\circuitindex} \vflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex
   \end{aligned}

Hydrogen Balance
~~~~~~~~~~~~~~~~
It is represented by «``eHydrogenBalance``») as follows:

.. math::

   \begin{aligned}
   &\sum_{\genindex \in \nGH_{\busindex}} \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \!-\! \sum_{\storageindex \in \nEH_{\busindex}} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \!-\! \sum_{\genindex \in \nGEH_{\busindex}} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &\!+\! \sum_{\traderindex \in \nRE_{\busindex}}(\vhydmarketbuy_{\periodindex,\scenarioindex,\timeindex,\traderindex} \!-\! \vhydmarketsell_{\periodindex,\scenarioindex,\timeindex,\traderindex}) \\
   &= \sum_{\demandindex \in \nDH_{\busindex}} (\vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} \!-\! \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex})
   \!+\! \sum_{\busindexb,\circuitindex} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   \!-\! \sum_{\busindexa,\circuitindex} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex
   \end{aligned}

2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Output and Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~
Total generation of an electricity unit (all except the VRE units) («``eEleTotalOutput``»)

:math:`\frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} = \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! URA^{SR}_{n}up^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! DRA^{SR}_{n}dp^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGE \setminus \nGVRE`

Total generation of a hydrogen unit («``eHydTotalOutput``»)

:math:`\frac{\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} = \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGH`

Total charge of an electricity ESS («``eEleTotalCharge``»)

:math:`\frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} = 1 \!+\! \frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! URA^{SR}_{n}uc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! DRA^{SR}_{n}dc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Total charge of a hydrogen unit («``eHydTotalCharge``»)

:math:`\frac{\vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} = 1 \!+\! \frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Energy Conversion
~~~~~~~~~~~~~~~~~
Energy conversion from energy from electricity to hydrogen and vice versa («``eAllEnergy2Ele``, ``eAllEnergy2Hyd``»)

:math:`\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} = \phydtoelefunction_{\periodindex,\scenarioindex,\timeindex,\genindex} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGEH`

:math:`\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} = \peletohydfunction_{\periodindex,\scenarioindex,\timeindex,\genindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

Ramping Limits
~~~~~~~~~~~~~~
A series of constraints limit how quickly the output or charging rate of an asset can change. For example, ``eEleMaxRampUpOutput`` restricts the increase in a generator's output between consecutive timesteps.

Maximum ramp up and ramp down for the second block of a non-renewable (thermal, hydro) electricity unit («``eMaxRampUpEleOutput``, ``eMaxRampDwEleOutput``»)

* P. Damcı-Kurt, S. Küçükyavuz, D. Rajan, and A. Atamtürk, “A polyhedral study of production ramping,” Math. Program., vol. 158, no. 1–2, pp. 175–205, Jul. 2016. `10.1007/s10107-015-0919-9 <https://doi.org/10.1007/s10107-015-0919-9>`_

:math:`\frac{- ep2b_{n-\nu,g} \!-\! dp^{SR}_{n-\nu,g} \!-\! dp^{TR}_{n-\nu,g} \!+\! ep2b_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! up^{SR}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! up^{TR}_{\periodindex,\scenarioindex,\timeindex,\genindex}}{DUR_n RU_g} \leq   euc_{\periodindex,\scenarioindex,\timeindex,\genindex}      \!-\! esu_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

:math:`\frac{- ep2b_{n-\nu,g} \!+\! up^{SR}_{n-\nu,g} \!+\! up^{TR}_{n-\nu,g} \!+\! ep2b_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! dp^{SR}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! dp^{TR}_{\periodindex,\scenarioindex,\timeindex,\genindex}}{DUR_n RD_g} \geq \!-\! euc_{n-\nu,g} \!+\! esd_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

Maximum ramp down and ramp up for the charge of an electricity ESS («``eMaxRampUpEleCharge``, ``eMaxRampDwEleCharge``»)

:math:`\frac{- ec2b_{n-\nu,es} \!+\! dc^{SR}_{n-\nu,es} \!+\! dc^{TR}_{n-\nu,es} \!+\! ec2b_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! uc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! uc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RU_es} \geq \!-\! 1 \quad \forall nes`

:math:`\frac{- ec2b_{n-\nu,es} \!-\! uc^{SR}_{n-\nu,es} \!-\! uc^{TR}_{n-\nu,es} \!+\! ec2b_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RD_es} \leq   1 \quad \forall nes`

Maximum ramp up and ramp down for the  second block of a hydrogen unit («``eMaxRampUpHydOutput``, ``eMaxRampDwHydOutput``»)

:math:`\frac{- hp2b_{n-\nu,hg} \!+\! hp2b_{\periodindex,\scenarioindex,\timeindex,\genindex}}{DUR_n RU_hg} \leq   huc_{\periodindex,\scenarioindex,\timeindex,\genindex}      \!-\! hsu_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhg`

:math:`\frac{- hp2b_{n-\nu,hg} \!+\! hp2b_{\periodindex,\scenarioindex,\timeindex,\genindex}}{DUR_n RD_hg} \geq \!-\! huc_{n-\nu,hg} \!+\! hsd_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhg`

Maximum ramp down and ramp up for the charge of a hydrogen ESS («``eMaxRampUpHydCharge``, ``eMaxRampDwHydCharge``»)

:math:`\frac{- hc2b_{n-\nu,hs} \!+\! hc2b_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RU_hs} \geq \!-\! 1 \quad \forall nhs`

:math:`\frac{- hc2b_{n-\nu,hs} \!+\! hc2b_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RD_hs} \leq   1 \quad \forall nhs`

Maximum ramp up and ramp down for the outflows of a hydrogen ESS («``eMaxRampUpHydOutflows``, ``eMaxRampDwHydOutflows``»)

:math:`\frac{- heo_{n-\nu,hs} \!+\! heo_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RU_hs} \leq   1 \quad \forall nhs`

:math:`\frac{- heo_{n-\nu,hs} \!+\! heo_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_n RD_hs} \geq \!-\! 1 \quad \forall nhs`

Ramp up and ramp down for the provision of demand to the hydrogen customers («``eMaxRampUpHydDemand``, ``eMaxRampDwHydDemand``»)

:math:`\frac{- hd_{n-\nu,nd} \!+\! hd_{nnd}}{DUR_n RU_nd} \leq   1 \quad \forall nnd`

:math:`\frac{- hd_{n-\nu,nd} \!+\! hd_{nnd}}{DUR_n RD_nd} \geq \!-\! 1 \quad \forall nnd`

Differences between electricity consumption of two consecutive hours [GW] («``eEleConsumptionDiff``»)

:math:`-ec_{n-\nu,es} \!+\! ec_{\periodindex,\scenarioindex,\timeindex,\storageindex} = RC^{\!+\!}_{hz} \!-\! RC^{-}_{hz}`

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

Logical relation between commitment, startup and shutdown status of a committed electricity unit (all except the VRE units) [p.u.] («``eEleCommitmentStartupShutdown``»)
Initial commitment of the units is determined by the model based on the merit order loading, including the VRE and ESS units.

:math:`\velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \velecommitbin_{\periodindex,\scenarioindex,\timeindex-\timestep,\genindex} = \velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \veleshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGE \setminus \nGVRE`

Logical relation between commitment, startup and shutdown status of a committed hydrogen unit [p.u.] («``eHydCommitmentStartupShutdown``»)

:math:`\vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex-\timestep,\genindex} = \velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \veleshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

Minimum up time and down time of thermal unit [h] («``eMinUpTimeEle``, ``eMinDownTimeEle``»)

- D. Rajan and S. Takriti, “Minimum up/down polytopes of the unit commitment problem with start-up costs,” IBM, New York, Technical Report RC23628, 2005. https://pdfs.semanticscholar.org/b886/42e36b414d5929fed48593d0ac46ae3e2070.pdf

:math:`\sum_{n'=n\!+\!\nu-TU_t}^n esu_{n't} \leq     euc_{net} \quad \forall net`

:math:`\sum_{n'=n\!+\!\nu-TD_t}^n esd_{n't} \leq 1 \!-\! euc_{net} \quad \forall net`

Minimum up time and down time of hydrogen unit [h] («``eMinUpTimeHyd``, ``eMinDownTimeHyd``»)

:math:`\sum_{n'=n\!+\!\nu-TU_h}^n hsu_{n'hg} \leq     huc_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhg`

:math:`\sum_{n'=n\!+\!\nu-TD_h}^n hsd_{n'hg} \leq 1 \!-\! huc_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhg`

Decision variable of the operation of the compressor conditioned by the on/off status variable of itself [GWh] («``eCompressorOperStatus``»)

:math:`ec^{Comp}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \geq hp_{\periodindex,\scenarioindex,\timeindex,\genindex}/\overline{HP}_{\periodindex,\scenarioindex,\timeindex,\genindex} \overline{EC}^{comp}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! 1e-3 (1 \!-\! hcf_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \quad \forall nhs`

Decision variable of the operation of the compressor conditioned by the status of energy of the hydrogen tank [kgH2] («``eCompressorOperInventory``»)

:math:`hsi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! (\overline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) hcf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nhs`

StandBy status of the electrolyzer conditioning its electricity consumption («``eEleStandBy_consumption_UpperBound``, ``eEleStandBy_consumption_LowerBound``»)

:math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \geq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

:math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

StandBy status of the electrolyzer conditioning its hydrogen production («``eHydStandBy_production_UpperBound``, ``eHydStandBy_production_LowerBound``»)

:math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \geq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} (1 \!-\! hsf_{\periodindex,\scenarioindex,\timeindex,\genindex}) \quad \forall nhz`

:math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \underline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} (1 \!-\! hsf_{\periodindex,\scenarioindex,\timeindex,\genindex}) \quad \forall nhz`

Avoid transition status from off to StandBy of the electrolyzer («``eHydAvoidTransitionOff2StandBy``»)

:math:`hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq huc_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

3. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

Inventory  Balance (State-of-Charge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equation, ``eEleInventory`` for electricity and ``eHydInventory`` for hydrogen, tracks the stored energy level over time.

State-of-Charge balance for electricity storage systems:

:math:`\veleinventory_{\timeindex-\frac{\pelestoragecycle_{\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}},\storageindex} \!+\! \sum_{\timeindex ' = \timeindex-\frac{\pelestoragecycle_{\storageindex}}{\ptimestep}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \veleproduction_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!+\! \pelestorageefficiency_{\storageindex} \veleconsumption_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) = \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \velespillage_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

State-of-Charge balance for hydrogen storage systems:

:math:`\vhydinventory_{\timeindex-\frac{\phydstoragecycle_{\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}},\storageindex} \!+\! \sum_{\timeindex ' = \timeindex-\frac{\phydstoragecycle_{\storageindex}}{\ptimestep}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\vhydenergyinflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \vhydproduction_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!+\! \phydstorageefficiency_{\storageindex} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) = \vhydinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \vhydspillage_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The constraints prevent a storage unit from charging and discharging in the same timestep, using binary variables (:math:`\velestoroperatbin`) and (:math:`\vhydstoroperatbin`) to enforce this condition.

Electricity Storage Charge/Discharge Incompatibility: «``eEleChargingDecision``» and «``eEleDischargingDecision``»

:math:`\frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

:math:`\frac{\veleproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \!-\! \velestoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Hydrogen Storage Charge/Discharge Incompatibility:  «``eHydChargingDecision``» and «``eHydDischargingDecision``»

:math:`\frac{\vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \vhydstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

:math:`\frac{\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \!-\! \vhydstoroperatbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Maximum and Minimum Relative Inventory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The relative inventory of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the maximum capacity («``eMaxInventory2Comm``, ``eMinInventory2Comm``»)

:math:`\frac{esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}  \leq euc_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

:math:`\frac{esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\underline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq euc_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

:math:`\frac{hsi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}  \leq huc_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nhs`

:math:`\frac{hsi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq huc_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nhs`


Energy Inflows
~~~~~~~~~~~~~~
Energy inflows of ESS (only for load levels multiple of 1, 24, 168, 8736 h depending on the ESS storage type) constrained by the ESS commitment decision times the inflows data.

For maximum electricity inflows («``eMaxEleInflows2Commitment``»)

:math:`\frac{\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

For minimum electricity inflows («``eMinEleInflows2Commitment``»)

:math:`\frac{\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemininflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

For maximum hydrogen inflows («``eMaxHydInflows2Commitment``»)

:math:`\frac{\vhydenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

For minimum hydrogen inflows («``eMinHydInflows2Commitment``»)

:math:`\frac{\vhydenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmininflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Energy Outflows
~~~~~~~~~~~~~~~
Relationship between electricity outflows and commitment of the units («``eEleMaxOutflows2Commitment``, ``eEleMinOutflows2Commitment``»)

:math:`\frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

:math:`\frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Relationship between hydrogen outflows and commitment of the units («``eHydMaxOutflows2Commitment``, ``eHydMinOutflows2Commitment``»)

:math:`\frac{\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

:math:`\frac{\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

ESS electricity outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) must be satisfied («``eEleMaxEnergyOutflows``») and («``eEleMinEnergyOutflows``»)

:math:`\sum_{\timeindex ' = \timeindex-\frac{\pelestoragecycle_{\storageindex}}{\pelestorageoutflowcycle_{\storageindex}}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \pelemaxoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) \leq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\timeindex \in \pelestorageoutflowcycle_{\storageindex}, \storageindex \in \nEE`

:math:`\sum_{\timeindex ' = \timeindex-\frac{\pelestoragecycle_{\storageindex}}{\pelestorageoutflowcycle_{\storageindex}}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \peleminoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\timeindex \in \pelestorageoutflowcycle_{\storageindex}, \storageindex \in \nEE`

ESS hydrogen minimum and maximum outflows (only for load levels multiple of 1, 24, 168, 672, and 8736 h depending on the ESS outflow cycle) must be satisfied («``eHydMaxEnergyOutflows``») and («``eHydMinEnergyOutflows``»)

:math:`\sum_{\timeindex ' = \timeindex-\frac{\phydstoragecycle_{\storageindex}}{\phydstorageoutflowcycle_{\storageindex}}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \phydmaxoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) \leq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\timeindex \in \phydstorageoutflowcycle_{\storageindex}, \storageindex \in \nEH`

:math:`\sum_{\timeindex ' = \timeindex-\frac{\phydstoragecycle_{\storageindex}}{\phydstorageoutflowcycle_{\storageindex}}}^{\timeindex} \ptimestepduration_{\periodindex,\scenarioindex,\timeindex '} (\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex} \!-\! \phydminoutflow_{\periodindex,\scenarioindex,\timeindex ',\storageindex}) \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\timeindex \in \phydstorageoutflowcycle_{\storageindex}, \storageindex \in \nEH`

Incompatibility between charge and outflows use of an electricity ESS [p.u.] («``eIncompatibilityEleChargeOutflows``»)

:math:`\frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Incompatibility between charge and outflows use of a hydrogen ESS [p.u.] («``eIncompatibilityHydChargeOutflows``»)

:math:`\frac{\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Operating reserves from energy storage systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Operating reserves from ESS can only be if enought energy is available for discharging

:math:`RA^{FN}_{n}rp^{FN}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! URA^{FD}_{n}up^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \frac{                      esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_{n}} \quad \forall nes`

:math:`RA^{FN}_{n}rp^{FN}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! DRA^{FD}_{n}dp^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \frac{\overline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_{n}} \quad \forall nes`

or for charging

:math:`RA^{FN}_{n}rc^{FN}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! URA^{FD}_{n}uc^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \frac{\overline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_{n}} \quad \forall nes`

:math:`RA^{FN}_{n}rc^{FN}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! DRA^{FD}_{n}dc^{FD}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \frac{                      esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{DUR_{n}} \quad \forall nes`

Upward operating reserve decision of an ESS when it is consuming and constrained by charging and discharging itself («``eReserveConsChargingDecision_Up``»)

:math:`\frac{uc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! uc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq esf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Upward operating reserve decision of an ESS when it is producing and constrained by charging and discharging itself («``eReserveProdDischargingDecision_Up``»)

:math:`\frac{up^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! up^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{EP}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq esf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Downward operating reserve decision of an ESS when it is consuming and constrained by charging and discharging itself («``eReserveConsChargingDecision_Dw``»)

:math:`\frac{dc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \!-\! esf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Downward operating reserve decision of an ESS when it is producing and constrained by charging and discharging itself («``eReserveProdDischargingDecision_Dw``»)

:math:`\frac{dp^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dp^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\overline{EP}_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \!-\! esf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Energy stored for upward operating reserve in consecutive time steps when ESS is consuming («``eReserveConsUpConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (uc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! uc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! esi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Energy stored for downward operating reserve in consecutive time steps when ESS is consuming («``eReserveConsDwConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (dc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \leq esi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Energy stored for upward operating reserve in consecutive time steps when ESS is producing («``eReserveProdUpConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (up^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! up^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \leq \overline{EP}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! esi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Energy stored for downward operating reserve in consecutive time steps when ESS is producing («``eReserveProdDwConsecutiveTime``»)

:math:`\sum_{n' = n-\frac{\tau_e}{\nu}}^n DUR_{n'} (dp^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! dp^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \leq esi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{EP}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nes`

Second block of a committed electric generator providing reserves
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Maximum and minimum electricity generation of the second block of a committed unit (all except the VRE and ESS units) [p.u.] («``eEleMaxOutput2ndBlock``») and («``eEleMinOutput2ndBlock``»)

* D.A. Tejada-Ara\periodindex,\scenarioindex,\timeindex,\genindexo, S. Lumbreras, P. Sánchez-Martín, and A. Ramos "Which Unit-Commitment Formulation is Best? A Systematic Comparison" IEEE Transactions on Power Systems 35 (4):2926-2936 Jul 2020 `10.1109/TPWRS.2019.2962024 <https://doi.org/10.1109/TPWRS.2019.2962024>`_

* C. Gentile, G. Morales-España, and A. Ramos "A tight MIP formulation of the unit commitment problem with start-up and shut-down constraints" EURO Journal on Computational Optimization 5 (1), 177-201 Mar 2017. `10.1007/s13675-016-0066-y <https://doi.org/10.1007/s13675-016-0066-y>`_

* G. Morales-España, A. Ramos, and J. Garcia-Gonzalez "An MIP Formulation for Joint Market-Clearing of Energy and Reserves Based on Ramp Scheduling" IEEE Transactions on Power Systems 29 (1): 476-488, Jan 2014. `10.1109/TPWRS.2013.2259601 <https://doi.org/10.1109/TPWRS.2013.2259601>`_

* G. Morales-España, J.M. Latorre, and A. Ramos "Tight and Compact MILP Formulation for the Thermal Unit Commitment Problem" IEEE Transactions on Power Systems 28 (4): 4897-4908, Nov 2013. `10.1109/TPWRS.2013.2251373 <https://doi.org/10.1109/TPWRS.2013.2251373>`_

:math:`\frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \vPupward_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \leq \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGENR`

:math:`\frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \vPdownward_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \geq 0         \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGENR`

Maximum and minimum hydrogen generation of the second block of a committed unit [p.u.] («``eMaxHydOutput2ndBlock``, ``eMinHydOutput2ndBlock``»)

:math:`\frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \leq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

:math:`\frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \geq 0         \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

Maximum and minimum discharge of the second block of an electricity ESS [p.u.] («``eMaxEleESSOutput2ndBlock``, ``eMinEleESSOutput2ndBlock``»)

:math:`\frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \vPupward_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

:math:`\frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \vPdownward_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Maximum and minimum discharge of the second block of a hydrogen ESS [p.u.] («``eMaxHydESSOutput2ndBlock``, ``eMinHydESSOutput2ndBlock``»)

:math:`\frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \phydminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

:math:`\frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \phydminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

Maximum and minimum charge of the second block of an electricity ESS [p.u.] («``eMaxEleESSCharge2ndBlock``, ``eMinEleESSCharge2ndBlock``»)

:math:`\frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! \vCdownward_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

:math:`\frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \vCupward_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE`

Maximum and minimum charge of the second block of a hydrogen unit due to the energy conversion [p.u.] («``eMaxEle2HydCharge2ndBlock``, ``eMinEle2HydCharge2ndBlock``»)

:math:`\frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \!+\! \vCdownward_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

:math:`\frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \vCupward_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}} \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

Maximum and minimum charge of the second block of a hydrogen ESS [p.u.] («``eMaxHydESSCharge2ndBlock``, ``eMinHydESSCharge2ndBlock``»)

:math:`\frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \leq 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

:math:`\frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \geq 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

4. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

DC Power Flow
~~~~~~~~~~~~~
For the electricity grid, ``eKirchhoff2ndLaw`` implements a DC power flow model, relating the power flow on a line to the voltage angles at its connecting nodes.

.. math::
   \frac{\veleflow_{\periodindex,\scenarioindex,\timeindex,\text{ni,nf,cc}}}{\text{TTC}_{\text{ni,nf,cc}}} \!-\! \frac{\theta_{\periodindex,\scenarioindex,\timeindex,\text{ni}} \!-\! \theta_{\periodindex,\scenarioindex,\timeindex,\text{nf}}}{\text{X}_{\text{ni,nf,cc}} \cdot \text{TTC}_{\text{ni,nf,cc}}} \cdot 0.1 = 0

6. Demand-Side and Reliability Constraints
------------------------------------------
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

Demand Shifting Balance
~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand shifting balance («``eEleDemandShiftBalance``»)

If :math:`\peledemflexible_{\demandindex} == 1.0` and :math:`\peledemshiftedsteps_{\demandindex} > 0.0`:

:math:`\sum_{\timeindex ' = \timeindex-\peledemshiftedsteps_{\demandindex}}^n DUR_{n'} (\veledemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex} \!-\! \peledemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex}) = 0 \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex`

Share of Flexible Demand
~~~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand share of total demand («``eEleDemandShifted``»)

If :math:`\peledemflexible_{\demandindex} == 1.0` and :math:`\peledemshiftedsteps_{\demandindex} > 0.0`:

:math:`\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} = \peledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} \!+\! \veledemflex_{\periodindex,\scenarioindex,\timeindex,\demandindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex`

Cycle target for demand
~~~~~~~~~~~~~~~~~~~~~~~
Hydrogen demand cycle target («``eHydDemandCycleTarget``»)

:math:`\sum_{n' = n-\frac{\tau_d}{\nu}}^n DUR_{n'} (hd_{n'nd} \!-\! HD_{n'nd}) = 0 \quad \forall nnd, n \in \rho_d`

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

:math:`0 \leq ep_{\periodindex,\scenarioindex,\timeindex,\genindex}                               \leq \overline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                              \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

:math:`0 \leq hp_{\periodindex,\scenarioindex,\timeindex,\genindex}   \leq \overline{HP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                                          \quad \forall nhg`

:math:`0 \leq ec_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                           \quad \forall nes`

:math:`0 \leq ec_{\periodindex,\scenarioindex,\timeindex,\genindex}  \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                                           \quad \forall nhz`

:math:`0 \leq hc_{\periodindex,\scenarioindex,\timeindex,\storageindex}   \leq \overline{HC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                          \quad \forall nhs`

:math:`0 \leq hc_{net}   \leq \overline{HC}_{net}                                                          \quad \forall net`

:math:`0 \leq ep2b_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \underline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

:math:`0 \leq hp2b_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{HP}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \underline{HP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                   \quad \forall nh`

:math:`0 \leq eeo_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \max(\overline{EP}_{\periodindex,\scenarioindex,\timeindex,\storageindex},\overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex})                                 \quad \forall nes`

:math:`0 \leq heo_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \max(\overline{HP}_{\periodindex,\scenarioindex,\timeindex,\storageindex},\overline{HC}_{\periodindex,\scenarioindex,\timeindex,\storageindex})                                 \quad \forall nhs`

:math:`0 \leq up^{SR}_{\periodindex,\scenarioindex,\timeindex,\genindex}, dp^{SR}_{\periodindex,\scenarioindex,\timeindex,\genindex}  \leq \overline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \underline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

:math:`0 \leq up^{TR}_{\periodindex,\scenarioindex,\timeindex,\genindex}, dp^{TR}_{\periodindex,\scenarioindex,\timeindex,\genindex}  \leq \overline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \underline{EP}_{\periodindex,\scenarioindex,\timeindex,\genindex}                \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex`

:math:`0 \leq uc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}, dc^{SR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                 \quad \forall nes`

:math:`0 \leq uc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex}, dc^{TR}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                 \quad \forall nes`

:math:`0 \leq ec2b_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                         \quad \forall nes`

:math:`0 \leq hc2b_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \overline{HC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                         \quad \forall nhs`

:math:`\underline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq  esi_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \overline{EI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                      \quad \forall nes`

:math:`\underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq  hsi_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \overline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                      \quad \forall nhs`

:math:`0 \leq  ess_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                                                   \quad \forall nes`

:math:`0 \leq  hss_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                                                   \quad \forall nhs`

:math:`0 \leq ec^{R\!+\!}_{\periodindex,\scenarioindex,\timeindex,\storageindex}, ec^{R-}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                        \quad \forall nes`

:math:`0 \leq ec^{R\!+\!}_{\periodindex,\scenarioindex,\timeindex,\genindex}, ec^{R-}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                        \quad \forall nhz`

:math:`0 \leq ec^{Comp}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                     \quad \forall nhs`

:math:`0 \leq ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                                  \quad \forall nhz`

:math:`-\overline{ENF}_{nijc} \leq  ef_{nij}  \leq \overline{ENF}_{nijc}                                   \quad \forall nijc`

:math:`-\overline{HNF}_{nijc} \leq  hf_{nij}  \leq \overline{HNF}_{nijc}                                   \quad \forall nijc`