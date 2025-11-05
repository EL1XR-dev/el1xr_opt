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
   * - :math:`\pdiscountfactor_{\periodindex}`
     - Discount factor for each period
     - -
     - ``pDiscountFactor``
   * - :math:`\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}`
     - Duration of each time step
     - h
     - ``pDuration``

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
   * - :math:`\pEleRetPowerTariff_{\eletraderindex}`
     - Tariff for peak power consumption
     - €/kW
     - ``pEleRetPowerTariff``
   * - :math:`\pEleRetMoms_{\eletraderindex}`
     - Value-added tax (VAT)
     - %
     - ``pEleRetMoms``
   * - :math:`\pEleRetOverforingsavgift_{\eletraderindex}`
     - Variable network fee
     - €/kWh
     - ``pEleRetOverforingsavgift``
   * - :math:`\pEleRetFastavgift_{\eletraderindex}`
     - Fixed network fee
     - €/month
     - ``pEleRetFastavgift``
   * - :math:`\pVarEnergyCost_{\periodindex,\scenarioindex,\timeindex}`
     - Cost of energy from the market
     - €/MWh
     - ``pVarEnergyCost``
   * - :math:`\pEleRetBuyingRatio_{\eletraderindex}`
     - Ratio for electricity purchases
     - -
     - ``pEleRetBuyingRatio``
   * - :math:`\pEleRetPaslag_{\eletraderindex}`
     - Pass-through fee for electricity
     - €/kWh
     - ``pEleRetPaslag``
   * - :math:`\pVarEnergyPrice_{\periodindex,\scenarioindex,\timeindex}`
     - Price of energy sold to the market
     - €/MWh
     - ``pVarEnergyPrice``
   * - :math:`\pEleRetSellingRatio_{\eletraderindex}`
     - Ratio for electricity sales
     - -
     - ``pEleRetSellingRatio``
   * - :math:`\pOperatingReservePriceFCRDUp_{\periodindex,\scenarioindex,\timeindex}`
     - Price for upward frequency containment reserve (FCR-D)
     - €/MW
     - ``pOperatingReservePrice_FCRD_Up``
   * - :math:`\pOperatingReservePriceFCRDDown_{\periodindex,\scenarioindex,\timeindex}`
     - Price for downward frequency containment reserve (FCR-D)
     - €/MW
     - ``pOperatingReservePrice_FCRD_Down``
   * - :math:`\pEleGenRetailer_{\eunitindex}`
     - Retailer associated with a generation unit
     - -
     - ``pEleGenRetailer``
   * - :math:`\pEleRetEnergyTax_{\eletraderindex}`
     - Energy tax
     - €/kWh
     - ``pEleRetEnergyTax``
   * - :math:`\pEleRetIncentive_{\eletraderindex}`
     - Incentive for selling electricity
     - €/kWh
     - ``pEleRetIncentive``
   * - :math:`\pEleGenLinearVarCost_{\eunitindex}`
     - Linear variable cost for electricity generation
     - €/MWh
     - ``pEleGenLinearVarCost``
   * - :math:`\pEleGenConstantVarCost_{\eunitindex}`
     - Constant variable cost for electricity generation
     - €
     - ``pEleGenConstantVarCost``
   * - :math:`\pEleGenStartUpCost_{\eunitindex}`
     - Start-up cost for an electricity generation unit
     - €
     - ``pEleGenStartUpCost``
   * - :math:`\pEleGenShutDownCost_{\eunitindex}`
     - Shutdown cost for an electricity generation unit
     - €
     - ``pEleGenShutDownCost``
   * - :math:`\pEleGenOMVariableCost_{\eunitindex}`
     - Variable O&M cost for electricity generation
     - €/MWh
     - ``pEleGenOMVariableCost``
   * - :math:`\pGenCO2EmissionCost_{\eunitindex}`
     - CO2 emission cost
     - €/tCO2
     - ``pGenCO2EmissionCost``
   * - :math:`\pEleGenLinearTerm_{\eunitindex}`
     - Linear term for electricity consumption cost
     - €/MWh
     - ``pEleGenLinearTerm``
   * - :math:`\pParENSCost`
     - Cost of energy not served (electricity)
     - €/MWh
     - ``pParENSCost``
   * - :math:`\pHydGenLinearVarCost_{\hunitindex}`
     - Linear variable cost for hydrogen generation
     - €/kg
     - ``pHydGenLinearVarCost``
   * - :math:`\pHydGenConstantVarCost_{\hunitindex}`
     - Constant variable cost for hydrogen generation
     - €
     - ``pHydGenConstantVarCost``
   * - :math:`\pHydGenStartUpCost_{\hunitindex}`
     - Start-up cost for a hydrogen generation unit
     - €
     - ``pHydGenStartUpCost``
   * - :math:`\pHydGenShutDownCost_{\hunitindex}`
     - Shutdown cost for a hydrogen generation unit
     - €
     - ``pHydGenShutDownCost``
   * - :math:`\pHydGenOMVariableCost_{\hunitindex}`
     - Variable O&M cost for hydrogen generation
     - €/kg
     - ``pHydGenOMVariableCost``
   * - :math:`\pHydGenLinearTerm_{\hunitindex}`
     - Linear term for hydrogen consumption cost
     - €/kg
     - ``pHydGenLinearTerm``
   * - :math:`\pParHNSCost`
     - Cost of hydrogen not served
     - €/kg
     - ``pParHNSCost``

