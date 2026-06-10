.. _parameters:

Parameters
==========

Parameters are the fixed input values that define the characteristics of the energy system being modeled. They are read from the input data files and built in ``oM_InputData.py``, where they are stored as plain dictionary entries under ``model.Par`` (keyed by the parameter name). They are **not** Pyomo ``Param`` components and are **not** defined in ``oM_ModelFormulation.py``; the formulation only reads them. Many keys are built dynamically by prefixing a data-file column name with its sector tag (``pEleGen``, ``pHydGen``, ``pEleDem``, ``pEleRet``, ...), so almost every key carries an ``Ele`` or ``Hyd`` sector prefix. In the mathematical notation, parameters are written in **uppercase** letters.

The "Key" column below gives the exact ``model.Par`` dictionary key.

.. note::

   This page covers the core electricity/hydrogen parameters. The heat sector
   (``pHeat*``), the investment layer (``pEleGenInvestCost`` / ``pHydGenInvestCost``,
   ``pDiscountFactor``, ...) and the option/feature flags (``pOptInd*``,
   ``pParGreenH2Matching``, ``pParBalanceMode``, ...) add their own. See
   :doc:`heat-sector` and :doc:`features-and-modes`.

General & Time
--------------

These parameters define the temporal structure and general constants for the model.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}`
     - Duration of each time step
     - h
     - ``pDuration``
   * - :math:`\pfactorone`
     - A utility conversion factor (e.g., 1,000)
     - -
     - ``factor1``
   * - :math:`\pfactortwo`
     - A utility conversion factor (e.g., 100)
     - -
     - ``factor2``
   * - :math:`\pdiscountrate_{\periodindex}`
     - Annual discount rate read from the parameter file; the derived per-period discount factor is ``pDiscountFactor``
     - %
     - ``pParAnnualDiscountRate``

Market & Costs
--------------

These parameters define the economic environment, including energy prices, tariffs, and other costs.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Cost of electricity purchased from a trader
     - €/MWh
     - ``pVarEnergyCost``
   * - :math:`\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Price of electricity sold to a trader
     - €/MWh
     - ``pVarEnergyPrice``
   * - :math:`\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Cost of hydrogen purchased from a trader (hydrogen uses the same shared key as electricity, indexed over both sectors' retailers)
     - €/kgH2
     - ``pVarEnergyCost``
   * - :math:`\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Price of hydrogen sold to a trader (shared key, see above)
     - €/kgH2
     - ``pVarEnergyPrice``
   * - :math:`\pelemarketbuyingratio_{\eletraderindex}`
     - Ratio for electricity purchases
     - -
     - ``pEleRetBuyingRatio``
   * - :math:`\pelemarketsellingratio_{\eletraderindex}`
     - Ratio for electricity sales
     - -
     - ``pEleRetSellingRatio``
   * - :math:`\pelemarketcertrevenue_{\eletraderindex}`
     - Export incentive paid per exported kWh (the per-kWh revenue term)
     - €/kWh
     - ``pEleRetIncentive``
   * - :math:`\pelemarketpassthrough_{\eletraderindex}`
     - Pass-through fee added to the buy price (påslag)
     - €/kWh
     - ``pEleRetPaslag``
   * - :math:`\pelemarketmoms_{\eletraderindex}`
     - Value-added tax (moms) multiplier for electricity
     - -
     - ``pEleRetMoms``
   * - :math:`\pelemarketnetfee_{\eletraderindex}`
     - Per-kWh network transfer fee (överföringsavgift)
     - €/kWh
     - ``pEleRetOverforingsavgift``
   * - :math:`\pelemarketnetfee_{\eletraderindex}`
     - Fixed monthly network connection fee (fast avgift)
     - €/month
     - ``pEleRetFastavgift``
   * - :math:`\pelemarketnetfee_{\eletraderindex}`
     - Per-kWh electricity energy tax
     - €/kWh
     - ``pEleRetEnergyTax``
   * - :math:`\pelemarkettariff_{\eletraderindex}`
     - Capacity-based power tariff (demand charge)
     - €/kW
     - ``pEleRetPowerTariff``
   * - :math:`\pelemaxmarketbuy_{\traderindex}`
     - Maximum electricity purchase from a retailer
     - kWh
     - ``pEleRetMaximumEnergyBuy``
   * - :math:`\pelemaxmarketsell_{\traderindex}`
     - Maximum electricity sale to a retailer
     - kWh
     - ``pEleRetMaximumEnergySell``
   * - :math:`\pfactortwo`
     - A large number for big-M constraints
     - -
     - ``factor2``
   * - :math:`CF_g, CV_g`
     - Fixed and variable operating cost of an electricity generator (hydrogen uses ``pHydGen...``)
     - €/h, €/kWh
     - ``pEleGenConstantVarCost``, ``pEleGenLinearVarCost``
   * - :math:`CSU_g, CSD_g`
     - Startup and shutdown cost of an electricity unit (hydrogen uses ``pHydGen...``)
     - €
     - ``pEleGenStartUpCost``, ``pEleGenShutDownCost``

