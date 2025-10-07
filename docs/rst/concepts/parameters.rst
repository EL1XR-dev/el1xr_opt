.. _parameters:

Parameters
==========

Parameters are the fixed input values that define the characteristics of the energy system being modeled. They are defined in ``oM_ModelFormulation.py`` and are typically derived from the input data files. In the mathematical notation, they are written in **uppercase** letters.

General & Time
--------------

These parameters define the temporal structure and general constants for the model.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}`
     - Duration of each time step
     - h
     - ``pDuration``
   * - :math:`\pfactorone`
     - A utility conversion factor (e.g., 1,000)
     - -
     - ``factor1``
   * - :math:`\pdiscountrate_{\periodindex}`
     - Annual discount rate for NPV calculations
     - %
     - ``pParDiscountRate``

Market & Costs
--------------

These parameters define the economic environment, including energy prices, tariffs, and other costs.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Cost of electricity purchased from a trader
     - €/MWh
     - ``pVarEnergyCost``
   * - :math:`\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Price of electricity sold to a trader
     - €/MWh
     - ``pVarEnergyPrice``
   * - :math:`\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Cost of hydrogen purchased from a trader
     - €/kgH2
     - ``pHydrogenCost``
   * - :math:`\phydsellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`
     - Price of hydrogen sold to a trader
     - €/kgH2
     - ``pHydrogenPrice``
   * - :math:`\pelemarketbuyingratio_{\eletraderindex}`
     - Ratio for electricity purchases
     - -
     - ``pEleRetBuyingRatio``
   * - :math:`\pelemarketsellingratio_{\eletraderindex}`
     - Ratio for electricity sales
     - -
     - ``pEleRetSellingRatio``
   * - :math:`\pelemarketcertrevenue_{\eletraderindex}`
     - Revenue from electricity certificates
     - €/kWh
     - ``pEleRetelcertifikat``
   * - :math:`\pelemarketpassthrough_{\eletraderindex}`
     - Pass-through fee for electricity
     - €/kWh
     - ``pEleRetpaslag``
   * - :math:`\pelemarketmoms_{\eletraderindex}`
     - Value-added tax (moms) for electricity
     - -
     - ``pEleRetmoms``
   * - :math:`\pelemarketnetfee_{\eletraderindex}`
     - Network usage fee for electricity
     - €/kWh
     - ``pEleRetnetavgift``
   * - :math:`\pelemarkettariff_{\eletraderindex}`
     - Capacity-based tariff
     - €/kW
     - ``pEleRetTariff``
   * - :math:`CF_g, CV_g`
     - Fixed and variable costs of a generator
     - €/h, €/kWh
     - ``pGenConstantVarCost``, ``pGenLinearVarCost``
   * - :math:`CSU_g, CSD_g`
     - Startup and shutdown cost of a unit
     - €
     - ``pGenStartUpCost``, ``pGenShutDownCost``
   * - :math:`CRU_h, CRD_h`
     - Ramping cost for a hydrogen unit
     - €/kWh
     - ``pGenRampUpCost``, ``pGenRampDownCost``

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
     - **Pyomo Component**
   * - :math:`\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Maximum available electricity production
     - kWh
     - ``pMaxEleProduction``
   * - :math:`\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Minimum stable electricity production
     - kWh
     - ``pMinEleProduction``
   * - :math:`\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Maximum available hydrogen production
     - kgH2
     - ``pMaxHydProduction``
   * - :math:`\phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}`
     - Minimum stable hydrogen production
     - kgH2
     - ``pMinHydProduction``
   * - :math:`\overline{EP}_{neg}` / :math:`\underline{EP}_{neg}`
     - Max/min electricity generation capacity
     - kWh
     - ``pMaxPower``, ``pMinPower``
   * - :math:`\widehat{EP}_{neg}`
     - Last market position update (Elec Gen)
     - kWh
     - ``pVarPositionGeneration``
   * - :math:`\overline{HP}_{nhg}` / :math:`\underline{HP}_{nhg}`
     - Max/min hydrogen generation capacity
     - kgH2
     - ``pMaxPower``, ``pMinPower``
   * - :math:`\widehat{HP}_{nhg}`
     - Last market position update (Hyd Gen)
     - kWh
     - ``pVarPositionGeneration``
   * - :math:`\overline{EC}^{comp}_{nhs}`
     - Max elec consumption of a compressor
     - kWh
     - ``pGenMaxCompressorConsumption``
   * - :math:`\overline{EC}^{standby}_{nhz}`
     - Max elec consumption of an electrolyzer at standby
     - kWh
     - ``pGenStandByPower``
   * - :math:`PF_{he}`
     - Production function (Elec from H2)
     - kWh/kgH2
     - ``pGenProductionFunction``
   * - :math:`PF1_{ehk}` / :math:`PF2_{ehk}`
     - Piecewise production function (H2 from Elec)
     - kgH2/kWh
     - ``pGenProductionFunction``, ``pGenProductionFunctionSlope``