Asset Performance & Limits
--------------------------

These parameters define the operational characteristics, capacities, and limitations of generation and storage assets.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\pEleRetMaxBuy_{\eletraderindex}`
     - Maximum electricity purchase from a retailer
     - kWh
     - ``pEleRetMaxBuy``
   * - :math:`\pEleRetMaxSell_{\eletraderindex}`
     - Maximum electricity sale to a retailer
     - kWh
     - ``pEleRetMaxSell``
   * - :math:`\pHydRetMaxBuy_{\hydtraderindex}`
     - Maximum hydrogen purchase from a retailer
     - kg
     - ``pHydRetMaxBuy``
   * - :math:`\pHydRetMaxSell_{\hydtraderindex}`
     - Maximum hydrogen sale to a retailer
     - kg
     - ``pHydRetMaxSell``
   * - :math:`\pEleDemFlexible_{\edemandindex}`
     - Flag indicating if electricity demand is flexible
     - -
     - ``pEleDemFlexible``
   * - :math:`\pEleDemShiftedSteps_{\edemandindex}`
     - Number of time steps for demand shifting
     - -
     - ``pEleDemShiftedSteps``
   * - :math:`\pVarMaxDemand_{\edemandindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum electricity demand
     - kWh
     - ``pVarMaxDemand``
   * - :math:`\pOperatingReserveRequireFCRDUp_{\periodindex,\scenarioindex,\timeindex}`
     - Requirement for upward frequency containment reserve (FCR-D)
     - MW
     - ``pOperatingReserveRequire_FCRD_Up``
   * - :math:`\pOperatingReserveRequireFCRDDown_{\periodindex,\scenarioindex,\timeindex}`
     - Requirement for downward frequency containment reserve (FCR-D)
     - MW
     - ``pOperatingReserveRequire_FCRD_Down``
   * - :math:`\pEleGenNoFCRD_{\eunitindex}`
     - Flag indicating if a unit can provide FCR-D
     - -
     - ``pEleGenNoFCRD``
   * - :math:`\pEleMaxPower_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum power output of an electricity unit
     - kW
     - ``pEleMaxPower``
   * - :math:`\pEleMinPower_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum power output of an electricity unit
     - kW
     - ``pEleMinPower``
   * - :math:`\pEleMinCharge_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum charging rate of an electricity storage unit
     - kW
     - ``pEleMinCharge``
   * - :math:`\pEleMaxCharge_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum charging rate of an electricity storage unit
     - kW
     - ``pEleMaxCharge``
   * - :math:`\pEleMaxStorage_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum storage capacity of an electricity storage unit
     - kWh
     - ``pEleMaxStorage``
   * - :math:`\pEleMaxPower2ndBlock_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum power output of the second block of a unit
     - kW
     - ``pEleMaxPower2ndBlock``
   * - :math:`\pEleMaxInflows_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum inflows for an electricity storage unit
     - kWh
     - ``pEleMaxInflows``
   * - :math:`\pEleMinStorage_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum storage level of an electricity storage unit
     - kWh
     - ``pEleMinStorage``
   * - :math:`\pEleMinInflows_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum inflows for an electricity storage unit
     - kWh
     - ``pEleMinInflows``
   * - :math:`\pHydMaxStorage_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum storage capacity of a hydrogen storage unit
     - kg
     - ``pHydMaxStorage``
   * - :math:`\pHydMaxPower2ndBlock_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum power output of the second block of a hydrogen unit
     - kg/h
     - ``pHydMaxPower2ndBlock``
   * - :math:`\pHydMaxInflows_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum inflows for a hydrogen storage unit
     - kg
     - ``pHydMaxInflows``
   * - :math:`\pHydMinStorage_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum storage level of a hydrogen storage unit
     - kg
     - ``pHydMinStorage``
   * - :math:`\pHydMinInflows_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum inflows for a hydrogen storage unit
     - kg
     - ``pHydMinInflows``
   * - :math:`\pEleCycleTimeStep_{\eunitindex}`
     - Cycle time step for electricity storage
     - h
     - ``pEleCycleTimeStep``
   * - :math:`\pEleInitialInventory_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Initial inventory of an electricity storage unit
     - kWh
     - ``pEleInitialInventory``
   * - :math:`\pEleGenEfficiency_discharge_{\eunitindex}`
     - Discharge efficiency of an electricity storage unit
     - -
     - ``pEleGenEfficiency_discharge``
   * - :math:`\pEleGenEfficiency_charge_{\eunitindex}`
     - Charge efficiency of an electricity storage unit
     - -
     - ``pEleGenEfficiency_charge``
   * - :math:`\pHydCycleTimeStep_{\hunitindex}`
     - Cycle time step for hydrogen storage
     - h
     - ``pHydCycleTimeStep``
   * - :math:`\pHydInitialInventory_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Initial inventory of a hydrogen storage unit
     - kg
     - ``pHydInitialInventory``
   * - :math:`\pHydGenEfficiency_{\hunitindex}`
     - Efficiency of a hydrogen unit
     - -
     - ``pHydGenEfficiency``
   * - :math:`\pHydGenProductionFunction_{\hunitindex}`
     - Production function for hydrogen generation
     - kg/kWh
     - ``pHydGenProductionFunction``
   * - :math:`\pEleGenProductionFunction_{\eunitindex}`
     - Production function for electricity generation from hydrogen
     - kWh/kg
     - ``pEleGenProductionFunction``
   * - :math:`\pEleMaxOutflows_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum outflows for an electricity storage unit
     - kWh
     - ``pEleMaxOutflows``
   * - :math:`\pEleMinOutflows_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum outflows for an electricity storage unit
     - kWh
     - ``pEleMinOutflows``
   * - :math:`\pHydMaxOutflows_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum outflows for a hydrogen storage unit
     - kg
     - ``pHydMaxOutflows``
   * - :math:`\pHydMinOutflows_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Minimum outflows for a hydrogen storage unit
     - kg
     - ``pHydMinOutflows``
   * - :math:`\pEleOutflowsTimeStep_{\eunitindex}`
     - Outflows time step for electricity storage
     - h
     - ``pEleOutflowsTimeStep``
   * - :math:`\pHydOutflowsTimeStep_{\hunitindex}`
     - Outflows time step for hydrogen storage
     - h
     - ``pHydOutflowsTimeStep``
   * - :math:`\pEleMaxCharge2ndBlock_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum charging rate of the second block of a unit
     - kW
     - ``pEleMaxCharge2ndBlock``
   * - :math:`\pHydMaxCharge2ndBlock_{\hunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Maximum charging rate of the second block of a hydrogen unit
     - kg/h
     - ``pHydMaxCharge2ndBlock``
   * - :math:`\pVarFixedAvailability_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Availability of a unit
     - -
     - ``pVarFixedAvailability``
   * - :math:`\pOperatingReserveActivationFCRDUp_{\periodindex,\scenarioindex,\timeindex}`
     - Activation of upward frequency containment reserve (FCR-D)
     - -
     - ``pOperatingReserveActivation_FCRD_Up``
   * - :math:`\pOperatingReserveActivationFCRDDown_{\periodindex,\scenarioindex,\timeindex}`
     - Activation of downward frequency containment reserve (FCR-D)
     - -
     - ``pOperatingReserveActivation_FCRD_Down``
   * - :math:`\pEleInitialUC_{\periodindex, \scenarioindex, \eunitindex}`
     - Initial unit commitment status for an electricity unit
     - -
     - ``pEleInitialUC``
   * - :math:`\pHydInitialUC_{\periodindex, \scenarioindex, \hunitindex}`
     - Initial unit commitment status for a hydrogen unit
     - -
     - ``pHydInitialUC``
   * - :math:`\pEleGenRampUp_{\eunitindex}`
     - Ramp-up rate for an electricity unit
     - kW/h
     - ``pEleGenRampUp``
   * - :math:`\pEleGenRampDown_{\eunitindex}`
     - Ramp-down rate for an electricity unit
     - kW/h
     - ``pEleGenRampDown``
   * - :math:`\pOptIndBinGenRamps`
     - Flag to indicate if binary variables are used for ramping
     - -
     - ``pOptIndBinGenRamps``
   * - :math:`\pHydGenRampUp_{\hunitindex}`
     - Ramp-up rate for a hydrogen unit
     - kg/h
     - ``pHydGenRampUp``
   * - :math:`\pHydGenRampDown_{\hunitindex}`
     - Ramp-down rate for a hydrogen unit
     - kg/h
     - ``pHydGenRampDown``
   * - :math:`\pEleGenUpTime_{\eunitindex}`
     - Minimum up time for an electricity unit
     - h
     - ``pEleGenUpTime``
   * - :math:`\pEleGenUpTimeZero_{\eunitindex}`
     - Initial up time for an electricity unit
     - h
     - ``pEleGenUpTimeZero``
   * - :math:`\pEleGenDownTime_{\eunitindex}`
     - Minimum down time for an electricity unit
     - h
     - ``pEleGenDownTime``
   * - :math:`\pEleGenDownTimeZero_{\eunitindex}`
     - Initial down time for an electricity unit
     - h
     - ``pEleGenDownTimeZero``
   * - :math:`\pOptIndBinGenMinTime`
     - Flag to indicate if binary variables are used for minimum up/down time
     - -
     - ``pOptIndBinGenMinTime``
   * - :math:`\pHydGenUpTime_{\hunitindex}`
     - Minimum up time for a hydrogen unit
     - h
     - ``pHydGenUpTime``
   * - :math:`\pHydGenUpTimeZero_{\hunitindex}`
     - Initial up time for a hydrogen unit
     - h
     - ``pHydGenUpTimeZero``
   * - :math:`\pHydGenDownTime_{\hunitindex}`
     - Minimum down time for a hydrogen unit
     - h
     - ``pHydGenDownTime``
   * - :math:`\pHydGenDownTimeZero_{\hunitindex}`
     - Initial down time for a hydrogen unit
     - h
     - ``pHydGenDownTimeZero``
   * - :math:`\pVarStartUp_{\eunitindex, \periodindex,\scenarioindex,\timeindex}`
     - Start-up flag for a unit
     - -
     - ``pVarStartUp``
   * - :math:`\pEleGenFixedAvailability_{\eunitindex}`
     - Fixed availability of a unit
     - -
     - ``pEleGenFixedAvailability``

Network
-------

Parameters related to the energy network infrastructure.

.. list-table::
   :widths: 30 50 10 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Unit**
     - **Pyomo Component**
   * - :math:`\pEleNetInitialPeriod_{\busindexa,\busindexb,\circuitindex}`
     - Initial period of a network line
     - -
     - ``pEleNetInitialPeriod``
   * - :math:`\pParEconomicBaseYear`
     - Base year for economic calculations
     - -
     - ``pParEconomicBaseYear``
   * - :math:`\pEleNetFinalPeriod_{\busindexa,\busindexb,\circuitindex}`
     - Final period of a network line
     - -
     - ``pEleNetFinalPeriod``
   * - :math:`\pEleNetTTC_{\busindexa,\busindexb,\circuitindex}`
     - Total transfer capacity of a network line
     - MW
     - ``pEleNetTTC``
   * - :math:`\pEleNetReactance_{\busindexa,\busindexb,\circuitindex}`
     - Reactance of a network line
     - p.u.
     - ``pEleNetReactance``