.. note::

   **Peak-hour discount factors (optional retailer columns).** When the model
   computes the demand-charge peaks, it compares the grid import against an
   "adjusted import": the import is scaled by a night/day buy factor and, for a
   retailer with no demand, a fixed addend is added so an idle connection still
   registers a baseline. The night window itself is set per retailer by
   ``StartNightTime`` / ``EndNightTime``. The four factors can be set per retailer
   with the optional columns ``PeakNightBuyFactor``, ``PeakDayBuyFactor``,
   ``PeakNightAddend`` and ``PeakDayAddend`` in the electricity-retail data (read as
   ``pEleRetPeakNightBuyFactor`` and so on). If a column is absent the factor falls
   back to a default that depends on the tariff type -- Hourly uses ``1, 1, 1, 1``
   and Daily uses ``0.5, 1, 2, 5`` -- so a case without these columns is unchanged.

Asset Performance & Limits
--------------------------

These parameters define the operational characteristics, capacities, and limitations of generation and storage assets.

**Generation**
~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}` / :math:`\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Max/min electricity generation capacity
     - kWh
     - ``pEleMaxPower``, ``pEleMinPower``
   * - :math:`\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}` / :math:`\phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Max/min hydrogen generation capacity
     - kgH2
     - ``pHydMaxPower``, ``pHydMinPower``
   * - :math:`\widehat{EP}_{neg}`
     - Last market position update (Elec Gen)
     - kWh
     - ``pVarPositionGeneration``
   * - :math:`\widehat{HP}_{nhg}`
     - Last market position update (Hyd Gen)
     - kWh
     - ``pVarPositionGeneration``
   * - :math:`\overline{EC}^{comp}_{nhs}`
     - Max elec consumption of a compressor
     - kWh
     - ``pEleGenMaxCompressorConsumption``
   * - :math:`\phydgenstandbypower_{\genindex}`
     - Electricity drawn by an electrolyzer in the standby state (column
       ``StandByPower`` of the hydrogen-generation data)
     - kW
     - ``pHydGenStandByPower``
   * - :math:`\phydgenstandbystatus_{\genindex}`
     - Electrolyzer has standby capability (column ``StandByStatus``; enables the
       three-state on/standby/off model)
     - p.u.
     - ``pHydGenStandByStatus``
   * - :math:`PF_{he}`
     - Production function (Elec from H2)
     - kWh/kgH2
     - ``pHydGenProductionFunction``
   * - :math:`PF_{ehk}`
     - Production function (H2 from Elec)
     - kgH2/kWh
     - ``pEleGenProductionFunction``

**Ramping and Commitment**
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`RU_t, RD_t`
     - Max ramp-up/down rate of an electricity unit
     - kW/h
     - ``pEleGenRampUp``, ``pEleGenRampDown``
   * - :math:`RC^{+}_{hz}, RC^{-}_{hz}`
     - Max ramp-up/down rate of a hydrogen unit
     - kgH2/h
     - ``pHydGenRampUp``, ``pHydGenRampDown``
   * - :math:`TU_t, TD_t`
     - Minimum up-time and down-time of an electricity unit
     - h
     - ``pEleGenUpTime``, ``pEleGenDownTime``

**Storage**
~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\overline{EC}_{neg}` / :math:`\underline{EC}_{neg}`
     - Max/min electricity charging rate
     - kWh
     - ``pEleMaxCharge``, ``pEleMinCharge``
   * - :math:`\widehat{EC}_{neg}`
     - Last market position update (Elec Consumption)
     - kWh
     - ``pVarPositionConsumption``
   * - :math:`\overline{HC}_{nhg}` / :math:`\underline{HC}_{nhg}`
     - Max/min hydrogen charging rate
     - kgH2
     - ``pHydMaxCharge``, ``pHydMinCharge``
   * - :math:`\widehat{HC}_{nhg}`
     - Last market position update (Hyd Consumption)
     - kgH2
     - ``pVarPositionConsumption``
   * - :math:`\overline{EI}_{neg}` / :math:`\underline{EI}_{neg}`
     - Max/min electricity state-of-charge
     - kWh
     - ``pEleMaxStorage``, ``pEleMinStorage``
   * - :math:`\overline{HI}_{nhg}` / :math:`\underline{HI}_{nhg}`
     - Max/min hydrogen state-of-charge
     - kgH2
     - ``pHydMaxStorage``, ``pHydMinStorage``
   * - :math:`\overline{EEO}_{neg}` / :math:`\underline{EEO}_{neg}`
     - Max/min electricity outflow
     - kW
     - ``pEleMaxOutflows``, ``pEleMinOutflows``
   * - :math:`\overline{HEO}_{nhg}` / :math:`\underline{HEO}_{nhg}`
     - Max/min hydrogen outflow
     - kgH2
     - ``pHydMaxOutflows``, ``pHydMinOutflows``
   * - :math:`\overline{EEI}_{neg}` / :math:`\underline{EEI}_{neg}`
     - Max/min electricity inflow
     - kW
     - ``pEleMaxInflows``, ``pEleMinInflows``
   * - :math:`\overline{HEI}_{nhg}` / :math:`\underline{HEI}_{nhg}`
     - Max/min hydrogen inflow
     - kgH2
     - ``pHydMaxInflows``, ``pHydMinInflows``
   * - :math:`EF_e` / :math:`EF_h`
     - Round-trip efficiency (Elec/H2)
     - p.u.
     - ``pEleGenEfficiency`` / ``pHydGenEfficiency``
   * - :math:`\pelestoragecycle`
     - Storage cycle length (time steps) for electricity
     - h
     - ``pEleCycleTimeStep``
   * - :math:`\phydstoragecycle`
     - Storage cycle length (time steps) for hydrogen
     - h
     - ``pHydCycleTimeStep``
   * - :math:`\pelestorageoutflowcycle`
     - Outflow cycle length (time steps) for electricity storage
     - h
     - ``pEleOutflowsTimeStep``
   * - :math:`\phydstorageoutflowcycle`
     - Outflow cycle length (time steps) for hydrogen storage
     - h
     - ``pHydOutflowsTimeStep``
   * - :math:`\peleconscompress`
     - Electricity consumption of a compressor (see ``pEleGenMaxCompressorConsumption`` in the Generation table)
     - kWh
     - ``pEleGenMaxCompressorConsumption``