**Ramping and Commitment**
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`RU_t, RD_t`
     - Max ramp-up/down rate of an electric unit
     - kW/h
     - ``pGenRampUp``, ``pGenRampDown``
   * - :math:`RC^{+}_{hz}, RC^{-}_{hz}`
     - Max ramp-up/down rate of a hydrogen unit
     - kgH2/h
     - ``pGenRampUp``, ``pGenRampDown``
   * - :math:`TU_t, TD_t`
     - Minimum up-time and down-time
     - h
     - ``pGenUpTime``, ``pGenDownTime``

**Storage**
~~~~~~~~~~~

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\overline{EC}_{neg}` / :math:`\underline{EC}_{neg}`
     - Max/min electricity charging rate
     - kWh
     - ``pMaxCharge``, ``pMinCharge``
   * - :math:`\widehat{EC}_{neg}`
     - Last market position update (Elec Consumption)
     - kWh
     - ``pVarPositionConsumption``
   * - :math:`\overline{HC}_{nhg}` / :math:`\underline{HC}_{nhg}`
     - Max/min hydrogen charging rate
     - kgH2
     - ``pMaxCharge``, ``pMinCharge``
   * - :math:`\widehat{HC}_{nhg}`
     - Last market position update (Hyd Consumption)
     - kgH2
     - ``pVarPositionConsumption``
   * - :math:`\overline{EI}_{neg}` / :math:`\underline{EI}_{neg}`
     - Max/min electricity state-of-charge
     - kWh
     - ``pMaxStorage``, ``pMinStorage``
   * - :math:`\overline{HI}_{nhg}` / :math:`\underline{HI}_{nhg}`
     - Max/min hydrogen state-of-charge
     - kgH2
     - ``pMaxStorage``, ``pMinStorage``
   * - :math:`\overline{EEO}_{neg}` / :math:`\underline{EEO}_{neg}`
     - Max/min electricity outflow
     - kW
     - ``pMaxOutflows``, ``pMinOutflows``
   * - :math:`\overline{HEO}_{nhg}` / :math:`\underline{HEO}_{nhg}`
     - Max/min hydrogen outflow
     - kgH2
     - ``pMaxOutflows``, ``pMinOutflows``
   * - :math:`\overline{EEI}_{neg}` / :math:`\underline{EEI}_{neg}`
     - Max/min electricity inflow
     - kW
     - ``pMaxInflows``, ``pMinInflows``
   * - :math:`\overline{HEI}_{nhg}` / :math:`\underline{HEI}_{nhg}`
     - Max/min hydrogen inflow
     - kgH2
     - ``pMaxInflows``, ``pMinInflows``
   * - :math:`EF_e` / :math:`EF_h`
     - Round-trip efficiency (Elec/H2)
     - p.u.
     - ``pGenEfficiency``

Ancillary Services
~~~~~~~~~~~~~~~~~~

Parameters related to grid support services.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`URA^{SR}_{n}, DRA^{SR}_{n}`
     - Up/down activation of Synchronous Reserve
     - p.u.
     - ``pOperatingReserveActivation_Up_SR``, ``pOperatingReserveActivation_Down_SR``
   * - :math:`URA^{TR}_{n}, DRA^{TR}_{n}`
     - Up/down activation of Tertiary Reserve
     - p.u.
     - ``pOperatingReserveActivation_Up_TR``, ``pOperatingReserveActivation_Down_TR``

Network
~~~~~~~

Parameters related to network infrastructure.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\overline{ENF}_{nijc}` / :math:`\underline{ENF}_{nijc}`
     - Max/min electricity network flow
     - MWh
     - ``pEleNetTTC``, ``pEleNetTTCBck``
   * - :math:`\overline{HNF}_{nijc}` / :math:`\underline{HNF}_{nijc}`
     - Max/min hydrogen network flow
     - MWh
     - ``pHydNetTTC``, ``pHydNetTTCBck``
   * - :math:`\overline{X}_{nijc}`
     - Reactance of an electricity line
     - p.u.
     - ``pEleNetReactance``
