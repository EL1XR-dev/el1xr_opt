.. _parameters:

Parameters
==========

Parameters are the fixed input values that define the characteristics of the energy system being modeled. They are defined in ``oM_ModelFormulation.py`` and are typically derived from the input data files. In the mathematical notation, they are written in **uppercase** letters.

General & Time
--------------

These parameters define the temporal structure and general constants for the model.

*   **Symbol**: :math:`\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}`
*   **Description**: Duration of each time step.
*   **Unit**: h
*   **Pyomo Component**: ``pDuration``

*   **Symbol**: :math:`\pfactorone`
*   **Description**: A utility conversion factor, typically used for scaling (e.g., 1,000 to convert from kW to MW).
*   **Unit**: -
*   **Pyomo Component**: ``factor1``

*   **Symbol**: :math:`\pdiscountrate_{\periodindex}`
*   **Description**: The annual discount rate used to calculate the net present value of future costs and revenues.
*   **Unit**: %
*   **Pyomo Component**: ``pParDiscountRate``


Market & Costs
--------------

These parameters define the economic environment, including energy prices, tariffs, and other costs.

*   **Symbol**: :math:`\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
*   **Description**: Cost of electricity purchased from an external market or trader.
*   **Unit**: €/MWh
*   **Pyomo Component**: ``pVarEnergyCost``

*   **Symbol**: :math:`\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
*   **Description**: Price received for electricity sold to an external market or trader.
*   **Unit**: €/MWh
*   **Pyomo Component**: ``pVarEnergyPrice``

*   **Symbol**: :math:`\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
*   **Description**: Cost of hydrogen purchased from an external market.
*   **Unit**: €/kgH2
*   **Pyomo Component**: ``pHydrogenCost``

*   **Symbol**: :math:`\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
*   **Description**: Price received for hydrogen sold to an external market.
*   **Unit**: €/kgH2
*   **Pyomo Component**: ``pHydrogenPrice``

*   **Symbol**: :math:`\pelemarketbuyingratio_{\eletraderindex}`
*   **Description**: A ratio applied to electricity purchases from a specific market region.
*   **Unit**: -
*   **Pyomo Component**: ``pEleRetBuyingRatio``

*   **Symbol**: :math:`\pelemarketsellingratio_{\eletraderindex}`
*   **Description**: A ratio applied to electricity sales to a specific market region.
*   **Unit**: -
*   **Pyomo Component**: ``pEleRetSellingRatio``

*   **Symbol**: :math:`\pelemarketcertrevenue_{\eletraderindex}`
*   **Description**: Revenue from electricity certificates in a specific market region.
*   **Unit**: €/kWh
*   **Pyomo Component**: ``pEleRetelcertifikat``

*   **Symbol**: :math:`\pelemarketpassthrough_{\eletraderindex}`
*   **Description**: A pass-through fee for electricity in a specific market region.
*   **Unit**: €/kWh
*   **Pyomo Component**: ``pEleRetpaslag``

*   **Symbol**: :math:`\pelemarketmoms_{\eletraderindex}`
*   **Description**: Value-added tax (moms) for electricity in a specific market region.
*   **Unit**: -
*   **Pyomo Component**: ``pEleRetmoms``

*   **Symbol**: :math:`\pelemarketnetfee_{\eletraderindex}`
*   **Description**: Network usage fee for electricity in a specific market region.
*   **Unit**: €/kWh
*   **Pyomo Component**: ``pEleRetnetavgift``

*   **Symbol**: :math:`\pelemarkettariff_{\eletraderindex}`
*   **Description**: A capacity-based tariff for a specific electricity market region.
*   **Unit**: €/kW
*   **Pyomo Component**: ``pEleRetTariff``


Asset Performance & Limits
--------------------------

These parameters define the operational characteristics, capacities, and limitations of generation and storage assets.

General Generation
~~~~~~~~~~~~~~~~~~