Ancillary Services
~~~~~~~~~~~~~~~~~~

Parameters related to grid support services.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`URA^{FCRD}_{n}, DRA^{FCRD}_{n}`
     - Up/down activation of FCR-D (disturbance reserve)
     - p.u.
     - ``pOperatingReserveActivation_FCRD_Up``, ``pOperatingReserveActivation_FCRD_Down``
   * - :math:`URA^{FCRN}_{n}, DRA^{FCRN}_{n}`
     - Up/down activation of FCR-N (normal reserve)
     - p.u.
     - ``pOperatingReserveActivation_FCRN_Up``, ``pOperatingReserveActivation_FCRN_Down``
   * - :math:`\pi^{FCRD}_{n}, \pi^{FCRN}_{n}`
     - Reserve clearing price per product
     - €/kW
     - ``pOperatingReservePrice_FCRD_Up`` / ``..._FCRD_Down`` / ``..._FCRN_Up`` / ``..._FCRN_Down``
   * - :math:`R^{FCRD}_{n}, R^{FCRN}_{n}`
     - Reserve requirement per product
     - kW
     - ``pOperatingReserveRequire_FCRD_Up`` / ``..._FCRD_Down`` / ``..._FCRN_Up`` / ``..._FCRN_Down``
   * - :math:`\pgennofcrd_{\genindex}, \pgennofcrn_{\genindex}`
     - Electricity unit not participating in FCR-D / FCR-N (1 = no, the default; 0 =
       the unit may bid)
     - p.u.
     - ``pEleGenNoFCRD``, ``pEleGenNoFCRN``
   * - :math:`\pelegenendurancefcrd_{\storageindex}, \pelegenendurancefcrn_{\storageindex}`
     - FCR-D / FCR-N endurance requirement of an electricity storage unit
     - min
     - ``pEleGenEnduranceFCRD``, ``pEleGenEnduranceFCRN``
   * - :math:`\phydgennofcrd_{\genindex}, \phydgennofcrn_{\genindex}`
     - Electrolyser not participating in FCR-D / FCR-N (read from the
       hydrogen-generation columns ``NoFCRD`` / ``NoFCRN``; 1 = no, the default, so
       cases without the columns are unchanged)
     - p.u.
     - ``pHydGenNoFCRD``, ``pHydGenNoFCRN``
   * - :math:`\phydgenendurancefcrd_{\genindex}, \phydgenendurancefcrn_{\genindex}`
     - FCR-D / FCR-N endurance requirement of an electrolyser (defaults to 0 when the
       hydrogen-generation columns ``EnduranceFCRD`` / ``EnduranceFCRN`` are absent)
     - min
     - ``pHydGenEnduranceFCRD``, ``pHydGenEnduranceFCRN``

Network
~~~~~~~

Parameters related to network infrastructure.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\pelemaxrealpower_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}` / :math:`\peleminrealpower_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}`
     - Max/min electricity network flow
     - kWh
     - ``pEleNetTTC``, ``pEleNetTTCBck``
   * - :math:`\phydmaxflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}` / :math:`\phydminflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}`
     - Max/min hydrogen network flow
     - kWh
     - ``pHydNetTTC``, ``pHydNetTTCBck``
   * - :math:`\pelereactanceline_{\busindexa,\busindexb,\circuitindex}`
     - Reactance of an electricity line
     - p.u.
     - ``pEleNetReactance``

Demand
~~~~~~

Parameters related to energy demand.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\peledemflexible`
     - Flag for flexible electricity demand
     - -
     - ``pEleDemFlexible``
   * - :math:`\alpha^{e,flex}`
     - Flexible fraction of the demand (sets the shift band as a share of peak demand)
     - -
     - ``pEleDemFlexPercent``
   * - :math:`\peledemshiftedsteps`
     - Number of time steps over which demand may be shifted
     - -
     - ``pEleDemShiftedSteps``

EV Specific
~~~~~~~~~~~

Parameters specific to Electric Vehicle (EV) modeling.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Key**
   * - :math:`\pvarfixedavailability`
     - Time-varying availability of the EV for grid services (0 while driving)
     - -
     - ``pVarFixedAvailability``
   * - :math:`\peleminstoragestart`
     - Minimum battery state-of-charge required at departure
     - p.u.
     - ``pEleGenMinSoCDepart``

Heat sector
-----------

.. list-table::
   :widths: 50 20 30
   :header-rows: 1

   * - **Description**
     - **Unit**
     - **Key**
   * - Heat generator maximum power
     - kW
     - ``pHeatGenMaxPower``
   * - Heat generator running cost
     - €/kWh
     - ``pHeatGenCost``
   * - Heat-pump coefficient of performance (heat / electricity)
     - -
     - ``pHeatPumpCOP``
   * - Heat-to-power maximum heat input / efficiency
     - kW, -
     - ``pHeatToEleMaxHeat`` / ``pHeatToEleEff``
   * - Thermal store maximum energy / round-trip efficiency / initial level
     - kWh, -, kWh
     - ``pHeatStoMax`` / ``pHeatStoEff`` / ``pHeatStoInitial``
   * - Heat demand / heat-not-served cost
     - kW, €/kWh
     - ``pHeatDemand`` / ``pHeatNSCost``

Investment and options
----------------------

.. list-table::
   :widths: 50 20 30
   :header-rows: 1

   * - **Description**
     - **Unit**
     - **Key**
   * - Annualised investment cost of a candidate (electricity / hydrogen)
     - €
     - ``pEleGenInvestCost`` / ``pHydGenInvestCost``
   * - Build a candidate as a binary (vs continuous fraction)
     - 0/1
     - ``pEleGenBinaryInvestment`` / ``pHydGenBinaryInvestment``
   * - Build-fraction lower / upper bound
     - -
     - ``pEleGenInvestmentLo`` / ``...Up`` (and ``pHyd...``)
   * - Period discount factor
     - -
     - ``pDiscountFactor``
   * - Feature flags (unit commitment, ramps, single node, community, green-H2 matching, balance mode, ...)
     - 0/1 / text
     - ``pOptIndBin*``, ``pParGreenH2Matching``, ``pParBalanceMode``

See :doc:`heat-sector` and :doc:`features-and-modes`.