*   **Symbol**: :math:`\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
*   **Description**: Maximum available electricity production from a generator, considering availability factors.
*   **Unit**: kWh
*   **Pyomo Component**: ``pMaxEleProduction``

*   **Symbol**: :math:`\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
*   **Description**: Minimum stable electricity production from a generator when committed.
*   **Unit**: kWh
*   **Pyomo Component**: ``pMinEleProduction``

*   **Symbol**: :math:`\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
*   **Description**: Maximum available hydrogen production from a generator (e.g., electrolyzer).
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxHydProduction``

*   **Symbol**: :math:`\phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
*   **Description**: Minimum stable hydrogen production from a generator when committed.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMinHydProduction``

*   **Symbol**: :math:`\overline{EP}_{neg}` / :math:`\underline{EP}_{neg}`
*   **Description**: Maximum and minimum electricity generation capacity of a generator.
*   **Unit**: kWh
*   **Pyomo Component**: ``pMaxPower``, ``pMinPower``

*   **Symbol**: :math:`\overline{HP}_{nhg}` / :math:`\underline{HP}_{nhg}`
*   **Description**: Maximum and minimum hydrogen generation capacity of a generator.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxPower``, ``pMinPower``

*   **Symbol**: :math:`CF_g, CV_g`
*   **Description**: Fixed (no-load) and variable (marginal) cost of an electricity generator. Variable cost includes fuel, O&M, and emission costs.
*   **Unit**: €/h, €/kWh
*   **Pyomo Component**: ``pGenConstantVarCost``, ``pGenLinearVarCost``

*   **Symbol**: :math:`PF_{he}`
*   **Description**: Production function (efficiency) for generating electricity from hydrogen (e.g., in a fuel cell).
*   **Unit**: kWh/kgH2
*   **Pyomo Component**: ``pGenProductionFunction``

*   **Symbol**: :math:`PF1_{ehk}` / :math:`PF2_{ehk}`
*   **Description**: Intercept and slope for the piecewise linear production function of hydrogen from electricity (e.g., in an electrolyzer).
*   **Unit**: kgH2/kWh
*   **Pyomo Component**: ``pGenProductionFunction``, ``pGenProductionFunctionSlope``


Ramping and Commitment
~~~~~~~~~~~~~~~~~~~~~~

*   **Symbol**: :math:`RU_t, RD_t`
*   **Description**: Maximum ramp-up and ramp-down rate of an electricity thermal unit.
*   **Unit**: kW/h
*   **Pyomo Component**: ``pGenRampUp``, ``pGenRampDown``

*   **Symbol**: :math:`RC^{+}_{hz}, RC^{-}_{hz}`
*   **Description**: Maximum ramp-up and ramp-down rate of a hydrogen unit.
*   **Unit**: kgH2/h
*   **Pyomo Component**: ``pGenRampUp``, ``pGenRampDown``

*   **Symbol**: :math:`TU_t, TD_t`
*   **Description**: Minimum up-time and down-time for a dispatchable electricity thermal unit.
*   **Unit**: h
*   **Pyomo Component**: ``pGenUpTime``, ``pGenDownTime``

*   **Symbol**: :math:`CSU_g, CSD_g`
*   **Description**: Cost incurred for starting up and shutting down a dispatchable electricity unit.
*   **Unit**: €
*   **Pyomo Component**: ``pGenStartUpCost``, ``pGenShutDownCost``

*   **Symbol**: :math:`CRU_h, CRD_h`
*   **Description**: Cost associated with ramping a hydrogen unit up or down.
*   **Unit**: €/kWh
*   **Pyomo Component**: ``pGenRampUpCost``, ``pGenRampDownCost``


Storage
~~~~~~~

*   **Symbol**: :math:`\overline{EC}_{neg}` / :math:`\underline{EC}_{neg}`
*   **Description**: Maximum and minimum charging rate of an electricity storage system (ESS).
*   **Unit**: kWh
*   **Pyomo Component**: ``pMaxCharge``, ``pMinCharge``

*   **Symbol**: :math:`\overline{HC}_{nhg}` / :math:`\underline{HC}_{nhg}`
*   **Description**: Maximum and minimum charging rate of a hydrogen storage system.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxCharge``, ``pMinCharge``

*   **Symbol**: :math:`\overline{EI}_{neg}` / :math:`\underline{EI}_{neg}`
*   **Description**: Maximum and minimum state-of-charge (inventory level) of an ESS.
*   **Unit**: kWh
*   **Pyomo Component**: ``pMaxStorage``, ``pMinStorage``

*   **Symbol**: :math:`\overline{HI}_{nhg}` / :math:`\underline{HI}_{nhg}`
*   **Description**: Maximum and minimum state-of-charge (inventory level) of a hydrogen storage system.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxStorage``, ``pMinStorage``

*   **Symbol**: :math:`\overline{EEO}_{neg}` / :math:`\underline{EEO}_{neg}`
*   **Description**: Maximum and minimum energy outflow from an ESS (e.g., for EV driving).
*   **Unit**: kW
*   **Pyomo Component**: ``pMaxOutflows``, ``pMinOutflows``

*   **Symbol**: :math:`\overline{HEO}_{nhg}` / :math:`\underline{HEO}_{nhg}`
*   **Description**: Maximum and minimum hydrogen outflow from a storage system.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxOutflows``, ``pMinOutflows``

*   **Symbol**: :math:`\overline{EEI}_{neg}` / :math:`\underline{EEI}_{neg}`
*   **Description**: Maximum and minimum energy inflow to an ESS.
*   **Unit**: kW
*   **Pyomo Component**: ``pMaxInflows``, ``pMinInflows``

*   **Symbol**: :math:`\overline{HEI}_{nhg}` / :math:`\underline{HEI}_{nhg}`
*   **Description**: Maximum and minimum hydrogen inflow to a storage system.
*   **Unit**: kgH2
*   **Pyomo Component**: ``pMaxInflows``, ``pMinInflows``

*   **Symbol**: :math:`EF_e`
*   **Description**: Round-trip efficiency of an electricity ESS (charge/discharge cycle).
*   **Unit**: p.u.
*   **Pyomo Component**: ``pGenEfficiency``

*   **Symbol**: :math:`EF_h`
*   **Description**: Round-trip efficiency of a hydrogen ESS.
*   **Unit**: p.u.
*   **Pyomo Component**: ``pGenEfficiency``


Ancillary Services & Network
----------------------------

Parameters related to grid support services and network infrastructure.

Ancillary Services
~~~~~~~~~~~~~~~~~~

*   **Symbol**: :math:`URA^{SR}_{n}, DRA^{SR}_{n}`
*   **Description**: Upward and downward activation of Synchronous Reserve (SR).
*   **Unit**: p.u.
*   **Pyomo Component**: ``pOperatingReserveActivation_Up_SR``, ``pOperatingReserveActivation_Down_SR``

*   **Symbol**: :math:`URA^{TR}_{n}, DRA^{TR}_{n}`
*   **Description**: Upward and downward activation of Tertiary Reserve (TR).
*   **Unit**: p.u.
*   **Pyomo Component**: ``pOperatingReserveActivation_Up_TR``, ``pOperatingReserveActivation_Down_TR``


Network
~~~~~~~

*   **Symbol**: :math:`\overline{ENF}_{nijc}` / :math:`\underline{ENF}_{nijc}`
*   **Description**: Maximum and minimum (forward and backward) flow capacity of an electricity network line.
*   **Unit**: MWh
*   **Pyomo Component**: ``pEleNetTTC``, ``pEleNetTTCBck``

*   **Symbol**: :math:`\overline{HNF}_{nijc}` / :math:`\underline{HNF}_{nijc}`
*   **Description**: Maximum and minimum (forward and backward) flow capacity of a hydrogen pipeline.
*   **Unit**: MWh
*   **Pyomo Component**: ``pHydNetTTC``, ``pHydNetTTCBck``

*   **Symbol**: :math:`\overline{X}_{nijc}`
*   **Description**: Reactance of an electricity transmission line, used in DC power flow calculations.
*   **Unit**: p.u.
*   **Pyomo Component**: ``pEleNetReactance``