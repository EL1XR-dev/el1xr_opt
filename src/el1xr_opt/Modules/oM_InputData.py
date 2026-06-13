# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import datetime
import os
import math
import time                                         # count clock time
import numpy             as np
import pandas            as pd
from   itertools         import product
from   pyomo.environ     import Set, Param, Var, Binary, UnitInterval, NonNegativeIntegers, NonNegativeReals, Reals, PositiveReals, RangeSet
from   pyomo.dataportal  import DataPortal
from  .oM_InputSource     import resolve_source, df_to_set_values
from  .utils.oM_Utils    import log_time, _update_parameters, _psdn_init, _psmd_init, _psmdn_init, _cartesian_4_psd, _cartesian_4_psm, _extend_psdn_filtered, _apply_mask_and_set_zero

# Unit-scale conversion factor (audit C38). 1.0 by default (byte-unchanged goldens). A true unit
# conversion: extensive quantities scale by FACTOR1, per-quantity prices by 1/FACTOR1, and fixed
# charges / investment / dimensionless ratios are unscaled, so the optimum is invariant.
# Overridable for the factor1-invariance regression test; future hook for a dfParameter input.
FACTOR1 = 1.0

def data_processing(DirName, CaseName, DateModel, model, indlog):
    # %% Read the input data
    print('-- Reading the input data')
    # Defining the path
    path_to_read = os.path.join(DirName,CaseName)
    start_time = time.time()

    if isinstance(DateModel, str):
        DateModel = datetime.datetime.strptime(DateModel, "%Y-%m-%d %H:%M:%S")

    set_definitions = {
        'pp': ('Period',     'p' ), 'scc': ('Scenario', 'sc'), 'nn': ('LoadLevel',  'n' ),
        'st': ('Storage',    'st'), 'gt':  ('Technology', 'gt'),
        'nd': ('Node',       'nd'), 'ni':  ('Node',     'nd'), 'nf': ('Node',       'nd'),
        'zn': ('Zone',       'zn'), 'cc':  ('Circuit',  'cc'), 'c2': ('Circuit',    'cc'),
        'ndzn': ('NodeToZone', 'ndzn'),
        'egg': ('ElectricityGeneration', 'eg' ), 'hgg': ('HydrogenGeneration', 'hg' ),
        'edd': ('ElectricityDemand',     'ed' ), 'hdd': ('HydrogenDemand',     'hd' ),
        'err': ('ElectricityRetail',     'er' ), 'hrr': ('HydrogenRetail',     'hr' ),}

    # Open the input source: a CSV case directory or a <case>.duckdb file. Both
    # backends return identical DataFrames, so the rest of this function is the
    # same regardless of which one was used.
    source = resolve_source(DirName, CaseName)

    # Build the model sets from the dimension dicts. Several set names share one
    # dict file (e.g. ni/nf/nd all come from Node), so dict reads are cached.
    unordered_sets = {'egg', 'hgg', 'edd', 'hdd', 'err', 'hrr', 'st', 'gt', 'nd', 'ni', 'nf', 'cc', 'c2', 'ndzn'}
    dict_cache = {}
    for set_name, (file_set_name, set_key) in set_definitions.items():
        if file_set_name not in dict_cache:
            dict_cache[file_set_name] = df_to_set_values(source.read_dict(file_set_name))
        is_ordered = set_name not in unordered_sets
        setattr(model, set_name, Set(initialize=dict_cache[file_set_name], ordered=is_ordered, doc=f'{file_set_name}'))

    #%% Reading the input data
    data_frames = {}
    for stem in source.list_data_stems():
        data_frames[f'df{stem}'] = source.read_data(stem)
    source.close()

    # substitute NaN by 0 (only for numeric columns to avoid TypeError on string columns)
    for df in data_frames.values():
        numeric_cols = df.select_dtypes(include='number').columns
        df[numeric_cols] = df[numeric_cols].fillna(0.0)

    # Define prefixes and suffixes
    model.reserves_prefixes     = ['FCRD_Up', 'FCRD_Down','FCRN_Up','FCRN_Down']
    model.FCRD_prefixes         = [i for i in model.reserves_prefixes if "FCRD" in i]
    model.FCRN_prefixes         = [i for i in model.reserves_prefixes if "FCRN" in i]
    model.gen_frames_suffixes   = ['VarMinGeneration', 'VarMaxGeneration',
                                   'VarMinConsumption', 'VarMaxConsumption',
                                   'VarMinStorage', 'VarMaxStorage',
                                   'VarMinInflows', 'VarMaxInflows',
                                   'VarMinOutflows', 'VarMaxOutflows',
                                   'VarMinEnergy', 'VarMaxEnergy',
                                   'VarMinFuelCost', 'VarMaxFuelCost',
                                   'VarMinEmissionCost', 'VarMaxEmissionCost',
                                   'VarPositionConsumption', 'VarPositionGeneration',
                                   'VarFixedAvailability',]
    model.demand_frames_suffixes = ['VarMaxDemand', 'VarMinDemand']
    model.retail_frames_suffixes = ['VarEnergyCost', 'VarEnergyPrice']

    # Apply the condition to each specified column
    for keys, df in data_frames.items():
        if [1 for suffix in model.gen_frames_suffixes if suffix in keys]:
            data_frames[keys] = df.where(df > 0.0, 0.0)

    # Apply the condition to each specified column
    for column in model.gen_frames_suffixes:
        data_frames[f'df{column}'] = data_frames[f'df{column}'].where(data_frames[f'df{column}'] > 0.0)

    log_time('--- Reading the CSV files:', start_time, ind_log=indlog)
    start_time = time.time()

    # Constants
    # factor1 is a unit-scale conversion (audit C38) for numerical conditioning -- it lets the
    # model work at utility (MWh/MEUR) or home (kWh/EUR) scale. It is a TRUE unit conversion, so
    # it must leave the optimum unchanged: it scales the EXTENSIVE quantities (capacities,
    # demand, flows, storage energy, network limits, FCR volume, ramps) by factor1, scales each
    # per-quantity PRICE by 1/factor1 so price x quantity (the money) is invariant, and leaves
    # fixed charges, investment lump sums, and dimensionless ratios (production function,
    # compressor/emission rates) unscaled. At factor1 == 1 every scaling is a no-op (goldens
    # byte-unchanged); a factor1 != 1 run reproduces the same decisions and total cost
    # (guarded by test_factor1_invariant). FACTOR1 (module global) is the override hook for
    # that test and the future dfParameter input.
    factor1 = FACTOR1
    # factor2 (the old 1e-3 commitment-cost unit bridge) is ELIMINATED (audit Phase B / B0):
    # the model now works in a single canonical currency, so ConstantTerm / StartUpCost /
    # ShutDownCost are entered directly in that currency (no hidden scaling). See the
    # generation-cost block below and the realistic electrolyser values in the data.
    model.factor1 = factor1

    # Option Indicators
    option_ind = data_frames['dfOption'].columns.to_list()

    # Extract and cast option indicators
    parameters_dict = {f'pOpt{indicator}': data_frames['dfOption'][indicator].iloc[0].astype('int') for indicator in option_ind}

    # Optional feature flags that may be absent from older Option files default to
    # off (from the feature catalogue), so existing cases are unaffected.
    from .oM_Features import apply_flag_defaults
    apply_flag_defaults(parameters_dict)

    # Parameter Indicators
    parameter_ind = data_frames['dfParameter'].columns.to_list()

    # Extract, process parameter variables and add to parameters_dict
    for indicator in parameter_ind:
        if ('Cost' in indicator or 'Target' in indicator or 'Ramp' in indicator) and 'CO2' not in indicator:
            parameters_dict[f'pPar{indicator}'] = data_frames['dfParameter'][indicator].iloc[0] * factor1
        else:
            parameters_dict[f'pPar{indicator}'] = data_frames['dfParameter'][indicator].iloc[0]

    parameters_dict['pDuration'       ] = data_frames['dfDuration']['Duration'] * parameters_dict['pParTimeStep']
    #parameters_dict['pLevelToIDmarket'] = data_frames['dfDuration']['IDMarket'].astype('int')
    parameters_dict['pPeriodWeight'   ] = data_frames['dfPeriod']['Weight'].astype('int')
    parameters_dict['pScenProb'       ] = data_frames['dfScenario']['Probability'].astype('float')

    # Merging sets gg and hh
    model.ehd = model.edd | model.hdd
    # Extract and cast nodal parameters
    for suffix in model.demand_frames_suffixes:
        parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'].reindex(columns=model.ehd, fill_value=0.0) * factor1

    # Merging sets gg and hh
    model.ehg = model.egg | model.hgg
    # Extract and cast generation parameters. factor1 (audit C38): per-quantity PRICES carry
    # 1/factor1, dimensionless RATIOS/availabilities are unscaled, and the extensive quantities
    # carry factor1. VarMin/MaxStorage are storage energy but read unscaled here -- the factor1
    # is applied once later at the inventory-bound / investment-cap sites (and the initial
    # inventory), matching the GenMaximumStorage fallback (C24).
    _gen_price_suffixes = ('VarMinFuelCost', 'VarMaxFuelCost', 'VarMinEmissionCost', 'VarMaxEmissionCost')
    _gen_unscaled_suffixes = ('VarMinStorage', 'VarMaxStorage',                       # applied later at bounds
                              'VarFixedAvailability', 'VarPositionConsumption', 'VarPositionGeneration')  # dimensionless
    for suffix in model.gen_frames_suffixes:
        if suffix in _gen_price_suffixes:
            scale = 1.0 / factor1
        elif suffix in _gen_unscaled_suffixes:
            scale = 1.0
        else:
            scale = factor1
        parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'].reindex(columns=model.ehg, fill_value=0.0) * scale

    # Merging sets gg and hh
    model.ehr = model.err | model.hrr
    # Extract and cast retail parameters. retail_frames_suffixes are the day-ahead energy
    # buy/sell PRICES (VarEnergyCost/Price), so they carry 1/factor1 (audit C38): the bought/
    # sold energy scales by factor1, keeping the money invariant.
    for suffix in model.retail_frames_suffixes:
        parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'].reindex(columns=model.ehr, fill_value=0.0) / factor1

    # Extract and cast operating reserve parameters for RM and RT markets
    for ind in model.reserves_prefixes:
        parameters_dict[f'pOperatingReservePrice_{ind}'     ] = data_frames['dfOperatingReservePrice'     ][ind] / factor1   # FCR PRICE -> 1/factor1 (audit C38)
        parameters_dict[f'pOperatingReserveRequire_{ind}'   ] = data_frames['dfOperatingReserveRequire'   ][ind] * factor1   # FCR VOLUME (quantity) -> factor1
        parameters_dict[f'pOperatingReserveActivation_{ind}'] = data_frames['dfOperatingReserveActivation'][ind]

    # compute the Demand as the mean over the time step load levels and assign it to active load levels.
    # Idem for operating reserve, variable max power, variable min and max storage capacity and inflows and outflows
    for ind in model.gen_frames_suffixes + model.demand_frames_suffixes + model.retail_frames_suffixes:
        parameters_dict[f'p{ind}'] = parameters_dict[f'p{ind}'].rolling(parameters_dict['pParTimeStep']).mean()
        parameters_dict[f'p{ind}'].fillna(0.0, inplace=True)

    for idx in model.reserves_prefixes:
        parameters_dict[f'pOperatingReservePrice_{idx}'     ] = parameters_dict[f'pOperatingReservePrice_{idx}'     ].rolling(parameters_dict['pParTimeStep']).mean()
        parameters_dict[f'pOperatingReservePrice_{idx}'     ].fillna(0.0, inplace=True)
        parameters_dict[f'pOperatingReserveRequire_{idx}'   ] = parameters_dict[f'pOperatingReserveRequire_{idx}'   ].rolling(parameters_dict['pParTimeStep']).mean()
        parameters_dict[f'pOperatingReserveRequire_{idx}'   ].fillna(0.0, inplace=True)
        parameters_dict[f'pOperatingReserveActivation_{idx}'] = parameters_dict[f'pOperatingReserveActivation_{idx}'].rolling(parameters_dict['pParTimeStep']).mean()
        parameters_dict[f'pOperatingReserveActivation_{idx}'].fillna(0.0, inplace=True)

    if parameters_dict['pParTimeStep'] > 1:
        # assign duration 0 to load levels not being considered, active load levels are at the end of every pTimeStep
        for i in range(parameters_dict['pParTimeStep']-2,-1,-1):
            parameters_dict['pDuration'].iloc[[range(i, len(model.nn), parameters_dict['pParTimeStep'])]] = 0

    # generation indicators
    EleGeneration_ind = data_frames['dfElectricityGeneration'].columns.to_list()
    HydGeneration_ind = data_frames['dfHydrogenGeneration'].columns.to_list()
    # factor1 (audit C38): only EXTENSIVE quantities are scaled by factor1 here. Prices
    # (OMVariableCost) are handled as 1/factor1 below, and dimensionless ratios
    # (ProductionFunction, MaxCompressorConsumption, CO2EmissionRate) are NOT scaled.
    idx_gen_factoring  = ['MaximumPower', 'MinimumPower', 'StandByPower', 'MaximumCharge', 'MinimumCharge',
                      'RampUp', 'RampDown', 'MaxOutflowsProd', 'MinOutflowsProd', 'MaxInflowsCons', 'MinInflowsCons', 'OutflowsRampDown', 'OutflowsRampUp']
    # demand indicators
    EleDemand_ind = data_frames['dfElectricityDemand'].columns.to_list()
    HydDemand_ind = data_frames['dfHydrogenDemand'].columns.to_list()
    idx_dem_factoring = ['MaximumPower']

    # retail indicators
    EleRetail_ind = data_frames['dfElectricityRetail'].columns.to_list()
    HydRetail_ind = data_frames['dfHydrogenRetail'].columns.to_list()
    idx_retail_factoring = ['MaximumEnergyBuy', 'MinimumEnergyBuy', 'MaximumEnergySell', 'MinimumEnergySell']

    # Update electricity-related parameters
    _update_parameters(data_frames, parameters_dict, factor1, EleGeneration_ind, idx_gen_factoring, 'dfElectricityGeneration', 'pEleGen')
    _update_parameters(data_frames, parameters_dict, factor1, EleDemand_ind, idx_dem_factoring, 'dfElectricityDemand', 'pEleDem')
    _update_parameters(data_frames, parameters_dict, factor1, EleRetail_ind, idx_retail_factoring, 'dfElectricityRetail', 'pEleRet')

    # Update hydrogen-related parameters
    _update_parameters(data_frames, parameters_dict, factor1, HydGeneration_ind, idx_gen_factoring, 'dfHydrogenGeneration', 'pHydGen')
    _update_parameters(data_frames, parameters_dict, factor1, HydDemand_ind, idx_dem_factoring, 'dfHydrogenDemand', 'pHydDem')
    _update_parameters(data_frames, parameters_dict, factor1, HydRetail_ind, idx_retail_factoring, 'dfHydrogenRetail', 'pHydRet')

    # Per-step buy/sell caps (MaxBuy/MaxSell) are optional retail columns. When a
    # retail file omits them, default the cap to 0.0, read as "no cap" by the
    # eRetMaxBuy/Sell constraints (they skip a zero cap). The hydrogen retail file
    # has no MaxBuy/MaxSell columns, so activating a hydrogen retailer would
    # otherwise KeyError here; the electricity file already carries them.
    # factor1 (audit C38): MaxBuy/MaxSell are per-step power caps (kW/step) -- extensive
    # quantities -- so they must scale by factor1 like the other quantity bounds (the var ub
    # pEleRetMaximumEnergySell already does). Without this the cap stays fixed while prices
    # carry 1/factor1, so a sell pinned at the cap earns half the revenue at twice the unit
    # scale, breaking invariance. They are read unscaled by _update_parameters (not in
    # idx_retail_factoring), so scale them here. A defaulted/zero cap (= "no cap") stays zero.
    for sector, df_key in [('Ele', 'dfElectricityRetail'), ('Hyd', 'dfHydrogenRetail')]:
        for cap in ['MaxBuy', 'MaxSell']:
            key = f'p{sector}Ret{cap}'
            if key not in parameters_dict:
                parameters_dict[key] = pd.Series(0.0, index=data_frames[df_key].index)
            else:
                parameters_dict[key] = parameters_dict[key] * factor1
        # TariffType is optional too (the hydrogen retail file does not carry it).
        # Default to '' = no peak tariff: the variable-fixing loops compare against
        # 'Hourly'/'Daily' and fix every peak variable of any other type to zero.
        key = f'p{sector}RetTariffType'
        if key not in parameters_dict:
            parameters_dict[key] = pd.Series('', index=data_frames[df_key].index)

    for sector in ['Ele', 'Hyd']:
        # Degradation cost is an optional generation column (audit Phase B / B2); default it to
        # zero so units / cases without it are unaffected (the column read only creates present ones).
        _df_gen_key = 'dfElectricityGeneration' if sector == 'Ele' else 'dfHydrogenGeneration'
        if f'p{sector[0:3]}GenDegradationCost' not in parameters_dict:
            parameters_dict[f'p{sector[0:3]}GenDegradationCost'] = pd.Series(0.0, index=data_frames[_df_gen_key].index)
        # factor1 (audit C38): per-quantity PRICES carry 1/factor1 so price x quantity (which
        # scales by factor1) is invariant. LinearVarCost, CO2EmissionCost and OMVariableCost are
        # such prices; the CO2 emission RATE is a dimensionless ratio and is no longer factored.
        parameters_dict[f'p{sector[0:3]}GenLinearVarCost'     ] = parameters_dict[f'p{sector[0:3]}GenLinearTerm'          ] / model.factor1 * parameters_dict[f'p{sector[0:3]}GenFuelCost']  # linear fuel cost; O&M is added once in the objective (eTotal{Ele,Hyd}GCost)
        parameters_dict[f'p{sector[0:3]}GenOMVariableCost'    ] = parameters_dict[f'p{sector[0:3]}GenOMVariableCost'      ] / model.factor1                                                                                                                        # O&M variable cost (price)
        parameters_dict[f'p{sector[0:3]}GenConstantVarCost'   ] = parameters_dict[f'p{sector[0:3]}GenConstantTerm'        ] * parameters_dict[f'p{sector[0:3]}GenFuelCost']                                                                                          # no-load variable cost [canonical currency/h] (factor2 eliminated, B0)
        parameters_dict[f'p{sector[0:3]}GenCO2EmissionCost'   ] = parameters_dict[f'p{sector[0:3]}GenCO2EmissionRate'     ] / model.factor1 * parameters_dict[ 'pParCO2Cost']                                                                                      # CO2 emission cost
        # StartUpCost / ShutDownCost are used directly in the canonical currency (factor2
        # eliminated, B0); the generation-column read already populated them, so no rescaling.
        # Degradation cost (audit Phase B / B2): a stack-wear PRICE per kWh of productive
        # electricity, so it carries 1/factor1 like the other per-quantity prices (default 0).
        parameters_dict[f'p{sector[0:3]}GenDegradationCost'   ] = parameters_dict[f'p{sector[0:3]}GenDegradationCost'     ] / model.factor1                                                                                                                        # stack degradation cost (price per kWh)
        parameters_dict[f'p{sector[0:3]}GenInvestCost'        ] = parameters_dict[f'p{sector[0:3]}GenFixedInvestmentCost' ]        * parameters_dict[f'p{sector[0:3]}GenFixedChargeRate']                                                                          # generation fixed cost                   [MEUR]
        parameters_dict[f'p{sector[0:3]}GenRetireCost'        ] = parameters_dict[f'p{sector[0:3]}GenFixedRetirementCost' ]        * parameters_dict[f'p{sector[0:3]}GenFixedChargeRate']                                                                          # generation fixed retirement cost        [MEUR]                                                                           # H2 outflows ramp down rate              [tonH2]

    parameters_dict['pNodeLat'                 ] = data_frames['dfNodeLocation']['Latitude'          ]                                                                                                                                                             # node latitude                           [º]
    parameters_dict['pNodeLon'                 ] = data_frames['dfNodeLocation']['Longitude'         ]                                                                                                                                                             # node longitude                          [º]

    # electricity network indicators
    electricity_network_ind = data_frames['dfElectricityNetwork'].columns.to_list()
    for idx in electricity_network_ind:
        parameters_dict[f'pEleNet{idx}'] = data_frames['dfElectricityNetwork'][idx]

    # hydrogen network indicators
    hydrogen_network_ind = data_frames['dfHydrogenNetwork'].columns.to_list()
    for idx in hydrogen_network_ind:
        parameters_dict[f'pHydNet{idx}'] = data_frames['dfHydrogenNetwork'][idx]

    for net in ['Electricity', 'Hydrogen']:
        parameters_dict[f'p{net[0:3]}NetTTC'                ] = parameters_dict[f'p{net[0:3]}NetTTC'                ] * factor1 * parameters_dict[f'p{net[0:3]}NetSecurityFactor' ]
        parameters_dict[f'p{net[0:3]}NetTTCBck'             ] = parameters_dict[f'p{net[0:3]}NetTTCBck'             ] * factor1 * parameters_dict[f'p{net[0:3]}NetSecurityFactor' ]
        parameters_dict[f'p{net[0:3]}NetFixedInvestmentCost'] = parameters_dict[f'p{net[0:3]}NetFixedInvestmentCost']           * parameters_dict[f'p{net[0:3]}NetFixedChargeRate']
        if net == 'Electricity':
            parameters_dict[f'p{net[0:3]}NetReactance'] = parameters_dict[f'p{net[0:3]}NetReactance'].sort_index()
            parameters_dict[f'p{net[0:3]}NetSwOnTime' ] = parameters_dict[f'p{net[0:3]}NetSwOnTime' ].astype('int')
            parameters_dict[f'p{net[0:3]}NetSwOffTime'] = parameters_dict[f'p{net[0:3]}NetSwOffTime'].astype('int')

    for net in ['Electricity', 'Hydrogen']:
        # replace p{net[0:3]}NetTTCBck = 0.0 by p{net[0:3]}NetTTC
        parameters_dict[f'p{net[0:3]}NetTTCBck'] = parameters_dict[f'p{net[0:3]}NetTTCBck'].where(parameters_dict[f'p{net[0:3]}NetTTCBck'] > 0.0, other=parameters_dict[f'p{net[0:3]}NetTTC'])
        # replace p{net[0:3]}NetTTC = 0.0 by p{net[0:3]}NetTTCBck
        parameters_dict[f'p{net[0:3]}NetTTC'   ] = parameters_dict[f'p{net[0:3]}NetTTC'   ].where(parameters_dict[f'p{net[0:3]}NetTTC'] > 0.0, other=parameters_dict[f'p{net[0:3]}NetTTCBck'])
        # replace p{net[0:3]}NetInvestmentUp= 0.0 by 1.0
        parameters_dict[f'p{net[0:3]}NetInvestmentUp'] = parameters_dict[f'p{net[0:3]}NetInvestmentUp'].where(parameters_dict[f'p{net[0:3]}NetInvestmentUp'] > 0.0, other=1.0)

        parameters_dict[f'p{net[0:3]}GenInvestmentUp'] = parameters_dict[f'p{net[0:3]}GenInvestmentUp'].where(parameters_dict[f'p{net[0:3]}GenInvestmentUp'] > 0.0, other=1.0)

    # minimum up- and downtime converted to an integer number of time steps
    parameters_dict['pEleNetSwOnTime' ] = round(parameters_dict['pEleNetSwOnTime' ] / parameters_dict['pParTimeStep']).astype('int')

    log_time('--- Transforming the dataframes:', start_time, ind_log=indlog)
    start_time = time.time()

    # replacing string values by numerical values
    idxDict        = dict()
    idxDict[0    ] = 0
    idxDict[0.0  ] = 0
    idxDict['No' ] = 0
    idxDict['NO' ] = 0
    idxDict['no' ] = 0
    idxDict['N'  ] = 0
    idxDict['n'  ] = 0
    idxDict['Yes'] = 1
    idxDict['YES'] = 1
    idxDict['yes'] = 1
    idxDict['Y'  ] = 1
    idxDict['y'  ] = 1

    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector[0:3]}GenBinaryInvestment'   ] = parameters_dict[f'p{sector[0:3]}GenBinaryInvestment'   ].map(idxDict)
        parameters_dict[f'p{sector[0:3]}GenBinaryRetirement'   ] = parameters_dict[f'p{sector[0:3]}GenBinaryRetirement'   ].map(idxDict)
        parameters_dict[f'p{sector[0:3]}GenBinaryCommitment'   ] = parameters_dict[f'p{sector[0:3]}GenBinaryCommitment'   ].map(idxDict)
        parameters_dict[f'p{sector[0:3]}GenStorageInvestment'  ] = parameters_dict[f'p{sector[0:3]}GenStorageInvestment'  ].map(idxDict)
        parameters_dict[f'p{sector[0:3]}GenFixedAvailability'  ] = parameters_dict[f'p{sector[0:3]}GenFixedAvailability'  ].map(idxDict)
        parameters_dict[f'p{sector[0:3]}NetBinaryInvestment'   ] = parameters_dict[f'p{sector[0:3]}NetBinaryInvestment'   ].map(idxDict)



    parameters_dict['pEleNetSwitching'         ] = parameters_dict['pEleNetSwitching'         ].map(idxDict)
    parameters_dict['pHydNetBinaryInvestment'  ] = parameters_dict['pHydNetBinaryInvestment'  ].map(idxDict)
    parameters_dict['pEleGenV2G'               ] = parameters_dict['pEleGenV2G'               ].map(idxDict)
    parameters_dict['pEleGenNoDayAhead'        ] = parameters_dict['pEleGenNoDayAhead'        ].map(idxDict)
    # default 1 ("not participating") for a blank cell, like the e2h flags below; without
    # the fillna a blank maps to NaN -- neither 0 nor 1 -- so the unit escapes both the
    # bid fixing and every FCR constraint while still being paid revenue (C17).
    parameters_dict['pEleGenNoFCRD'            ] = parameters_dict['pEleGenNoFCRD'            ].map(idxDict).fillna(1).astype('int')
    parameters_dict['pEleGenNoFCRN'            ] = parameters_dict['pEleGenNoFCRN'            ].map(idxDict).fillna(1).astype('int')
    parameters_dict['pEleGenMaxCommitment'     ] = parameters_dict['pEleGenMaxCommitment'     ].map(idxDict)
    # Electrolyser (e2h) standby state and draw. When the hydrogen-generation data
    # omits these columns, standby is disabled (status 0) and the standby draw is 0,
    # so cases without the three-state feature load unchanged.
    if 'pHydGenStandByStatus' in parameters_dict:
        parameters_dict['pHydGenStandByStatus'] = parameters_dict['pHydGenStandByStatus'].map(idxDict).fillna(0).astype('int')
    else:
        parameters_dict['pHydGenStandByStatus'] = pd.Series(0, index=parameters_dict['pHydGenProductionFunction'].index, dtype='int')
    if 'pHydGenStandByPower' not in parameters_dict:
        parameters_dict['pHydGenStandByPower'] = pd.Series(0.0, index=parameters_dict['pHydGenProductionFunction'].index)
    # Compressor consumption: electricity drawn to compress hydrogen into a store, per
    # unit of hydrogen charged. When the hydrogen-generation data omits the column, or
    # leaves it blank for a unit, the draw defaults to 0, so units and cases without it
    # build unchanged.
    if 'pHydGenMaxCompressorConsumption' in parameters_dict:
        parameters_dict['pHydGenMaxCompressorConsumption'] = parameters_dict['pHydGenMaxCompressorConsumption'].fillna(0.0)
    else:
        parameters_dict['pHydGenMaxCompressorConsumption'] = pd.Series(0.0, index=parameters_dict['pHydGenProductionFunction'].index)
    # Electrolyser (e2h) FCR participation flags and endurance. When the hydrogen-
    # generation data omits these columns the flags default to 1 ("not participating")
    # and the endurance to 0, so existing cases are unaffected. An electrolyser only
    # offers FCR when its NoFCRD / NoFCRN column is set to "No".
    for flag_col in ['pHydGenNoFCRD', 'pHydGenNoFCRN']:
        if flag_col in parameters_dict:
            parameters_dict[flag_col] = parameters_dict[flag_col].map(idxDict).fillna(1).astype('int')
        else:
            parameters_dict[flag_col] = pd.Series(1, index=parameters_dict['pHydGenProductionFunction'].index, dtype='int')
    for end_col in ['pHydGenEnduranceFCRD', 'pHydGenEnduranceFCRN']:
        if end_col in parameters_dict:
            parameters_dict[end_col] = parameters_dict[end_col].fillna(0.0)
        else:
            parameters_dict[end_col] = pd.Series(0.0, index=parameters_dict['pHydGenProductionFunction'].index)
    parameters_dict['pEleGenRES'               ] = parameters_dict['pEleGenRES'               ].map(idxDict)
    parameters_dict['pEleGenESS'               ] = parameters_dict['pEleGenESS'               ].map(idxDict)
    parameters_dict['pEleGenEV'                ] = parameters_dict['pEleGenEV'                ].map(idxDict)
    parameters_dict['pEleDemFlexible'          ] = parameters_dict['pEleDemFlexible'          ].map(idxDict)
    parameters_dict['pHydDemFlexible'          ] = parameters_dict['pHydDemFlexible'          ].map(idxDict)
    parameters_dict['pEleRetBuy'               ] = parameters_dict['pEleRetBuy'               ].map(idxDict)
    parameters_dict['pEleRetSell'              ] = parameters_dict['pEleRetSell'              ].map(idxDict)
    parameters_dict['pHydRetBuy'               ] = parameters_dict['pHydRetBuy'               ].map(idxDict)
    parameters_dict['pHydRetSell'              ] = parameters_dict['pHydRetSell'              ].map(idxDict)

    # %% Getting the branches from the network data
    sEleBr = [(ni,nf) for (ni,nf,cc) in data_frames['dfElectricityNetwork'].index.to_list()]
    sHydBr = [(ni,nf) for (ni,nf,cc) in data_frames['dfHydrogenNetwork'].index.to_list()]
    # Dropping duplicate elements
    sEleBrList = [(ni,nf) for n, (ni,nf) in enumerate(sEleBr) if (ni,nf) not in sEleBr[:n]]
    sHydBrList = [(ni,nf) for n, (ni,nf) in enumerate(sHydBr) if (ni,nf) not in sHydBr[:n]]

    # %% defining subsets: active load levels (n,n2), thermal units (t), RES units (re), ESS units (es), candidate gen units (gc), candidate ESS units (ec), all the electric lines (la),
    # candidate electric lines (lc), electric lines with losses (ll), reference node (rf)
    model.p    = Set(doc='periods                      ', initialize=[pp     for pp   in model.pp            if  parameters_dict['pPeriodWeight']      [pp]   >  0.0 and  sum(parameters_dict['pDuration'] [pp,sc,n] for sc,n in model.scc*model.nn) > 0])
    model.sc   = Set(doc='scenarios                    ', initialize=[scc    for scc  in           model.scc ])
    model.ps   = Set(doc='periods/scenarios            ', initialize=[(p,sc) for p,sc in model.p * model.sc  if  parameters_dict['pScenProb']          [p,sc] >  0.0 and  sum(parameters_dict['pDuration'] [p ,sc,n] for    n in           model.nn) > 0])
    model.n    = Set(doc='load levels                  ', initialize=[nn     for nn   in           model.nn  if                                                           sum(parameters_dict['pDuration'] [p,sc,nn] for p,sc in           model.ps) > 0])
    model.n2   = Set(doc='load levels                  ', initialize=[nn     for nn   in           model.nn  if                                                           sum(parameters_dict['pDuration'] [p,sc,nn] for p,sc in           model.ps) > 0])
    model.eg   = Set(doc='electricity generation units ', initialize=[egg    for egg  in           model.egg if (parameters_dict['pEleGenMaximumPower']     [egg]  >  0.0 or   parameters_dict['pEleGenMaximumCharge']     [egg] >  0 ) and parameters_dict['pEleGenInitialPeriod']     [egg] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pEleGenFinalPeriod'][egg]  >= parameters_dict['pParEconomicBaseYear']])
    model.ed   = Set(doc='electricity demand     units ', initialize=[edd    for edd  in           model.edd if  parameters_dict['pEleDemMaximumPower']     [edd]  >  0.0 and parameters_dict['pEleDemInitialPeriod']     [edd] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pEleDemFinalPeriod'][edd]  >= parameters_dict['pParEconomicBaseYear']])
    model.er   = Set(doc='electricity retail     units ', initialize=[err    for err  in           model.err if (parameters_dict['pEleRetMaximumEnergyBuy'] [err]  >  0.0 or   parameters_dict['pEleRetMaximumEnergySell'] [err] >  0.0 or  parameters_dict['pEleRetMinimumEnergyBuy']  [err] >  0.0 or parameters_dict['pEleRetMinimumEnergySell'][err] > 0.0) and parameters_dict['pEleRetInitialPeriod']     [err] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pEleRetFinalPeriod'][err]  >= parameters_dict['pParEconomicBaseYear']])
    model.egt  = Set(doc='electricity thermal    units ', initialize=[egt    for egt  in           model.eg  if  parameters_dict['pEleGenConstantVarCost']  [egt]  >  0.0])
    model.egr  = Set(doc='electricity RES        units ', initialize=[egr    for egr  in           model.eg  if  parameters_dict['pEleGenRES']              [egr] ==  1.0])
    model.egs  = Set(doc='electricity ESS        units ', initialize=[egs    for egs  in           model.eg  if  parameters_dict['pEleGenESS']              [egs] ==  1.0 or   parameters_dict['pEleGenEV']                [egs] == 1.0])
    model.egv  = Set(doc='electricity EV         units ', initialize=[egv    for egv  in           model.eg  if  parameters_dict['pEleGenEV' ]              [egv] ==  1.0])
    model.egc  = Set(doc='electricity candidate  units ', initialize=[egc    for egc  in           model.eg  if  parameters_dict['pEleGenInvestCost']       [egc]  >  0.0])
    model.egsc = Set(doc='electricity storage    units ', initialize=[egsc   for egsc in           model.egs if  parameters_dict['pEleGenInvestCost']      [egsc]  >  0.0])
    model.hg   = Set(doc='hydrogen generation    units ', initialize=[hgg    for hgg  in           model.hgg if (parameters_dict['pHydGenMaximumPower']     [hgg]  >  0.0 or   parameters_dict['pHydGenMaximumCharge']     [hgg] >  0 ) and parameters_dict['pHydGenInitialPeriod']     [hgg] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pHydGenFinalPeriod'][hgg]  >= parameters_dict['pParEconomicBaseYear']])
    model.hgt  = Set(doc='hydrogen scheduled     units ', initialize=[hgt    for hgt  in           model.hg  if  parameters_dict['pHydGenConstantVarCost']  [hgt]  >  0.0])
    # Active hydrogen demands are those whose period window covers the base year --
    # the same period test as electricity demand (model.ed) and the generation sets.
    # (Unlike electricity, hydrogen demand is driven by the VarMaxDemand time series,
    # not a MaximumPower cap, so there is no MaximumPower > 0 filter; the previous
    # `== 0.0` test had no period window, so future hydrogen demand was active in the
    # base year while the matching hydrogen supply was correctly excluded.)
    model.hd   = Set(doc='hydrogen demand        units ', initialize=[hdd    for hdd  in           model.hdd if  parameters_dict['pHydDemInitialPeriod']     [hdd] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pHydDemFinalPeriod'][hdd]  >= parameters_dict['pParEconomicBaseYear']])
    model.hr   = Set(doc='hydrogen retail        units ', initialize=[hrr    for hrr  in           model.hrr if  parameters_dict['pHydRetMaximumEnergyBuy'] [hrr]  >  0.0 or   parameters_dict['pHydRetMaximumEnergySell'] [hrr] >  0.0 or  parameters_dict['pHydRetMinimumEnergyBuy']  [hrr] >  0.0 or parameters_dict['pHydRetMinimumEnergySell'][hrr] > 0.0])
    model.hgs  = Set(doc='hydrogen storage       units ', initialize=[hgs    for hgs  in           model.hg  if  parameters_dict['pHydGenMaximumStorage']   [hgs]  >  0.0 and (parameters_dict['pVarMaxInflows'].sum()     [hgs] >  0.0 or  parameters_dict['pVarMaxOutflows'].sum()    [hgs] >  0.0 or parameters_dict['pHydGenMaximumCharge'][hgs] > 0.0)])
    model.hgc  = Set(doc='hydrogen candidate     units ', initialize=[hgc    for hgc  in           model.hg  if  parameters_dict['pHydGenInvestCost']       [hgc]  >  0.0])
    model.hgsc = Set(doc='hydrogen storage       units ', initialize=[hgsc   for hgsc in           model.hgs if  parameters_dict['pHydGenInvestCost']      [hgsc]  >  0.0])
    model.e2h  = Set(doc='ele2hyd                units ', initialize=[hg     for hg   in           model.hg  if  parameters_dict['pHydGenProductionFunction'][hg]  >  0.0])
    model.h2e  = Set(doc='hyd2ele                units ', initialize=[eg     for eg   in           model.eg  if  parameters_dict['pEleGenProductionFunction'][eg]  >  0.0])
    # Audit C39: a generation unit whose InitialPeriod is after the economic base year is
    # dropped from the active sets above (single-period model). That is correct here, but it
    # used to happen silently; warn so a future-dated candidate is not lost unnoticed.
    _base_year = parameters_dict['pParEconomicBaseYear']
    for _g in model.egg:
        if _g not in model.eg and parameters_dict['pEleGenInitialPeriod'][_g] > _base_year:
            print(f"WARNING (C39): electricity unit '{_g}' has InitialPeriod "
                  f"{parameters_dict['pEleGenInitialPeriod'][_g]} > base year {_base_year} and is "
                  f"dropped from the model (single-period run).")
    for _g in model.hgg:
        if _g not in model.hg and parameters_dict['pHydGenInitialPeriod'][_g] > _base_year:
            print(f"WARNING (C39): hydrogen unit '{_g}' has InitialPeriod "
                  f"{parameters_dict['pHydGenInitialPeriod'][_g]} > base year {_base_year} and is "
                  f"dropped from the model (single-period run).")
    # Hydrogen analogue of egr (electricity RES). There is no hydrogen RES column,
    # so this set is empty; it exists because the initial-output loop references it
    # the same way the electricity loop references egr.
    model.hgr  = Set(doc='hydrogen RES           units ', within=model.hgg, initialize=[])
    model.ebr  = Set(doc='all input branches           ', initialize=[(ni,nf) for ni,nf in sEleBrList])
    model.eln  = Set(doc='all input lines              ', initialize=data_frames['dfElectricityNetwork'].index.to_list())
    model.ela  = Set(doc='all real lines               ', initialize=[el for el in model.eln if parameters_dict['pEleNetReactance'][el] != 0.0 and  parameters_dict['pEleNetTTC'][el] > 0.0 and parameters_dict['pEleNetTTCBck'][el] > 0.0 and parameters_dict['pEleNetInitialPeriod'][el] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pEleNetFinalPeriod'][el] >= parameters_dict['pParEconomicBaseYear']])
    model.els  = Set(doc='all real switch lines        ', initialize=[el for el in model.ela if parameters_dict['pEleNetSwitching'][el]])
    model.elc  = Set(doc='candidate lines              ', initialize=[el for el in model.ela if parameters_dict['pEleNetFixedInvestmentCost'][el] > 0.0])
    model.endrf= Set(doc='electricity reference node   ', initialize=[nd for nd in model.nd  if nd in parameters_dict['pParEleReferenceNode']])
    model.hndrf= Set(doc='hydrogen    reference node   ', initialize=[nd for nd in model.nd  if nd in parameters_dict['pParHydReferenceNode']])
    model.hbr  = Set(doc='all input branches           ', initialize=[(ni,nf) for ni,nf in sHydBrList])
    model.hpn  = Set(doc='all input H2 pipelines       ', initialize=data_frames['dfHydrogenNetwork'].index.to_list())
    model.hpa  = Set(doc='all real H2 pipelines        ', initialize=[hp for hp in model.hpn if parameters_dict['pHydNetTTC'][hp] > 0.0 and parameters_dict['pHydNetTTCBck'][hp] > 0.0 and parameters_dict['pHydNetInitialPeriod'][hp] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pHydNetFinalPeriod'][hp] >= parameters_dict['pParEconomicBaseYear']])
    model.hpc  = Set(doc='candidate H2 pipelines       ', initialize=[hp for hp in model.hpa if parameters_dict['pHydNetFixedInvestmentCost'][hp] > 0.0])

    model.egnr = model.eg  - model.egr           # non-RES units, they can be committed and also contribute to the operating reserves
    model.ele  = model.ela - model.elc           # existing electric lines (le)
    model.hpe  = model.hpa - model.hpc           # existing hydrogen pipelines (pe)

    model.eh   = model.egs | model.e2h           # set for the electricity consumption
    model.he   = model.hgs | model.h2e           # set for the hydrogen consumption
    model.ehs  = model.egs | model.hgs           # set for the electricity and hydrogen ESS
    model.esc  = model.egc | model.hgc           # set for the candidate ESS and hydrogen units
    model.ege2h = model.eg | model.e2h           # units that can bid FCR (generators/storage plus electrolysers)


    log_time('--- Defining the sets:', start_time, ind_log=indlog)
    start_time = time.time()

    # instrumental sets
    model.psc      = [(p, sc            )        for p, sc                    in model.p     * model.sc  ]
    model.pn       = [(p, n             )        for p, n                     in model.p     * model.n   ]
    model.pegs     = [(p, egs           )        for p, egs                   in model.p     * model.egs ]
    model.pehs     = [(p, ehs           )        for p, ehs                   in model.p     * model.ehs ]
    model.pnegg    = [(p, n , g         )        for p, n , g                 in model.pn    * model.egg ]
    model.pneg     = [(p, n , g         )        for p, n , g                 in model.pn    * model.eg  ]
    model.pnegt    = [(p, n , t         )        for p, n , t                 in model.pn    * model.egt ]
    model.pnnd     = [(p, n , nd        )        for p, n , nd                in model.pn    * model.nd  ]
    model.pnegr    = [(p, n , re        )        for p, n , re                in model.pn    * model.egr ]
    model.pnegs    = [(p, n , es        )        for p, n , es                in model.pn    * model.egs ]
    model.pnegnr   = [(p, n , nr        )        for p, n , nr                in model.pn    * model.egnr]
    model.pngt     = [(p, n , gt        )        for p, n , gt                in model.pn    * model.gt  ]
    model.pnhe     = [(p, n , he        )        for p, n , he                in model.pn    * model.he  ]
    model.pneh     = [(p, n , eh        )        for p, n , eh                in model.pn    * model.eh  ]
    model.pnesc    = [(p, n , esc       )        for p, n , esc               in model.pn    * model.esc ]
    model.pnhg     = [(p, n , h         )        for p, n , h                 in model.pn    * model.hg  ]
    model.pnhgs    = [(p, n , hs        )        for p, n , hs                in model.pn    * model.hgs ]
    model.pneln    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.eln ]
    model.pnela    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.ela ]
    model.pnele    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.ele ]
    model.pnels    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.els ]
    model.pnhpa    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.hpa ]
    model.pnhpc    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.hpc ]
    model.pnhpe    = [(p, n , ni, nf, cc)        for p, n , ni, nf, cc        in model.pn    * model.hpe ]
    model.pseg     = [(p, sc, g         )        for p, sc, g                 in model.psc   * model.eg  ]
    model.psegnr   = [(p, sc, nr        )        for p, sc, nr                in model.psc   * model.egnr]
    model.psegs    = [(p, sc, egs       )        for p, sc, egs               in model.psc   * model.egs ]
    model.pshgs    = [(p, sc, hgs       )        for p, sc, hgs               in model.psc   * model.hgs ]
    model.psehs    = [(p, sc, ess       )        for p, sc, ess               in model.psc   * model.ehs ]

    model.psn      = [(p, sc, n            )     for p, sc, n                 in model.psc   * model.n   ]
    model.psner    = [(p, sc, n, er        )     for p, sc, n, er             in model.psn   * model.er  ]
    model.psned    = [(p, sc, n, ed        )     for p, sc, n, ed             in model.psn   * model.ed  ]
    model.psneg    = [(p, sc, n, g         )     for p, sc, n, g              in model.psn   * model.eg  ]
    model.psnege2h = [(p, sc, n, g         )     for p, sc, n, g              in model.psn   * model.ege2h]
    model.psnehg   = [(p, sc, n, gh        )     for p, sc, n, gh             in model.psn   * model.ehg ]
    model.psnegt   = [(p, sc, n, t         )     for p, sc, n, t              in model.psn   * model.egt ]
    model.psnegc   = [(p, sc, n, gc        )     for p, sc, n, gc             in model.psn   * model.egc ]
    model.psnegr   = [(p, sc, n, re        )     for p, sc, n, re             in model.psn   * model.egr ]
    model.psnegnr  = [(p, sc, n, nr        )     for p, sc, n, nr             in model.psn   * model.egnr]
    model.psnegs   = [(p, sc, n, es        )     for p, sc, n, es             in model.psn   * model.egs ]
    model.psnegsc  = [(p, sc, n, ec        )     for p, sc, n, ec             in model.psn   * model.egsc]
    model.psnhg    = [(p, sc, n, hz        )     for p, sc, n, hz             in model.psn   * model.hg  ]
    model.psnnd    = [(p, sc, n, nd        )     for p, sc, n, nd             in model.psn   * model.nd  ]
    model.psngt    = [(p, sc, n, gt        )     for p, sc, n, gt             in model.psn   * model.gt  ]
    model.psneh    = [(p, sc, n, eh        )     for p, sc, n, eh             in model.psn   * model.eh  ]
    model.psnhe    = [(p, sc, n, he        )     for p, sc, n, he             in model.psn   * model.he  ]
    model.psnehs   = [(p, sc, n, es        )     for p, sc, n, es             in model.psn   * model.ehs ]
    model.psnhr    = [(p, sc, n, hr        )     for p, sc, n, hr             in model.psn   * model.hr  ]
    model.psnhd    = [(p, sc, n, hd        )     for p, sc, n, hd             in model.psn   * model.hd  ]
    model.psnhg    = [(p, sc, n, h         )     for p, sc, n, h              in model.psn   * model.hg  ]
    model.psnhgt   = [(p, sc, n, t         )     for p, sc, n, t              in model.psn   * model.hgt ]
    model.psnhgs   = [(p, sc, n, hs        )     for p, sc, n, hs             in model.psn   * model.hgs ]
    model.psnhgsc  = [(p, sc, n, hgsc      )     for p, sc, n, hgsc           in model.psn   * model.hgsc]
    model.psnesc   = [(p, sc, n, es        )     for p, sc, n, es             in model.psn   * model.esc ]
    model.psne2h   = [(p, sc, n, h         )     for p, sc, n, h              in model.psn   * model.e2h ]
    model.psnh2e   = [(p, sc, n, g         )     for p, sc, n, g              in model.psn   * model.h2e ]
    model.psneln   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.eln ]
    model.psnela   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.ela ]
    model.psnele   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.ele ]
    model.psnels   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.els ]
    model.psnhpn   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.hpn ]
    model.psnhpa   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.hpa ]
    model.psnhpe   = [(p, sc, n, ni, nf, cc)     for p, sc, n, ni, nf, cc     in model.psn   * model.hpe ]

    # define AC existing  lines
    model.elea = Set(initialize=model.ele, ordered=False, doc='AC existing  lines and non-switchable lines', filter=lambda model,value: value in model.ele and not parameters_dict['pEleNetType'][value] == 'DC')
    # define AC candidate lines
    model.elca = Set(initialize=model.ela, ordered=False, doc='AC candidate lines and     switchable lines', filter=lambda model,value: value in model.elc and not parameters_dict['pEleNetType'][value] == 'DC')

    model.elaa = model.elea | model.elca

    # define DC existing  lines
    model.eled = Set(initialize=model.ele, ordered=False, doc='DC existing  lines and non-switchable lines', filter=lambda model,value: value in model.ele and     parameters_dict['pEleNetType'][value] == 'DC')
    # define DC candidate lines
    model.elcd = Set(initialize=model.ela, ordered=False, doc='DC candidate lines and     switchable lines', filter=lambda model,value: value in model.elc and     parameters_dict['pEleNetType'][value] == 'DC')

    model.elad = model.eled | model.elcd

    # %% Getting the current year
    pCurrentYear = datetime.date.today().year
    if parameters_dict['pParEconomicBaseYear'] == 0:
        parameters_dict['pParEconomicBaseYear'] = pCurrentYear

    if parameters_dict['pParAnnualDiscountRate'] == 0.0:
        parameters_dict['pDiscountFactor'] = pd.Series(data=[                                                  parameters_dict['pPeriodWeight'][p]                                                                                                                                                                                       for p in model.p], index=model.p)
    else:
        parameters_dict['pDiscountFactor'] = pd.Series(data=[((1.0+parameters_dict['pParAnnualDiscountRate'])**parameters_dict['pPeriodWeight'][p]-1.0) / (parameters_dict['pParAnnualDiscountRate']*(1.0+parameters_dict['pParAnnualDiscountRate'])**(parameters_dict['pPeriodWeight'][p]-1+p-parameters_dict['pParEconomicBaseYear'])) for p in model.p], index=model.p)

    # %% inverse index node to electricity/hydrogen unit
    model.n2eg       = Set(initialize=sorted((parameters_dict['pEleGenNode'][eg], eg)   for     eg     in model.eg                                                                ), ordered=False, doc='node to generator'      )
    model.z2eg       = Set(initialize=sorted((zn,eg)                                   for (nd,eg,zn) in model.n2eg * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to generator'      )

    model.n2hg       = Set(initialize=sorted((parameters_dict['pHydGenNode'][hg], hg)   for     hg     in model.hg                                                                ), ordered=False, doc='node to generator'      )
    model.z2hg       = Set(initialize=sorted((zn,hg)                                   for (nd,hg,zn) in model.n2hg * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to generator'      )

    # inverse index generator to technology
    model.t2eg       = Set(initialize=sorted((parameters_dict['pEleGenTechnology'][eg],eg) for     eg     in model.eg              if parameters_dict['pEleGenTechnology'][eg] in model.gt), ordered=False, doc='technology to generator')
    model.t2hg       = Set(initialize=sorted((parameters_dict['pHydGenTechnology'][hg],hg) for     hg     in model.hg              if parameters_dict['pHydGenTechnology'][hg] in model.gt), ordered=False, doc='technology to generator')

    # inverse index generator to retailer
    model.r2eg       = Set(initialize=sorted((parameters_dict['pEleGenRetailer'][eg], eg)  for     eg     in model.eg                                                             ), ordered=False, doc='retailer to generator'  )
    model.r2hg       = Set(initialize=sorted((parameters_dict['pHydGenRetailer'][hg], hg)  for     hg     in model.hg                                                             ), ordered=False, doc='retailer to generator'  )

    # inverse index node to electricity/hydrogen demand
    model.n2ed       = Set(initialize=sorted((parameters_dict['pEleDemNode'][ed], ed)  for     ed     in model.ed                                                                 ), ordered=False, doc='node to demand'         )
    model.z2ed       = Set(initialize=sorted((zn,ed)                                   for (nd,ed,zn) in model.n2ed * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to demand'         )

    model.n2hd       = Set(initialize=sorted((parameters_dict['pHydDemNode'][hd], hd)  for     hd     in model.hd                                                                 ), ordered=False, doc='node to demand'         )
    model.z2hd       = Set(initialize=sorted((zn,hd)                                   for (nd,hd,zn) in model.n2hd * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to demand'         )

    # inverse index demand to retailer
    model.r2ed       = Set(initialize=sorted((parameters_dict['pEleDemRetailer'][ed], ed)  for     ed     in model.ed                                                             ), ordered=False, doc='retailer to demand'     )
    model.r2hd       = Set(initialize=sorted((parameters_dict['pHydDemRetailer'][hd], hd)  for     hd     in model.hd                                                             ), ordered=False, doc='retailer to demand'     )

    # inverse index node to electricity/hydrogen retail
    model.n2er       = Set(initialize=sorted((parameters_dict['pEleRetNode'][er], er)  for     er     in model.er                                                                 ), ordered=False, doc='node to retail'         )
    model.z2er       = Set(initialize=sorted((zn,er)                                   for (nd,er,zn) in model.n2er * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to retail'         )

    model.n2hr       = Set(initialize=sorted((parameters_dict['pHydRetNode'][hr], hr)  for     hr     in model.hr                                                                 ), ordered=False, doc='node to retail'         )
    model.z2hr       = Set(initialize=sorted((zn,hr)                                   for (nd,hr,zn) in model.n2hr * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to retail'         )

    # ESS and RES technologies
    model.et         = Set(initialize=model.gt, ordered=False, doc='Electricity ESS technologies', filter=lambda model, gt: gt in model.gt and sum(1 for egs in model.egs if (gt, egs) in model.t2eg))
    model.ht         = Set(initialize=model.gt, ordered=False, doc='Hydrogen    ESS technologies', filter=lambda model, gt: gt in model.gt and sum(1 for hgs in model.hgs if (gt, hgs) in model.t2hg))
    model.rt         = Set(initialize=model.gt, ordered=False, doc='RES technologies'            , filter=lambda model, gt: gt in model.gt and sum(1 for egr in model.egr if (gt, egr) in model.t2eg))

    model.pset  = [(p, sc, et)    for p, sc, et    in model.ps  * model.et]
    model.psht  = [(p, sc, ht)    for p, sc, ht    in model.ps  * model.ht]
    model.psrt  = [(p, sc, rt)    for p, sc, rt    in model.ps  * model.rt]
    model.psnet = [(p, sc, n, et) for p, sc, n, et in model.psn * model.et]
    model.psnht = [(p, sc, n, ht) for p, sc, n, ht in model.psn * model.ht]
    model.psnrt = [(p, sc, n, rt) for p, sc, n, rt in model.psn * model.rt]

    log_time('--- Defining the instrumental sets:', start_time, ind_log=indlog)
    start_time = time.time()

    # --- TEMPORAL REFERENCE FOR THE MODEL ---

    # Assuming model.n is ordered like ['t0001', 't0002', ..., 'tNNNN']
    n_list = list(model.n)

    # Reference position of DateModel in the year
    hour_of_day = DateModel.hour
    day_of_year = DateModel.timetuple().tm_yday
    hour_of_year = (day_of_year - 1) * 24 + hour_of_day

    start_dt = DateModel - pd.Timedelta(hours=(hour_of_year))

    # Index only by n
    idx_n = pd.Index(n_list, name='n')
    pDate = pd.DataFrame(index=idx_n)

    # Vectorized DateTime for each n (no loops over p, sc)
    pDate['DateTime'] = start_dt + pd.to_timedelta(np.arange(len(idx_n)), unit='h')

    # Components
    pDate['Month'] = pDate['DateTime'].dt.month.astype(int)
    pDate['Day'] = pDate['DateTime'].dt.dayofyear.astype(int)
    pDate['Hour'] = pDate['DateTime'].dt.hour.astype(int)
    pDate['HourOfYear'] = (pDate['Day'] - 1) * 24 + pDate['Hour']

    parameters_dict['pDate'] = pDate

    log_time('--- Creating the temporal reference dataframe:', start_time, ind_log=indlog)
    start_time = time.time()

    # --- Fundamental time sets ---
    # Unique values
    model.hoy = Set(initialize=sorted(pDate['HourOfYear'].unique()))
    model.doy = Set(initialize=sorted(pDate['Day'].unique()))
    model.moy = Set(initialize=sorted(pDate['Month'].unique()))

    # n -> month/day
    model.n2m = Set(dimen=2, initialize=[(n, m) for n, m in zip(pDate.index, pDate['Month'])])

    model.n2d = Set(dimen=2, initialize=[(n, d) for n, d in zip(pDate.index, pDate['Day'])])

    # day -> month (unique pairs)
    d2m_pairs = list(dict.fromkeys(zip(pDate['Day'], pDate['Month'])))
    model.d2m = Set(dimen=2, initialize=d2m_pairs)

    log_time('--- Defining the fundamental time sets:', start_time, ind_log=indlog)
    start_time = time.time()

    # --- Composite time sets ---
    model.psm = Set(dimen=3, initialize=lambda m: product(m.p, m.sc, m.moy))
    model.psd = Set(dimen=3, initialize=lambda m: product(m.p, m.sc, m.doy))

    # For quick lookup
    n2d_dict = dict(model.n2d.data())  # n -> d
    d2m_dict = {d: m for d, m in d2m_pairs}  # d -> m

    model.n2d_dict = n2d_dict
    model.d2m_dict = d2m_dict

    model.psdn = Set(dimen=4, initialize=_psdn_init(model, n2d_dict))
    model.psmd = Set(dimen=4, initialize=_psmd_init(model, d2m_dict))
    model.psmdn = Set(dimen=5, initialize=_psmdn_init(model, n2d_dict, d2m_dict))

    # psm × {er, hr, hd}
    model.psmer  = Set(dimen=4, initialize=lambda m: _cartesian_4_psm(m, m.er))
    model.psmhr  = Set(dimen=4, initialize=lambda m: _cartesian_4_psm(m, m.hr))
    model.psmhd  = Set(dimen=4, initialize=lambda m: _cartesian_4_psm(m, m.hd))

    # psd × {er, ed, hr, hd, egs, hgs}
    model.psder  = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.er))
    model.psded  = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.ed))
    model.psdhr  = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.hr))
    model.psdhd  = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.hd))
    model.psdegs = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.egs))
    model.psdhgs = Set(dimen=4, initialize=lambda m: _cartesian_4_psd(m, m.hgs))

    # Now define each:
    model.psdner  = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psner', m.er))
    model.psdned  = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psned', m.ed))
    model.psdnhr  = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psnhr', m.hr))
    model.psdnhd  = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psnhd', m.hd))
    model.psdnegs = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psnegs', m.egs))
    model.psdnhgs = Set(dimen=5, initialize=lambda m: _extend_psdn_filtered(m, 'psnhgs', m.hgs))

    log_time('--- Defining the temporal reference for the model:', start_time, ind_log=indlog)
    start_time = time.time()

    # minimum and maximum variable power, charge, and storage capacity
    dict_sector = {'Ele': model.eg, 'Hyd': model.hg}
    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector}MinPower'   ] = parameters_dict['pVarMinGeneration'  ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumPower'   ])
        parameters_dict[f'p{sector}MaxPower'   ] = parameters_dict['pVarMaxGeneration'  ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumPower'   ])
        parameters_dict[f'p{sector}MinCharge'  ] = parameters_dict['pVarMinConsumption' ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumCharge'  ])
        parameters_dict[f'p{sector}MaxCharge'  ] = parameters_dict['pVarMaxConsumption' ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumCharge'  ])
        parameters_dict[f'p{sector}MinStorage' ] = parameters_dict['pVarMinStorage'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumStorage' ])
        parameters_dict[f'p{sector}MaxStorage' ] = parameters_dict['pVarMaxStorage'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumStorage' ])
        parameters_dict[f'p{sector}MinInflows' ] = parameters_dict['pVarMinInflows'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinInflowsCons' ])
        parameters_dict[f'p{sector}MaxInflows' ] = parameters_dict['pVarMaxInflows'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaxInflowsCons' ])
        parameters_dict[f'p{sector}MinOutflows'] = parameters_dict['pVarMinOutflows'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinOutflowsProd'])
        parameters_dict[f'p{sector}MaxOutflows'] = parameters_dict['pVarMaxOutflows'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaxOutflowsProd'])
        parameters_dict[f'p{sector}MinFuelCost'] = parameters_dict['pVarMinFuelCost'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenLinearVarCost'  ])
        parameters_dict[f'p{sector}MaxFuelCost'] = parameters_dict['pVarMaxFuelCost'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenLinearVarCost'  ])
        parameters_dict[f'p{sector}MinCO2Cost' ] = parameters_dict['pVarMinEmissionCost'][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenCO2EmissionCost'])
        parameters_dict[f'p{sector}MaxCO2Cost' ] = parameters_dict['pVarMaxEmissionCost'][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenCO2EmissionCost'])

    # parameters_dict['pMaxEnergyBuy' ] = parameters_dict['pVarEnergyCost' ].replace(0.0, parameters_dict['pEleRetMaximumEnergyBuy' ])
    # parameters_dict['pMinEnergyBuy' ] = parameters_dict['pVarEnergyCost' ].replace(0.0, parameters_dict['pEleRetMinimumEnergyBuy' ])
    # parameters_dict['pMaxEnergySell'] = parameters_dict['pVarEnergyPrice'].replace(0.0, parameters_dict['pEleRetMaximumEnergySell'])
    # parameters_dict['pMinEnergySell'] = parameters_dict['pVarEnergyPrice'].replace(0.0, parameters_dict['pEleRetMinimumEnergySell'])

    for idx in ['MinPower', 'MaxPower', 'MinCharge', 'MaxCharge', 'MinStorage', 'MaxStorage', 'MinInflows', 'MaxInflows', 'MinOutflows', 'MaxOutflows', 'MinFuelCost', 'MaxFuelCost', 'MinCO2Cost', 'MaxCO2Cost']:
        for sector in ['Ele', 'Hyd']:
            parameters_dict[f'p{sector}{idx}'] = parameters_dict[f'p{sector}{idx}'].where(parameters_dict[f'p{sector}{idx}'] > 0.0, other=0.0)

    # for idx in ['MaxEnergyBuy', 'MinEnergyBuy', 'MaxEnergySell', 'MinEnergySell']:
    #     parameters_dict[f'p{idx}'] = parameters_dict[f'p{idx}'].where(parameters_dict[f'p{idx}'] > 0.0, other=0.0)

    # parameter that allows the initial inventory to change with load level
    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector}InitialInventory'] = pd.DataFrame([parameters_dict[f'p{sector}GenInitialStorage'] * model.factor1] * len(parameters_dict[f'p{sector}MinStorage'].index), index=parameters_dict[f'p{sector}MinStorage'].index, columns=parameters_dict[f'p{sector}GenInitialStorage'].index)

    # minimum up- and downtime and maximum shift time converted to an integer number of time steps
    for idx in ['Up', 'Down']:
        parameters_dict[f'pEleGen{idx}Time'] = round(parameters_dict[f'pEleGen{idx}Time'] / parameters_dict['pParTimeStep']).astype('int')

    # %% definition of the time-steps leap to observe the stored energy at an ESS
    idxCycle            = dict()
    idxCycle[0        ] = 8736
    idxCycle[0.0      ] = 8736
    idxCycle['Hourly' ] = 1
    idxCycle['Daily'  ] = 1
    idxCycle['Weekly' ] = round(24  / parameters_dict['pParTimeStep'])
    idxCycle['Monthly'] = round(168 / parameters_dict['pParTimeStep'])
    idxCycle['Yearly' ] = round(168 / parameters_dict['pParTimeStep'])

    idxOutflows            = dict()
    idxOutflows[0        ] = 8736
    idxOutflows[0.0      ] = 8736
    idxOutflows['Hourly' ] =    1
    idxOutflows['Daily'  ] = round(24   / parameters_dict['pParTimeStep'])
    idxOutflows['Weekly' ] = round(168  / parameters_dict['pParTimeStep'])
    idxOutflows['Monthly'] = round(672  / parameters_dict['pParTimeStep'])
    idxOutflows['Yearly' ] = round(8736 / parameters_dict['pParTimeStep'])

    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector}CycleTimeStep'   ] = parameters_dict[f'p{sector}GenStorageType' ].map(idxCycle                                                                                                                                                            ).fillna(8736).astype('int')
        parameters_dict[f'p{sector}OutflowsTimeStep'] = parameters_dict[f'p{sector}GenOutflowsType'].map(idxOutflows).where(parameters_dict['pVarMinOutflows'][dict_sector[sector]].sum() + parameters_dict['pVarMaxOutflows'][dict_sector[sector]].sum() > 0.0, other = 8736).fillna(8736).astype('int')
        parameters_dict[f'p{sector}CycleTimeStep'   ] = pd.concat([parameters_dict[f'p{sector}CycleTimeStep'], parameters_dict[f'p{sector}OutflowsTimeStep']], axis=1).min(axis=1)

    # mapping the string pParDemandType using the idxCycle dictionary
    parameters_dict['pParDemandType'] = idxOutflows[parameters_dict['pParDemandType']]
    # drop levels with duration 0
    parameters_dict['pDuration']      = parameters_dict['pDuration'].loc           [model.psn  ]

    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector}MinPower'        ] = parameters_dict[f'p{sector}MinPower'        ].loc[model.psn]
        parameters_dict[f'p{sector}MaxPower'        ] = parameters_dict[f'p{sector}MaxPower'        ].loc[model.psn]
        parameters_dict[f'p{sector}MinCharge'       ] = parameters_dict[f'p{sector}MinCharge'       ].loc[model.psn]
        parameters_dict[f'p{sector}MaxCharge'       ] = parameters_dict[f'p{sector}MaxCharge'       ].loc[model.psn]
        parameters_dict[f'p{sector}MinStorage'      ] = parameters_dict[f'p{sector}MinStorage'      ].loc[model.psn]
        parameters_dict[f'p{sector}MaxStorage'      ] = parameters_dict[f'p{sector}MaxStorage'      ].loc[model.psn]
        parameters_dict[f'p{sector}MinInflows'      ] = parameters_dict[f'p{sector}MinInflows'      ].loc[model.psn]
        parameters_dict[f'p{sector}MaxInflows'      ] = parameters_dict[f'p{sector}MaxInflows'      ].loc[model.psn]
        parameters_dict[f'p{sector}MinOutflows'     ] = parameters_dict[f'p{sector}MinOutflows'     ].loc[model.psn]
        parameters_dict[f'p{sector}MaxOutflows'     ] = parameters_dict[f'p{sector}MaxOutflows'     ].loc[model.psn]
        parameters_dict[f'p{sector}InitialInventory'] = parameters_dict[f'p{sector}InitialInventory'].loc[model.psn]

    parameters_dict['pVarMaxDemand'     ] = parameters_dict['pVarMaxDemand'     ].loc[model.psn]
    parameters_dict['pVarMinDemand'     ] = parameters_dict['pVarMinDemand'     ].loc[model.psn]
    parameters_dict['pVarEnergyCost'    ] = parameters_dict['pVarEnergyCost'    ].loc[model.psn]   # already 1/factor1 at read (audit C38)
    parameters_dict['pVarEnergyPrice'   ] = parameters_dict['pVarEnergyPrice'   ].loc[model.psn]   # already 1/factor1 at read (audit C38)
    parameters_dict['pVarMinInflows'    ] = parameters_dict['pVarMinInflows'    ].loc[model.psn]
    parameters_dict['pVarMaxInflows'    ] = parameters_dict['pVarMaxInflows'    ].loc[model.psn]
    parameters_dict['pVarMinOutflows'   ] = parameters_dict['pVarMinOutflows'   ].loc[model.psn]
    parameters_dict['pVarMaxOutflows'   ] = parameters_dict['pVarMaxOutflows'   ].loc[model.psn]

    for idx in model.reserves_prefixes:
        parameters_dict[f'pOperatingReservePrice_{idx}'     ] = parameters_dict[f'pOperatingReservePrice_{idx}'     ].loc[model.psn]
        parameters_dict[f'pOperatingReserveRequire_{idx}'   ] = parameters_dict[f'pOperatingReserveRequire_{idx}'   ].loc[model.psn]
        parameters_dict[f'pOperatingReserveActivation_{idx}'] = parameters_dict[f'pOperatingReserveActivation_{idx}'].loc[model.psn]

    # values < 1e-5 times the maximum system demand are converted to 0
    pEleEpsilon = (parameters_dict['pVarMaxDemand'][[ed for ed in model.ed]].sum(axis=1).max()) * 1e-5
    pHydEpsilon = (parameters_dict['pVarMaxDemand'][[hd for hd in model.hd]].sum(axis=1).max()) * 1e-5

    # these parameters are in GW or tH2
    for sector in ['Ele', 'Hyd']:
        if sector == 'Ele':
            pEpsilon = pEleEpsilon
        else:
            pEpsilon = pHydEpsilon

        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinPower'        , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxPower'        , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinCharge'       , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxCharge'       , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinStorage'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxStorage'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinInflows'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxInflows'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinOutflows'     , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxOutflows'     , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinFuelCost'     , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxFuelCost'     , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MinCO2Cost'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxCO2Cost'      , dict_sector[sector], pEpsilon)
        _apply_mask_and_set_zero(parameters_dict, f'p{sector}InitialInventory', dict_sector[sector], pEpsilon)

    _apply_mask_and_set_zero(parameters_dict, 'pVarMaxDemand'     , model.ed, pEleEpsilon)
    _apply_mask_and_set_zero(parameters_dict, 'pVarMinDemand'     , model.ed, pEleEpsilon)
    _apply_mask_and_set_zero(parameters_dict, 'pVarMaxDemand'     , model.hd, pHydEpsilon)
    _apply_mask_and_set_zero(parameters_dict, 'pVarMinDemand'     , model.hd, pHydEpsilon)

    for idx in model.reserves_prefixes:
        parameters_dict[f'pOperatingReservePrice_{idx}'     ][parameters_dict[f'pOperatingReservePrice_{idx}'     ] < pEleEpsilon] = 0.0
        parameters_dict[f'pOperatingReserveRequire_{idx}'   ][parameters_dict[f'pOperatingReserveRequire_{idx}'   ] < pEleEpsilon] = 0.0
        parameters_dict[f'pOperatingReserveActivation_{idx}'][parameters_dict[f'pOperatingReserveActivation_{idx}'] < pEleEpsilon] = 0.0

    for sector in ['Ele', 'Hyd']:
        if sector == 'Ele':
            pEpsilon = pEleEpsilon
        else:
            pEpsilon = pHydEpsilon
        parameters_dict[f'p{sector}NetTTC'   ].update(pd.Series([0.0 for ni, nf, cc in parameters_dict[f'p{sector}NetTTC'].index if parameters_dict[f'p{sector}NetTTC'   ][ni, nf, cc] < pEpsilon], index=[(ni, nf, cc) for ni, nf, cc in parameters_dict[f'p{sector}NetTTC'].index if parameters_dict[f'p{sector}NetTTC'   ][ni, nf, cc] < pEpsilon], dtype='float64'))
        parameters_dict[f'p{sector}NetTTCBck'].update(pd.Series([0.0 for ni, nf, cc in parameters_dict[f'p{sector}NetTTC'].index if parameters_dict[f'p{sector}NetTTCBck'][ni, nf, cc] < pEpsilon], index=[(ni, nf, cc) for ni, nf, cc in parameters_dict[f'p{sector}NetTTC'].index if parameters_dict[f'p{sector}NetTTCBck'][ni, nf, cc] < pEpsilon], dtype='float64'))
        parameters_dict[f'p{sector}NetTTCMax'] = parameters_dict[f'p{sector}NetTTC'].where(parameters_dict[f'p{sector}NetTTC'] > parameters_dict[f'p{sector}NetTTCBck'], parameters_dict[f'p{sector}NetTTCBck'])

        parameters_dict[f'p{sector}MaxPower2ndBlock' ] = parameters_dict[f'p{sector}MaxPower' ] - parameters_dict[f'p{sector}MinPower']
        parameters_dict[f'p{sector}MaxCharge2ndBlock'] = parameters_dict[f'p{sector}MaxCharge'] - parameters_dict[f'p{sector}MinCharge']
        parameters_dict[f'p{sector}MaxCapacity'      ] = parameters_dict[f'p{sector}MaxPower' ].where(parameters_dict[f'p{sector}MaxPower'] > parameters_dict[f'p{sector}MaxCharge'], parameters_dict[f'p{sector}MaxCharge'])

        parameters_dict[f'p{sector}MaxPower2ndBlock' ][parameters_dict[f'p{sector}MaxPower2ndBlock' ] < pEpsilon] = 0.0
        parameters_dict[f'p{sector}MaxCharge2ndBlock'][parameters_dict[f'p{sector}MaxCharge2ndBlock'] < pEpsilon] = 0.0

        # replace < 0.0 by 0.0
        parameters_dict[f'p{sector}MaxPower2ndBlock' ] = parameters_dict[f'p{sector}MaxPower2ndBlock' ].where(parameters_dict[f'p{sector}MaxPower2ndBlock' ] > 0.0, 0.0)
        parameters_dict[f'p{sector}MaxCharge2ndBlock'] = parameters_dict[f'p{sector}MaxCharge2ndBlock'].where(parameters_dict[f'p{sector}MaxCharge2ndBlock'] > 0.0, 0.0)

        parameters_dict[f'p{sector}MaxInflows2ndBlock'] = parameters_dict[f'p{sector}MaxInflows' ] - parameters_dict[f'p{sector}MinInflows' ]
        parameters_dict[f'p{sector}MaxInflows2ndBlock'][parameters_dict[f'p{sector}MaxInflows2ndBlock' ] < pEleEpsilon] = 0.0

        parameters_dict[f'p{sector}MaxOutflows2ndBlock'] = parameters_dict[f'p{sector}MaxOutflows'] - parameters_dict[f'p{sector}MinOutflows']
        parameters_dict[f'p{sector}MaxOutflows2ndBlock'][parameters_dict[f'p{sector}MaxOutflows2ndBlock'] < pEleEpsilon] = 0.0
        # replace < 0.0 by 0.0
        parameters_dict[f'p{sector}MaxOutflows2ndBlock'] = parameters_dict[f'p{sector}MaxOutflows2ndBlock'].where(parameters_dict[f'p{sector}MaxOutflows2ndBlock'] > 0.0, 0.0)

    # drop generators not nr or ec
    for sector in ['Ele', 'Hyd']:
        if sector == 'Ele':
            set_sector = model.egt
            parameters_dict[f'p{sector}GenStartUpCost'         ] = parameters_dict[f'p{sector}GenStartUpCost'         ].loc[set_sector]
            parameters_dict[f'p{sector}GenShutDownCost'        ] = parameters_dict[f'p{sector}GenShutDownCost'        ].loc[set_sector]
            parameters_dict[f'p{sector}GenBinaryCommitment'    ] = parameters_dict[f'p{sector}GenBinaryCommitment'    ].loc[set_sector]
            parameters_dict[f'p{sector}GenStorageInvestment'   ] = parameters_dict[f'p{sector}GenStorageInvestment'   ].loc[set_sector]
            parameters_dict[f'p{sector}GenMaxInflowsCons'      ] = parameters_dict[f'p{sector}GenMaxInflowsCons'      ].loc[set_sector]
            parameters_dict[f'p{sector}GenMinInflowsCons'      ] = parameters_dict[f'p{sector}GenMinInflowsCons'      ].loc[set_sector]
            parameters_dict[f'p{sector}GenMaxOutflowsProd'     ] = parameters_dict[f'p{sector}GenMaxOutflowsProd'     ].loc[set_sector]
            parameters_dict[f'p{sector}GenMinOutflowsProd'     ] = parameters_dict[f'p{sector}GenMinOutflowsProd'     ].loc[set_sector]

    # drop lines not lc or ll
    parameters_dict['pEleNetFixedInvestmentCost'] = parameters_dict['pEleNetFixedInvestmentCost'].loc[model.elc]
    parameters_dict['pEleNetInvestmentLo'       ] = parameters_dict['pEleNetInvestmentLo'       ].loc[model.elc]
    parameters_dict['pEleNetInvestmentUp'       ] = parameters_dict['pEleNetInvestmentUp'       ].loc[model.elc]

    # this option avoids a warning in the following assignments
    pd.options.mode.chained_assignment = None

    # drop pipelines not pc
    parameters_dict['pHydNetFixedInvestmentCost'] = parameters_dict['pHydNetFixedInvestmentCost'].loc[model.hpc]
    parameters_dict['pHydNetInvestmentLo'       ] = parameters_dict['pHydNetInvestmentLo'       ].loc[model.hpc]
    parameters_dict['pHydNetInvestmentUp'       ] = parameters_dict['pHydNetInvestmentUp'       ].loc[model.hpc]

    # replace very small costs by 0
    pEpsilon = 1e-4  # this value in €/GWh is related to the smallest reduced cost
    parameters_dict['pEleGenLinearTerm'  ][parameters_dict['pEleGenLinearTerm'  ] < pEpsilon] = 0.0
    parameters_dict['pEleGenConstantTerm'][parameters_dict['pEleGenConstantTerm'] < pEpsilon] = 0.0
    #

    parameters_dict['pPeriodProb'] = parameters_dict['pScenProb'].copy()

    for p,sc in model.ps:
        # periods and scenarios are going to be solved together with their weight and probability
        parameters_dict['pPeriodProb'][p,sc] = parameters_dict['pPeriodWeight'][p] * parameters_dict['pScenProb'][p,sc]

    # load levels multiple of cycles for each ESS/generator
    model.negs  = [(n,egs )    for n,egs   in model.n * model.egs  if model.n.ord(n) % parameters_dict['pEleCycleTimeStep'   ][egs ] == 0]
    model.negsc = [(n,egsc)    for n,egsc  in model.n * model.egsc if model.n.ord(n) % parameters_dict['pEleCycleTimeStep'   ][egsc] == 0]
    model.negso = [(n,egs )    for n,egs   in model.n * model.egs  if model.n.ord(n) % parameters_dict['pEleOutflowsTimeStep'][egs ] == 0]
    model.nhgs  = [(n,hgs )    for n,hgs   in model.n * model.hgs  if model.n.ord(n) % parameters_dict['pHydCycleTimeStep'   ][hgs ] == 0]
    model.nhgsc = [(n,hgsc)    for n,hgsc  in model.n * model.hgsc if model.n.ord(n) % parameters_dict['pHydCycleTimeStep'   ][hgsc] == 0]
    model.nhgso = [(n,hgs )    for n,hgs   in model.n * model.hgs  if model.n.ord(n) % parameters_dict['pHydOutflowsTimeStep'][hgs ] == 0]

    # # ESS with outflows
    model.psegsi = [(p,sc,egs) for p,sc,egs in model.psegs if sum(parameters_dict['pVarMaxInflows' ][egs][p,sc,n2] for n2 in model.n2)]
    model.psegso = [(p,sc,egs) for p,sc,egs in model.psegs if sum(parameters_dict['pVarMaxOutflows'][egs][p,sc,n2] for n2 in model.n2)]
    model.pshgsi = [(p,sc,hgs) for p,sc,hgs in model.pshgs if sum(parameters_dict['pVarMaxInflows' ][hgs][p,sc,n2] for n2 in model.n2)]
    model.pshgso = [(p,sc,hgs) for p,sc,hgs in model.pshgs if sum(parameters_dict['pVarMaxOutflows'][hgs][p,sc,n2] for n2 in model.n2)]

    # if line length = 0 changed to geographical distance with an additional 10%
    for network in ['Ele', 'Hyd']:
        if network == 'Ele':
            snet = model.ela
        else:
            snet = model.hpa
        for ni, nf, cc in snet:
            if parameters_dict[f'p{network}NetLength'][ni,nf,cc] == 0.0:
                parameters_dict[f'p{network}NetLength'][ni,nf,cc]   =  1.1 * 6371 * 2 * math.asin(math.sqrt(math.pow(math.sin((parameters_dict['pNodeLat'][nf]-parameters_dict['pNodeLat'][ni])*math.pi/180/2),2) + math.cos(parameters_dict['pNodeLat'][ni]*math.pi/180)*math.cos(parameters_dict['pNodeLat'][nf]*math.pi/180)*math.pow(math.sin((parameters_dict['pNodeLon'][nf]-parameters_dict['pNodeLon'][ni])*math.pi/180/2),2)))

    # thermal and variable units ordered by increasing variable cost
    model.go = parameters_dict['pEleGenLinearTerm'].sort_values().index

    # remove the elements in model.go if they are not in model.eg
    model.go = [go for go in model.go if go in model.eg]

    # determine the initial committed units and their output
    parameters_dict['pEleInitialOutput'] = pd.Series([0.0]*(len(model.ps)*len(model.eg)), model.ps * model.eg)
    parameters_dict['pEleInitialUC'    ] = pd.Series([0  ]*(len(model.ps)*len(model.eg)), model.ps * model.eg)
    for p,sc in model.ps:
        parameters_dict['pEleSystemOutput'] = 0.0
        for go in model.go:
            n1 = next(iter(model.n))
            if parameters_dict['pEleSystemOutput'] < sum(parameters_dict['pVarMaxDemand'][ed][p,sc,n1] for ed in model.ed):
                if   go in model.egr:
                    parameters_dict['pEleInitialOutput'][p,sc,go] = parameters_dict['pEleMaxPower'][go][p,sc,n1]
                elif go in model.eg:
                    parameters_dict['pEleInitialOutput'][p,sc,go] = parameters_dict['pEleMinPower'][go][p,sc,n1]
                parameters_dict['pEleInitialUC'    ][p,sc,go] = 1
                parameters_dict['pEleSystemOutput' ]     += parameters_dict['pEleInitialOutput'][p,sc,go]
            # calculating if the unit was committed before of the time periods or not
            # The carry-over only applies to a unit that was actually on (UpTimeZero > 0)
            # but has not yet served its minimum up time; without the UpTimeZero guard a
            # never-on unit (UpTimeZero == 0) would be force-committed, overriding the
            # merit-order pre-commitment above. Symmetric for the down state.
            if parameters_dict['pEleGenUpTimeZero'][go] > 0 and parameters_dict['pEleGenUpTime'][go] - parameters_dict['pEleGenUpTimeZero'][go] > 0:
                parameters_dict['pEleInitialUC'][p,sc,go] = 1
            if parameters_dict['pEleGenDownTimeZero'][go] > 0 and parameters_dict['pEleGenDownTime'][go] - parameters_dict['pEleGenDownTimeZero'][go] > 0:
                parameters_dict['pEleInitialUC'][p,sc,go] = 0

    # determine the initial committed hydrogen units and their output
    parameters_dict['pHydInitialOutput'] = pd.Series([0.0]*(len(model.ps)*len(model.hg)), model.ps * model.hg)
    parameters_dict['pHydInitialUC'    ] = pd.Series([0  ]*(len(model.ps)*len(model.hg)), model.ps * model.hg)
    # Pre-horizon standby state of the electrolysers (default off). Used by the standby
    # transition constraint so standby at the first step is only reachable when the unit
    # was warm (on or in standby) before the horizon.
    parameters_dict['pHydInitialStandBy'] = pd.Series([0  ]*(len(model.ps)*len(model.hg)), model.ps * model.hg)
    for p,sc in model.ps:
        parameters_dict['pHydSystemOutput'] = 0.0
        for hg in model.hg:
            n1 = next(iter(model.n))
            # Electrolysers (e2h) are electricity-driven loads, not dispatchable hydrogen
            # suppliers, so they are not pre-committed to cover the initial hydrogen demand;
            # their initial commitment stays 0 (off) and the optimiser decides when to run.
            if hg in model.e2h:
                continue
            if parameters_dict['pHydSystemOutput'] < sum(parameters_dict['pVarMaxDemand'][hd][p,sc,n1] for hd in model.hd):
                if   hg in model.hgr:
                    parameters_dict['pHydInitialOutput'][p,sc,hg] = parameters_dict['pHydMaxPower'][hg][p,sc,n1]
                elif hg in model.hg:
                    parameters_dict['pHydInitialOutput'][p,sc,hg] = parameters_dict['pHydMinPower'][hg][p,sc,n1]
                parameters_dict['pHydInitialUC'    ][p,sc,hg] = 1
                parameters_dict['pHydSystemOutput' ]     += parameters_dict['pHydInitialOutput'][p,sc,hg]
            # calculating if the unit was committed before of the time periods or not
            # Same UpTimeZero/DownTimeZero guard as the electricity side: only a unit that
            # was actually on (resp. off) before the horizon carries a remaining min-up
            # (resp. min-down) obligation; a never-on unit must not be force-committed.
            if parameters_dict['pHydGenUpTimeZero'][hg] > 0 and parameters_dict['pHydGenUpTime'][hg] - parameters_dict['pHydGenUpTimeZero'][hg] > 0:
                parameters_dict['pHydInitialUC'][p,sc,hg] = 1
            if parameters_dict['pHydGenDownTimeZero'][hg] > 0 and parameters_dict['pHydGenDownTime'][hg] - parameters_dict['pHydGenDownTimeZero'][hg] > 0:
                parameters_dict['pHydInitialUC'][p,sc,hg] = 0

    # load levels multiple of cycles for each ESS/generator
    model.negs         = [(n,egs ) for n,egs  in model.n * model.egs  if model.n.ord(n) %     parameters_dict['pEleCycleTimeStep'   ][egs ] == 0]
    model.negsc        = [(n,egsc) for n,egsc in model.n * model.egsc if model.n.ord(n) %     parameters_dict['pEleCycleTimeStep'   ][egsc] == 0]
    model.negso        = [(n,egs)  for n,egs  in model.n * model.egs  if model.n.ord(n) %     parameters_dict['pEleOutflowsTimeStep'][egs] == 0]

    for sector in ['Ele', 'Hyd']:
        # if sector == 'Ele':
        #     retail = model.er
        # else:
        #     retail = model.hr
        # small values are converted to 0
        pGenerationPeak   = parameters_dict[f'p{sector}MaxPower'].sum(axis=1).max()
        pEpsilon_capacity = pGenerationPeak * 1e-5
        pCostPeak         = parameters_dict[f'p{sector}GenLinearTerm'].max()
        pEpsilon_cost     = pCostPeak * model.factor1
        # pPricePeak        = parameters_dict['pVarEnergyPrice'][retail].max()         # electricity price
        # pEpsilon_price    = pPricePeak * model.factor1

        # values < 1e-5 times the maximum generation are converted to 0 for all elements in parameters_dict
        for idx in ['MinPower', 'MaxPower', 'MinCharge', 'MaxCharge', 'MinStorage', 'MaxStorage', 'MinInflows', 'MaxInflows', 'MinOutflows', 'MaxOutflows', 'MinFuelCost', 'MaxFuelCost', 'MinCO2Cost', 'MaxCO2Cost']:
            parameters_dict[f'p{sector}{idx}'] = parameters_dict[f'p{sector}{idx}'].where(parameters_dict[f'p{sector}{idx}'] > pEpsilon_capacity, other=0.0)

        # for all costs
        for idx in ['LinearTerm', 'ConstantTerm', 'StartUpCost', 'ShutDownCost', 'LinearVarCost', 'CO2EmissionCost']:
            parameters_dict[f'p{sector}Gen{idx}'] = parameters_dict[f'p{sector}Gen{idx}'].where(parameters_dict[f'p{sector}Gen{idx}'] > pEpsilon_cost, other=0.0)

        # # for all pricesi
        # for idx in ['VarEnergyPrice', 'VarEnergyCost']:
        #     if len(retail):
        #         parameters_dict[f'p{idx}'] = parameters_dict[f'p{idx}'][retail].where(parameters_dict[f'p{idx}'][retail]  > pEpsilon_price, other=0.0)

    # # calculating the availability of the unit

    # Loop through each sector and set the appropriate sector set
    for sector in ['Ele', 'Hyd']:
        set_sector = model.psneg if sector == 'Ele' else model.psnhg

        # Iterate over each index in the set
        for idx in set_sector:
            # Check if the fixed availability for the generator is enabled
            if parameters_dict[f'p{sector}GenFixedAvailability'][idx[-1]] != 1:
                parameters_dict['pVarFixedAvailability'].loc[idx[:3], idx[-1]] = 1

    df_fixed_availability = parameters_dict['pVarFixedAvailability'].stack().to_frame(name='Value')
    df_fixed_availability['Type'] = 'FixedAvailability'

    model.Par = parameters_dict

    log_time('--- Defining the parameters', start_time, ind_log=indlog)

    return model

def create_variables(model, optmodel, indlog):

    #
    print('-- Defining the variables')
    #%% start time
    StartTime = time.time()

    # %% Electrolyser piecewise-linear part-load efficiency curve (audit Phase B / B1)
    # Replaces the constant ProductionFunction (kWh/kgH2) with a part-load curve. FLAG-GATED
    # by pOptIndBinElectrolyserPWL (default 0 -> constant ProductionFunction, byte-unchanged).
    # Canonical alkaline shape (Brauns & Turek 2020, Processes 8(2):248): specific energy is
    # lowest near ~85% load and rises toward both low load and full load. The multipliers are
    # RELATIVE to the unit's full-load ProductionFunction, so at full load the PWL reproduces
    # the legacy linear conversion exactly. Each curve is 4 breakpoints (x_k = productive
    # electricity in kW, y_k = hydrogen out in kgH2/h) spanning the unit's [MinCharge, MaxCharge]
    # productive range; the SOS2 (segment-binary) convex combination in oM_ModelFormulation
    # picks the active segment.
    model.pwl_curve = {}
    model.hpwl      = []
    model.pwlbp     = list(range(4))   # breakpoint indices 0..3
    model.pwlseg    = list(range(3))   # segment indices 0..2 (between adjacent breakpoints)
    if int(model.Par.get('pOptIndBinElectrolyserPWL', 0)) == 1:
        _anchor_f    = [0.10, 0.20, 0.50, 0.85, 1.00]   # load fraction
        _anchor_mult = [1.35, 1.25, 1.08, 0.97, 1.00]   # specific energy / full-load value
        for g in model.e2h:
            pf   = float(model.Par['pHydGenProductionFunction'][g])
            pmax = max(float(model.Par['pHydMaxCharge'][g][idx]) for idx in model.psn)
            try:
                pmin = max(float(model.Par['pHydMinCharge'][g][idx]) for idx in model.psn)
            except (KeyError, ValueError):
                pmin = 0.0
            if pf <= 0.0 or pmax <= 0.0:
                continue
            fmin  = max(min(pmin / pmax, 1.0), 0.0)
            fracs = [fmin + (1.0 - fmin) * t for t in (0.0, 0.4, 0.75, 1.0)]
            model.pwl_curve[g] = [(f * pmax, (f * pmax) / (pf * float(np.interp(f, _anchor_f, _anchor_mult)))) for f in fracs]
            model.hpwl.append(g)

    # model.Peaks   = Set(initialize=[ i for i in range(1,4,1)]) # number of selected peaks hours
    if model.Par['pParNumberPowerPeaks'] == 0:
        model.Peaks   = RangeSet(1)
        # Audit C34: with no power peaks the peak-cost constraint (eTotalElePeakCost) charges
        # the power tariff with no kW quantity -- a constant added to the objective. It does
        # not change the optimal solution (a fixed offset), but it does shift the reported
        # total cost. Warn if a power tariff is configured so the offset is not mistaken for a
        # real peak charge; set pEleRetPowerTariff to 0 (or pParNumberPowerPeaks > 0) to avoid it.
        if sum(model.Par['pEleRetPowerTariff'][er] for er in model.er) > 0:
            print("WARNING (C34): pParNumberPowerPeaks == 0 but a non-zero pEleRetPowerTariff is "
                  "set; the peak cost becomes a constant objective offset with no kW quantity.")
    else:
        model.Peaks   = RangeSet(model.Par['pParNumberPowerPeaks']) # number of selected peaks hours

    #%% total variables
    setattr(optmodel, 'vTotalSCost',                       Var(                        within=            Reals, doc='total system                          cost                           [EUR]'))
    setattr(optmodel, 'vTotalCComponent',                  Var(model.ps ,     within=             Reals, doc='total system component                cost                           [EUR]'))
    setattr(optmodel, 'vTotalRComponent',                  Var(model.ps ,     within=             Reals, doc='total system component              revenue                          [EUR]'))

    # electricity and hydrogen cost components
    setattr(optmodel, 'vTotalEleNCost',                    Var(model.ps ,     within=             Reals, doc='total fixed   electricity   network   cost                           [EUR]'))
    setattr(optmodel, 'vTotalEleXCost',                    Var(model.ps ,     within=             Reals, doc='total tax and surcharges electricity  cost                           [EUR]'))
    setattr(optmodel, 'vTotalEleMCost',                    Var(model.psn,     within=             Reals, doc='total variable electricity market     cost                           [EUR]'))
    setattr(optmodel, 'vTotalHydMCost',                    Var(model.psn,     within=             Reals, doc='total variable hydrogen    market     cost                           [EUR]'))
    setattr(optmodel, 'vTotalEleOCost',                    Var(model.psn,     within=             Reals, doc='total          electricity   oper     cost                           [EUR]'))
    setattr(optmodel, 'vTotalHydOCost',                    Var(model.psn,     within=             Reals, doc='total          hydrogen      oper     cost                           [EUR]'))
    setattr(optmodel, 'vTotalEleDCost',                    Var(model.psd,     within=             Reals, doc='total electricity    degradation      cost                           [EUR]'))
    setattr(optmodel, 'vTotalHydDCost',                    Var(model.psd,     within=             Reals, doc='total hydrogen       degradation      cost                           [EUR]'))

    # electricity and hydrogen revenue components
    setattr(optmodel, 'vTotalEleXRev',                     Var(model.ps ,     within=             Reals, doc='total tax             electricity  revenue                           [EUR]'))
    setattr(optmodel, 'vTotalEleMRev',                     Var(model.psn,     within=             Reals, doc='total variable electricity market  revenue                           [EUR]'))
    setattr(optmodel, 'vTotalHydMRev',                     Var(model.psn,     within=             Reals, doc='total variable hydrogen    market  revenue                           [EUR]'))

    # electricity network/grid cost such capacity and peak costs
    setattr(optmodel, 'vTotalElePeakCost',                 Var(model.ps ,     within=             Reals, doc='total electricity peak                cost                           [EUR]'))
    # setattr(optmodel, 'vTotalHydPeakCost',                 Var(model.ps ,     within=             Reals, doc='total hydrogen    peak                cost  [EUR]'))
    setattr(optmodel, 'vTotalEleNetUseVarCost',               Var(model.ps ,     within=             Reals, doc='total electricity network usage       cost                           [EUR]'))
    setattr(optmodel, 'vTotalEleNetUseFixCost',            Var(model.ps ,     within=             Reals, doc='total electricity capacity tariff     cost                           [EUR]'))

    # electricity market costs
    setattr(optmodel, 'vTotalEleMrkDACost',                Var(model.psn,     within=             Reals, doc='total electricity day-ahead market   cost                            [EUR]'))
    setattr(optmodel, 'vTotalEleMrkPPACost',               Var(model.psn,     within=             Reals, doc='total electricity PPA market         cost                            [EUR]'))

    # electricity market revenues
    setattr(optmodel, 'vTotalEleMrkDARev',                 Var(model.psn,     within=             Reals, doc='total electricity day-ahead market revenue                           [EUR]'))
    setattr(optmodel, 'vTotalEleMrkPPARev',                Var(model.psn,     within=             Reals, doc='total electricity PPA market       revenue                           [EUR]'))
    setattr(optmodel, 'vTotalEleMrkFrqRev',                Var(model.psn,     within=             Reals, doc='total electricity frequency market revenue                           [EUR]'))

    # ancillary services revenues
    setattr(optmodel, 'vTotalEleFCRDUpRev',                Var(model.psn,     within=             Reals, doc='total electricity FCR-D up    market revenue                         [EUR]'))
    setattr(optmodel, 'vTotalEleFCRDDwRev',                Var(model.psn,     within=             Reals, doc='total electricity FCR-D down  market revenue                         [EUR]'))
    setattr(optmodel, 'vTotalEleFCRNRev',                  Var(model.psn,     within=             Reals, doc='total electricity FCR-N       market revenue                         [EUR]'))

    # hydrogen market costs and revenues
    setattr(optmodel, 'vTotalHydMrkPPACost',               Var(model.psn,     within=             Reals, doc='total hydrogen    PPA market         cost                            [EUR]'))
    setattr(optmodel, 'vTotalHydMrkPPARev',                Var(model.psn,     within=             Reals, doc='total hydrogen    PPA market       revenue                           [EUR]'))

    # electricity tax costs and revenues
    setattr(optmodel, 'vTotalEleEnergyTaxCost',                  Var(model.ps ,     within=             Reals, doc='total electricity VAT                cost                            [EUR]'))
    setattr(optmodel, 'vTotalEleISRev',                    Var(model.ps ,     within=             Reals, doc='total electricity  incentives     revenue                            [EUR]'))

    # electricity and hydrogen generation costs
    setattr(optmodel, 'vTotalEleGCost',                    Var(model.psn,     within=             Reals, doc='total variable electricity prod      cost                            [EUR]'))
    setattr(optmodel, 'vTotalHydGCost',                    Var(model.psn,     within=             Reals, doc='total variable hydrogen    prod      cost                            [EUR]'))

    # electricity and hydrogen start-up / shut-down costs (per-event, ps-indexed so the
    # objective does not duration-weight them; see eTotalEleSUCost / eTotalHydSUCost)
    setattr(optmodel, 'vTotalEleSUCost',                   Var(model.ps ,     within=             Reals, doc='total electricity start-up/shut-down cost                            [EUR]'))
    setattr(optmodel, 'vTotalHydSUCost',                   Var(model.ps ,     within=             Reals, doc='total hydrogen    start-up/shut-down cost                            [EUR]'))

    # electricity and hydrogen emission costs
    setattr(optmodel, 'vTotalEleECost',                    Var(model.psn,     within=             Reals, doc='total electricity   emission         cost                            [EUR]'))

    # electricity and hydrogen consumption costs
    setattr(optmodel, 'vTotalEleCCost',                    Var(model.psn,     within=             Reals, doc='total variable electricity cons      cost                            [EUR]'))
    setattr(optmodel, 'vTotalHydCCost',                    Var(model.psn,     within=             Reals, doc='total variable hydrogen    cons      cost                            [EUR]'))

    # electricity and hydrogen reliability costs
    setattr(optmodel, 'vTotalEleRCost',                    Var(model.psn,     within=             Reals, doc='total system electricity reliability cost                            [EUR]'))
    setattr(optmodel, 'vTotalHydRCost',                    Var(model.psn,     within=             Reals, doc='total system hydrogen    reliability cost                            [EUR]'))

    setattr(optmodel, 'vEleDemPeakGlobal',                 Var(model.psmer, model.Peaks, within=PositiveReals, doc='electricity peak                                             [kW]'))
    setattr(optmodel, 'vHydDemPeakGlobal',                 Var(model.psmhr, model.Peaks, within=PositiveReals, doc='hydrogen    peak                                           [kgH2]'))
    setattr(optmodel, 'vEleDemPeakDay',                    Var(model.psder,   within=PositiveReals, doc='electricity daily peak                                                  [kW]'))
    setattr(optmodel, 'vHydDemPeakDay',                    Var(model.psdhr,   within=PositiveReals, doc='hydrogen    daily peak                                                [kgH2]'))

    # Define continuous variables
    setattr(optmodel, 'vEleBuy',                           Var(model.psner,   within=NonNegativeReals, doc='electricity retail  buy                                                 [kW]'))
    setattr(optmodel, 'vEleSell',                          Var(model.psner,   within=NonNegativeReals, doc='electricity retail  sell                                                [kW]'))
    setattr(optmodel, 'vEleDemand',                        Var(model.psned,   within=NonNegativeReals, doc='electricity demand                                                      [kW]'))
    setattr(optmodel, 'vENS',                              Var(model.psned,   within=NonNegativeReals, doc='electricity not served                                                  [kW]'))
    setattr(optmodel, 'vEleTotalOutput',                   Var(model.psneg,   within=NonNegativeReals, doc='total electricity output of the unit                                    [kW]'))
    setattr(optmodel, 'vEleTotalOutput2ndBlock',           Var(model.psnegnr, within=NonNegativeReals, doc='second block of the unit                                                [kW]'))
    setattr(optmodel, 'vEleTotalCharge',                   Var(model.psneh,   within=NonNegativeReals, doc='ESS total charge power                                                  [kW]'))
    setattr(optmodel, 'vEleTotalCharge2ndBlock',           Var(model.psneh,   within=NonNegativeReals, doc='ESS       charge power                                                  [kW]'))
    setattr(optmodel, 'vEleEnergyInflows',                 Var(model.psnegs,  within=NonNegativeReals, doc='unscheduled inflows  of all ESS units                                  [kW]'))
    setattr(optmodel, 'vEleEnergyOutflows',                Var(model.psnegs,  within=NonNegativeReals, doc='scheduled   outflows of all ESS units                                  [kW]'))
    setattr(optmodel, 'vEleInventory',                     Var(model.psnegs,  within=NonNegativeReals, doc='ESS inventory                                                          [kWh]'))
    setattr(optmodel, 'vEleInventoryMinDay',               Var(model.psdegs,  within=NonNegativeReals, doc=f'Minimum battery inventory per day                                     [kWh]'))
    setattr(optmodel, 'vEleInventoryMaxDay',               Var(model.psdegs,  within=NonNegativeReals, doc=f'Maximum battery inventory per day                                     [kWh]'))
    setattr(optmodel, 'vEleInventoryDoDDay',               Var(model.psdegs,  within=NonNegativeReals, doc=f'Battery Depth of Discharge per day                                    [kWh]'))
    setattr(optmodel, 'vEleInventoryDoDS1Day',             Var(model.psdegs,  within=NonNegativeReals, doc=f'Battery Depth of Discharge per day  S1                                [kWh]'))
    setattr(optmodel, 'vEleInventoryDoDS2Day',             Var(model.psdegs,  within=NonNegativeReals, doc=f'Battery Depth of Discharge per day  S2                                [kWh]'))
    setattr(optmodel, 'vEleInventoryDoDS3Day',             Var(model.psdegs,  within=NonNegativeReals, doc=f'Battery Depth of Discharge per day  S3                                [kWh]'))
    setattr(optmodel, 'vEleSpillage',                      Var(model.psnegs,  within=NonNegativeReals, doc='ESS spillage                                                           [kWh]'))
    setattr(optmodel, 'vEleExport',                        Var(model.psnnd,   within=NonNegativeReals, doc='electricity export   in node                                            [kW]'))
    setattr(optmodel, 'vEleImport',                        Var(model.psnnd,   within=NonNegativeReals, doc='electricity import   in node                                            [kW]'))

    setattr(optmodel, 'vHydBuy',                           Var(model.psnhr,   within=NonNegativeReals, doc='hydrogen buy        in node                                           [kgH2]'))
    setattr(optmodel, 'vHydSell',                          Var(model.psnhr,   within=NonNegativeReals, doc='hydrogen sell       in node                                           [kgH2]'))
    setattr(optmodel, 'vHydDemand',                        Var(model.psnhd,   within=NonNegativeReals, doc='hydrogen demand                                                       [kgH2]'))
    setattr(optmodel, 'vHNS',                              Var(model.psnhd,   within=NonNegativeReals, doc='hydrogen demand                                                       [kgH2]'))
    setattr(optmodel, 'vHydTotalOutput',                   Var(model.psnhg,   within=NonNegativeReals, doc='total hydrogen output of the unit                                     [kgH2/h]'))
    setattr(optmodel, 'vHydTotalOutput2ndBlock',           Var(model.psnhg,   within=NonNegativeReals, doc='second block of the unit                                              [kgH2/h]'))
    setattr(optmodel, 'vHydTotalCharge',                   Var(model.psnhe,   within=NonNegativeReals, doc='H2S total charge power                                                [kgH2/h]'))
    setattr(optmodel, 'vHydTotalCharge2ndBlock',           Var(model.psnhe,   within=NonNegativeReals, doc='H2S       charge power                                                [kgH2/h]'))
    setattr(optmodel, 'vHydEnergyInflows',                 Var(model.psnhgs,  within=NonNegativeReals, doc='unscheduled inflows  of all H2S units                                 [kgH2/h]'))
    setattr(optmodel, 'vHydEnergyOutflows',                Var(model.psnhgs,  within=NonNegativeReals, doc='scheduled   outflows of all H2S units                                 [kgH2/h]'))
    setattr(optmodel, 'vHydInventory',                     Var(model.psnhgs,  within=NonNegativeReals, doc='H2S inventory                                                         [kgH2]'))
    setattr(optmodel, 'vHydSpillage',                      Var(model.psnhgs,  within=NonNegativeReals, doc='H2S spillage                                                          [kgH2]'))
    setattr(optmodel, 'vHydExport',                        Var(model.psnnd,   within=NonNegativeReals, doc='hydrogen    export   in node                                          [kgH2]'))
    setattr(optmodel, 'vHydImport',                        Var(model.psnnd,   within=NonNegativeReals, doc='hydrogen    import   in node                                          [kgH2]'))

    setattr(optmodel, 'vEleNetFlow',                       Var(model.psnela,  within=           Reals, doc='electricity net flow                                                    [kW]'))
    setattr(optmodel, 'vHydNetFlow',                       Var(model.psnhpa,  within=           Reals, doc='hydrogen    net flow                                                  [kgH2]'))
    setattr(optmodel, 'vEleNetTheta',                      Var(model.psnnd,   within=           Reals, doc='electricity net theta                                                   [kW]'))

    setattr(optmodel, 'vEleFreqContReserveDisUpwardBid',   Var(model.psnege2h, within=NonNegativeReals, doc='electricity frequency containment reserve upward bid                   [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisDownwardBid', Var(model.psnege2h, within=NonNegativeReals, doc='electricity frequency containment reserve downward bid                 [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorBid',         Var(model.psnege2h, within=NonNegativeReals, doc='electricity frequency normal       reserve bid                         [kW]'))
    # setattr(optmodel, 'vEleFreqContReserveDisUpwardAct',   Var(model.psneg,   within=NonNegativeReals, doc='electricity frequency containment reserve upward fraction activation   [kW]'))
    # setattr(optmodel, 'vEleFreqContReserveDisDownwardAct', Var(model.psneg,   within=NonNegativeReals, doc='electricity frequency containment reserve downward fraction activation [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisUpGen',       Var(model.psnegt,  within=NonNegativeReals, doc='electricity frequency containment reserve upward generation            [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisDownGen',     Var(model.psnegt,  within=NonNegativeReals, doc='electricity frequency containment reserve downward generation          [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisUpCha',       Var(model.psneh,   within=NonNegativeReals, doc='electricity frequency containment reserve upward charge                [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisUpDis',       Var(model.psnegs,  within=NonNegativeReals, doc='electricity frequency containment reserve upward discharge             [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisDownCha',     Var(model.psneh,   within=NonNegativeReals, doc='electricity frequency containment reserve downward charge              [kW]'))
    setattr(optmodel, 'vEleFreqContReserveDisDownDis',     Var(model.psnegs,  within=NonNegativeReals, doc='electricity frequency containment reserve downward discharge           [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorUpGen',       Var(model.psnegt,  within=NonNegativeReals, doc='electricity frequency normal       reserve generation                  [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorDownGen',     Var(model.psnegt,  within=NonNegativeReals, doc='electricity frequency normal       reserve downward generation         [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorUpCha',       Var(model.psneh,   within=NonNegativeReals, doc='electricity frequency normal       reserve charge                      [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorUpDis',       Var(model.psnegs,  within=NonNegativeReals, doc='electricity frequency normal       reserve discharge                   [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorDownCha',     Var(model.psneh,   within=NonNegativeReals, doc='electricity frequency normal       reserve downward charge             [kW]'))
    setattr(optmodel, 'vEleFreqContReserveNorDownDis',     Var(model.psnegs,  within=NonNegativeReals, doc='electricity frequency normal       reserve downward discharge          [kW]'))

    if sum(model.Par['pEleDemFlexible'][idx] for idx in model.ed) > 0:
        setattr(optmodel, 'vEleDemFlex',                   Var(model.psned,  within=           Reals, doc='flexible electricity demand                 [kW]'))

    log_time('--- Defining the continuous variables', StartTime, ind_log=indlog)

    # Define binary variables
    if model.Par['pOptIndBinGenOperat'] == 0:
        setattr(optmodel, 'vEleGenCommitment',             Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vEleGenStartUp',                Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vEleGenShutDown',               Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary shut-down            '))
        # setattr(optmodel, 'vEleStorOperat',                Var(model.psnegs,             within=UnitInterval, initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vEleStorCharge',                Var(model.psnegs,             within=UnitInterval, initialize=0, doc='storage   binary charge               '))
        setattr(optmodel, 'vEleStorDischarge',             Var(model.psnegs,             within=UnitInterval, initialize=0, doc='storage   binary discharge            '))
        setattr(optmodel, 'vElePeakGlobalInd',             Var(model.psner, model.Peaks, within=UnitInterval, initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vElePeakMonthInd',              Var(model.psder, model.Peaks, within=UnitInterval, initialize=0, doc='monthly peak hour indicator           '))
        setattr(optmodel, 'vElePeakDayInd',                Var(model.psdner,             within=UnitInterval, initialize=0, doc='daily peak hour indicator             '))
        setattr(optmodel, 'vHydGenCommitment',             Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vHydGenStartUp',                Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vHydGenShutDown',               Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vHydGenStandBy',                Var(model.psnhg,              within=UnitInterval, initialize=0, doc='electrolyser standby state            '))
        setattr(optmodel, 'vHydStorOperat',                Var(model.psnhgs,             within=UnitInterval, initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vHydStorCharge',                Var(model.psnhgs,             within=UnitInterval, initialize=0, doc='storage   binary charge               '))
        setattr(optmodel, 'vHydStorDischarge',             Var(model.psnhgs,             within=UnitInterval, initialize=0, doc='storage   binary discharge            '))
        setattr(optmodel, 'vHydPeakGlobalInd',             Var(model.psnhr, model.Peaks, within=UnitInterval, initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vHydPeakMonthInd',              Var(model.psdhr, model.Peaks, within=UnitInterval, initialize=0, doc='monthly peak hour indicator           '))
        setattr(optmodel, 'vHydPeakDayInd',                Var(model.psdnhr,             within=UnitInterval, initialize=0, doc='daily peak hour indicator             '))
    else:
        setattr(optmodel, 'vEleGenCommitment',             Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vEleGenStartUp',                Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vEleGenShutDown',               Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary shut-down            '))
        # setattr(optmodel, 'vEleStorOperat',                Var(model.psnegs,             within=Binary,       initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vEleStorCharge',                Var(model.psnegs,             within=Binary,       initialize=0, doc='storage   binary charge               '))
        setattr(optmodel, 'vEleStorDischarge',             Var(model.psnegs,             within=Binary,       initialize=0, doc='storage   binary discharge            '))
        setattr(optmodel, 'vElePeakGlobalInd',             Var(model.psner, model.Peaks, within=Binary,       initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vElePeakMonthInd',              Var(model.psder, model.Peaks, within=Binary,       initialize=0, doc='monthly peak hour indicator           '))
        setattr(optmodel, 'vElePeakDayInd',                Var(model.psdner,             within=Binary,       initialize=0, doc='daily peak hour indicator             '))
        setattr(optmodel, 'vHydGenCommitment',             Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vHydGenStartUp',                Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vHydGenShutDown',               Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vHydGenStandBy',                Var(model.psnhg,              within=Binary,       initialize=0, doc='electrolyser standby state            '))
        setattr(optmodel, 'vHydStorOperat',                Var(model.psnhgs,             within=Binary,       initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vHydStorCharge',                Var(model.psnhgs,             within=Binary,       initialize=0, doc='storage   binary charge               '))
        setattr(optmodel, 'vHydStorDischarge',             Var(model.psnhgs,             within=Binary,       initialize=0, doc='storage   binary discharge            '))
        setattr(optmodel, 'vHydPeakGlobalInd',             Var(model.psnhr, model.Peaks, within=Binary,       initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vHydPeakMonthInd',              Var(model.psdhr, model.Peaks, within=Binary,       initialize=0, doc='monthly peak hour indicator           '))
        setattr(optmodel, 'vHydPeakDayInd',                Var(model.psdnhr,             within=Binary,       initialize=0, doc='daily peak hour indicator             '))

    # Electrolyser PWL part-load efficiency (audit Phase B / B1): breakpoint weights (lambda)
    # and the active-segment indicator for the SOS2 convex combination. Built only for the
    # flagged electrolysers (model.hpwl), so default-off cases declare nothing (byte-unchanged).
    # The segment indicator follows the commitment's domain (binary, or relaxed under the LP
    # operation mode); the weights are always continuous in [0,1] (bounded by the convexity row).
    if model.hpwl:
        _pwl_seg_domain = UnitInterval if model.Par['pOptIndBinGenOperat'] == 0 else Binary
        _pwl_bp_idx  = [(p, sc, n, g, k) for (p, sc, n) in model.psn for g in model.hpwl for k in model.pwlbp]
        _pwl_seg_idx = [(p, sc, n, g, s) for (p, sc, n) in model.psn for g in model.hpwl for s in model.pwlseg]
        setattr(optmodel, 'vHydGenPWLWeight',  Var(_pwl_bp_idx,  within=NonNegativeReals, initialize=0, doc='electrolyser PWL breakpoint weight (lambda)'))
        setattr(optmodel, 'vHydGenPWLSegment', Var(_pwl_seg_idx, within=_pwl_seg_domain,  initialize=0, doc='electrolyser PWL active-segment indicator'))

    if model.Par['pOptIndBinNetOperat'] == 0:
        setattr(optmodel, 'vEleNetCommit',                 Var(model.psnela,  within=UnitInterval, initialize=0, doc='network binary operation              '))
        setattr(optmodel, 'vHydNetCommit',                 Var(model.psnela,  within=UnitInterval, initialize=0, doc='network binary operation              '))
    else:
        setattr(optmodel, 'vEleNetCommit',                 Var(model.psnela,  within=Binary,       initialize=0, doc='network binary operation              '))
        setattr(optmodel, 'vHydNetCommit',                 Var(model.psnela,  within=Binary,       initialize=0, doc='network binary operation              '))

    log_time('--- Defining the binary variables', StartTime, ind_log=indlog)

    # Precompute the bounds
    # psn
    std_upper_bound = 1e4
    std_lower_bound = -1e4
    zero_upper_bound = 0.0
    zero_lower_bound = 0.0

    # List of variables to set bounds
    cost_vars = [optmodel.vTotalEleNCost, optmodel.vTotalEleXCost, optmodel.vTotalEleMCost, optmodel.vTotalHydMCost, optmodel.vTotalEleOCost, optmodel.vTotalHydOCost]

    zero_cost_vars = [optmodel.vTotalHydDCost,
                      optmodel.vTotalEleMrkPPACost,
                      optmodel.vTotalEleMrkPPARev]

    rev_vars = [optmodel.vTotalEleXRev, optmodel.vTotalEleMRev, optmodel.vTotalHydMRev]

    sub_cost_vars = [optmodel.vTotalEleDCost,
                     optmodel.vTotalElePeakCost, optmodel.vTotalEleNetUseVarCost, optmodel.vTotalEleNetUseFixCost,
                     optmodel.vTotalEleMrkDACost,
                     optmodel.vTotalHydMrkPPACost,
                     optmodel.vTotalEleEnergyTaxCost,
                     optmodel.vTotalEleGCost, optmodel.vTotalHydGCost,
                     optmodel.vTotalEleECost,
                     optmodel.vTotalEleCCost, optmodel.vTotalHydCCost,
                     optmodel.vTotalEleRCost, optmodel.vTotalHydRCost]

    sub_rev_vars = [optmodel.vTotalEleMrkDARev,
                    optmodel.vTotalHydMrkPPARev,
                    optmodel.vTotalEleISRev, optmodel.vTotalEleMrkFrqRev, optmodel.vTotalEleFCRDUpRev, optmodel.vTotalEleFCRDDwRev]

    # ed_vars = [optmodel.vENS]

    # Set bounds for each variable
    # Objective function
    for var in cost_vars + rev_vars + sub_cost_vars + sub_rev_vars:
        var.setlb(std_lower_bound)
        var.setub(std_upper_bound)

    for var in zero_cost_vars:
        var.setlb(zero_lower_bound)
        var.setub(zero_upper_bound)

    # Electricity
    for idx in model.psner:
        optmodel.vEleBuy [idx].setlb(model.Par['pEleRetMinimumEnergyBuy' ][idx[-1]])
        optmodel.vEleBuy [idx].setub(model.Par['pEleRetMaximumEnergyBuy' ][idx[-1]])
        optmodel.vEleSell[idx].setlb(model.Par['pEleRetMinimumEnergySell'][idx[-1]])
        optmodel.vEleSell[idx].setub(model.Par['pEleRetMaximumEnergySell'][idx[-1]])

    for idx in model.psned:
        if model.Par['pEleDemFlexible'][idx[-1]] == 0.0:
            optmodel.vEleDemand[idx].setlb(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
            optmodel.vEleDemand[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
        else:
            optmodel.vEleDemFlex[idx].setlb(-model.Par['pVarMaxDemand'][idx[-1]][idx[:3]]*model.Par['pEleDemFlexPercent'][idx[-1]])
            optmodel.vEleDemFlex[idx].setub(+model.Par['pVarMaxDemand'][idx[-1]][idx[:3]]*model.Par['pEleDemFlexPercent'][idx[-1]])
        #     optmodel.vEleDemand[idx].setlb(model.Par['pVarMinDemand'][idx[-1]][idx[:3]])
        #     optmodel.vEleDemand[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
        optmodel.vENS[idx].setlb(0.0)
        optmodel.vENS[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])

    for idx in model.psneg:
        optmodel.vEleTotalOutput[idx].setlb(0.0)
        optmodel.vEleTotalOutput[idx].setub(model.Par['pEleMaxPower'][idx[-1]][idx[:3]])
        if idx[-1] in model.egnr:
            optmodel.vEleTotalOutput2ndBlock[idx].setlb(0.0)
            optmodel.vEleTotalOutput2ndBlock[idx].setub(model.Par['pEleMaxPower2ndBlock'][idx[-1]][idx[:3]])

    for idx in model.psneh:
        optmodel.vEleTotalCharge[idx].setlb(0.0)
        optmodel.vEleTotalCharge2ndBlock[idx].setlb(0.0)
        if idx[-1] in model.eg:
            optmodel.vEleTotalCharge[idx].setub(model.Par['pEleMaxCharge'][idx[-1]][idx[:3]])
            # optmodel.vEleTotalCharge2ndBlock[idx].setub(model.Par['pEleMaxCharge'][idx[-1]][idx[:3]])
        elif idx[-1] in model.hg:
            optmodel.vEleTotalCharge[idx].setub(model.Par['pHydMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vEleTotalCharge2ndBlock[idx].setub(model.Par['pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]])

    # for idx in model.psnegs:
    #     if idx[-1] in model.egs:
    #         if model.Par['pEleMinCharge'][idx[-1]][idx[:3]] > 0.0:
    #             optmodel.vEleTotalCharge2ndBlock[idx].setlb(model.Par['pEleMinCharge'][idx[-1]][idx[:3]])
    #         else:
    #             optmodel.vEleTotalCharge2ndBlock[idx].setlb(0.0)
    #         if model.Par['pEleMinPower'][idx[-1]][idx[:3]] > 0.0:
    #             optmodel.vEleTotalOutput2ndBlock[idx].setlb(model.Par['pEleMinPower'][idx[-1]][idx[:3]])
    #         else:
    #             optmodel.vEleTotalOutput2ndBlock[idx].setlb(0.0)

        # Inflows, outflows and inventory exist only for storage units (egs), not
        # for electrolysers (e2h), which also appear in eh as electricity consumers.
        if idx[-1] in model.egs:
            optmodel.vEleEnergyInflows[idx].setlb(model.Par['pEleMinInflows'][idx[-1]][idx[:3]])
            optmodel.vEleEnergyInflows[idx].setub(model.Par['pEleMaxInflows'][idx[-1]][idx[:3]])
            optmodel.vEleEnergyOutflows[idx].setlb(model.Par['pEleMinOutflows'][idx[-1]][idx[:3]])
            optmodel.vEleEnergyOutflows[idx].setub(model.Par['pEleMaxOutflows'][idx[-1]][idx[:3]])
            optmodel.vEleInventory[idx].setlb(model.Par['pEleMinStorage'][idx[-1]][idx[:3]] * model.factor1)
            optmodel.vEleInventory[idx].setub(model.Par['pEleMaxStorage'][idx[-1]][idx[:3]] * model.factor1)

    for idx in model.psnela:
        if model.Par['pOptIndBinSingleNode'] == 0:
            optmodel.vEleNetFlow[idx].setlb(-model.Par['pEleNetTTCBck' ][idx[-3:]])
            optmodel.vEleNetFlow[idx].setub( model.Par['pEleNetTTC'    ][idx[-3:]])
        else:
            optmodel.vEleNetFlow[idx].setlb(std_lower_bound)
            optmodel.vEleNetFlow[idx].setub(std_upper_bound)

    # Hydrogen
    for idx in model.psnhr:
        optmodel.vHydBuy [idx].setlb(model.Par['pHydRetMinimumEnergyBuy' ][idx[-1]])
        optmodel.vHydBuy [idx].setub(model.Par['pHydRetMaximumEnergyBuy' ][idx[-1]])
        optmodel.vHydSell[idx].setlb(model.Par['pHydRetMinimumEnergySell'][idx[-1]])
        optmodel.vHydSell[idx].setub(model.Par['pHydRetMaximumEnergySell'][idx[-1]])

    for idx in model.psnhd:
        if model.Par['pHydDemFlexible'][idx[-1]] == 0.0:
            optmodel.vHydDemand[idx].setlb(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
            optmodel.vHydDemand[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
        else:
            optmodel.vHydDemand[idx].setlb(model.Par['pVarMinDemand'][idx[-1]][idx[:3]])
            optmodel.vHydDemand[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])
        optmodel.vHNS[idx].setlb(0.0)
        optmodel.vHNS[idx].setub(model.Par['pVarMaxDemand'][idx[-1]][idx[:3]])

    for idx in model.psnhg:
        optmodel.vHydTotalOutput[idx].setlb(0.0)
        optmodel.vHydTotalOutput[idx].setub(model.Par['pHydMaxPower'][idx[-1]][idx[:3]])
        optmodel.vHydTotalOutput2ndBlock[idx].setlb(0.0)
        optmodel.vHydTotalOutput2ndBlock[idx].setub(model.Par['pHydMaxPower2ndBlock'][idx[-1]][idx[:3]])

    for idx in model.psnhe:
        optmodel.vHydTotalCharge[idx].setlb(0.0)
        optmodel.vHydTotalCharge2ndBlock[idx].setlb(0.0)
        if idx[-1] in model.hg:
            optmodel.vHydTotalCharge[idx].setub(model.Par['pHydMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vHydTotalCharge2ndBlock[idx].setub(model.Par['pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]])
        elif idx[-1] in model.eg:
            optmodel.vHydTotalCharge[idx].setub(model.Par['pEleMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vHydTotalCharge2ndBlock[idx].setub(model.Par['pEleMaxCharge2ndBlock'][idx[-1]][idx[:3]])

    for idx in model.psnhgs:
        optmodel.vHydEnergyInflows[idx].setlb(model.Par['pHydMinInflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyInflows[idx].setub(model.Par['pHydMaxInflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyOutflows[idx].setlb(model.Par['pHydMinOutflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyOutflows[idx].setub(model.Par['pHydMaxOutflows'][idx[-1]][idx[:3]])
        # storage energy carries the factor1 unit conversion, like the electricity
        # inventory bounds above and the (already factor1-scaled) initial inventory, so
        # the bound, the initial state and the accumulated inventory share one unit.
        optmodel.vHydInventory[idx].setlb(model.Par['pHydMinStorage'][idx[-1]][idx[:3]] * model.factor1)
        optmodel.vHydInventory[idx].setub(model.Par['pHydMaxStorage'][idx[-1]][idx[:3]] * model.factor1)

    for idx in model.psnhpa:
        if model.Par['pOptIndBinSingleNode'] == 0:
            optmodel.vHydNetFlow[idx].setlb(-model.Par['pHydNetTTCBck' ][idx[-3:]])
            optmodel.vHydNetFlow[idx].setub( model.Par['pHydNetTTC'    ][idx[-3:]])
        else:
            optmodel.vHydNetFlow[idx].setlb(std_lower_bound)
            optmodel.vHydNetFlow[idx].setub(std_upper_bound)

    log_time('--- Setting the bounds for the variables', StartTime, ind_log=indlog)

    EnergyPrefix = {}
    AssetCand    = {}
    NetCand      = {}
    RetailPrefix = {}
    for e in model.eg:
        EnergyPrefix[e] = 'Ele'
        AssetCand[e]    = model.egc
    for h in model.hg:
        EnergyPrefix[h] = 'Hyd'
        AssetCand[h]    = model.hgc
    model.EnergyPrefix = EnergyPrefix
    model.AssetCand    = AssetCand

    for idx in model.ela:
        NetCand[idx] = 'Ele'
    for idx in model.hpa:
        NetCand[idx] = 'Hyd'
    model.NetCand = NetCand

    for idx in model.er:
        RetailPrefix[idx] = 'Ele'
    for idx in model.hr:
        RetailPrefix[idx] = 'Hyd'
    model.RetailPrefix = RetailPrefix

    #%% fixing variables
    nFixedVariables = 0.0

    if model.Par['pParNumberPowerPeaks'] == 0:
    #     for idx in model.psmer:
    #         for peak in model.Peaks:
    #             optmodel.__getattribute__('vEleDemPeakGlobal')[idx, peak].fix(0.0)
    #             nFixedVariables += 1.0
    #         nFixedVariables += 1.0
    #     for idx in model.psmhr:
    #         for peak in model.Peaks:
    #             optmodel.__getattribute__('vHydDemPeakGlobal')[idx, peak].fix(0.0)
    #             nFixedVariables += 1.0
    #         nFixedVariables += 1.0
        # for idx in model.psder:
        #     optmodel.vEleDemPeakDay[idx].fix(0.0)
        #     nFixedVariables += 1.0
        # for idx in model.psdhr:
        #     optmodel.vHydDemPeakDay[idx].fix(0.0)
        #     nFixedVariables += 1.0
        # fixing vElePeakGlobalInd, model.psner and model.Peaks
        for idx in model.psner:
            for peak in model.Peaks:
                optmodel.__getattribute__('vElePeakGlobalInd')[idx, peak].fix(0.0)
                nFixedVariables += 1.0
        # fixing vHydPeakGlobalInd, model.psnhr and model.Peaks
        for idx in model.psnhr:
            for peak in model.Peaks:
                optmodel.__getattribute__('vHydPeakGlobalInd')[idx, peak].fix(0.0)
                nFixedVariables += 1.0
        # fixing vElePeakMonthInd, model.psder and model.Peaks
        for idx in model.psder:
            for peak in model.Peaks:
                optmodel.__getattribute__('vElePeakMonthInd')[idx, peak].fix(0.0)
                nFixedVariables += 1.0
        # fixing vHydPeakMonthInd, model.psdhr and model.Peaks
        for idx in model.psdhr:
            for peak in model.Peaks:
                optmodel.__getattribute__('vHydPeakMonthInd')[idx, peak].fix(0.0)
                nFixedVariables += 1.0
        # fixing vElePeakDayInd, model.psdner
        for idx in model.psdner:
            optmodel.__getattribute__('vElePeakDayInd')[idx].fix(0.0)
            nFixedVariables += 1.0
        # fixing vHydPeakDayInd, model.psdnhr
        for idx in model.psdnhr:
            optmodel.__getattribute__('vHydPeakDayInd')[idx].fix(0.0)
            nFixedVariables += 1.0

    for idx in model.psnegs:
        egs = idx[-1]
        # fixing spillage based on the model.Par['pVarFixedAvailability'][egs][p,sc,n]
        # if model.Par['pVarFixedAvailability'][egs][idx[:3]] == 1:  # no storage operation
        optmodel.__getattribute__('vEleSpillage')[idx].fix(0.0)
        if model.Par['pEleGenMaximumPower'][egs] <= 1e-5:
            optmodel.__getattribute__('vEleStorDischarge')[idx].fix(0.0)
            nFixedVariables += 1.0
        nFixedVariables += 1.0

    # # fixing storage mode based on the model.Par['pVarFixedAvailability'][egs][p,sc,n]
    # for idx in model.psnegs:
    #     egs = idx[-1]
    #     if model.Par['pVarFixedAvailability'][egs][idx[:3]] == 0:  # charge only
    #         optmodel.__getattribute__('vEleStorCharge')[idx].fix(0.0)
    #         optmodel.__getattribute__('vEleStorDischarge')[idx].fix(0.0)
    #         optmodel.__getattribute__('vElePeakDayInd')[idx[:2]+(model.n2d_dict[idx[2]],idx[2],model.Par['pEleGenRetailer'][egs],)].fix(0.0)
    #         optmodel.__getattribute__('vEleBuy')[idx[:2]+(idx[2],model.Par['pEleGenRetailer'][egs],)].fix(0.0)
    #         optmodel.__getattribute__('vEleSell')[idx[:2] + (idx[2], model.Par['pEleGenRetailer'][egs],)].fix(0.0)
    #         nFixedVariables += 5.0

    # fixing storage variables related to depth of discharge scenarios
    for idx in model.psd:
        # The TOTAL degradation cost is zero only when NO storage unit degrades. Fixing it
        # whenever ANY single unit lacks DoD segments (the old per-unit test) pinned the
        # total to zero in a mixed fleet while eTotalEleDCost equates it to the nonzero sum
        # -- erasing the degrading unit's cost or making the case infeasible (C22).
        if all((model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs]) == 0 for egs in model.egs):
            optmodel.__getattribute__(f'vTotalEleDCost')[idx].fix(0.0)
            nFixedVariables += 1.0
        for egs in model.egs:
            if (idx, egs) in model.psdegs and (model.Par['pEleGenDoDS1'][egs] + model.Par['pEleGenDoDS2'][egs] + model.Par['pEleGenDoDS3'][egs]) == 0:
                optmodel.__getattribute__(f'vEleInventoryMinDay')[idx+(egs,)].fix(0.0)
                nFixedVariables += 1.0
                optmodel.__getattribute__(f'vEleInventoryMaxDay')[idx+(egs,)].fix(0.0)
                nFixedVariables += 1.0
                optmodel.__getattribute__(f'vEleInventoryDoDDay')[idx+(egs,)].fix(0.0)
                nFixedVariables += 1.0
                if model.Par['pEleGenDoDS1'][egs] == 0:
                    optmodel.__getattribute__(f'vEleInventoryDoDS1Day')[idx+(egs,)].fix(0.0)
                    nFixedVariables += 1.0
                if model.Par['pEleGenDoDS2'][egs] == 0:
                    optmodel.__getattribute__(f'vEleInventoryDoDS2Day')[idx+(egs,)].fix(0.0)
                    nFixedVariables += 1.0
                if model.Par['pEleGenDoDS3'][egs] == 0:
                    optmodel.__getattribute__(f'vEleInventoryDoDS3Day')[idx+(egs,)].fix(0.0)
                    nFixedVariables += 1.0

    # fixing the DemPeakDay and PeakDayInd variables
    # for idx in model.psmer:
    #     for peak in model.Peaks:
    #         if model.Par['pEleRetTariffType'][idx[-1]] != 'Hourly':
    #             optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}DemPeakGlobal')[idx, peak].fix(0.0)
    #             nFixedVariables += 1
    # for idx in model.psmhr:
    #     for peak in model.Peaks:
    #         if model.Par['pHydRetTariffType'][idx[-1]] != 'Hourly':
    #             optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}DemPeakGlobal')[idx, peak].fix(0.0)
    #             nFixedVariables += 1
    # for idx in model.psder:
    #     if model.Par['pEleRetTariffType'][idx[-1]] != 'Daily':
    #         optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}DemPeakDay')[idx].fix(0.0)
    #         # # delete the variable from the model to speed up the optimization
    #         # optmodel.del_component(optmodel.vEleDemPeakDay[idx])
    #         # nFixedVariables += 1
    # for idx in model.psdhr:
    #     if model.Par['pHydRetTariffType'][idx[-1]] != 'Daily':
    #         optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}DemPeakDay')[idx].fix(0.0)
    #         # optmodel.del_component(optmodel.vHydDemPeakDay[idx])
    #         # nFixedVariables += 1

    for idx in model.psner:
        for peak in model.Peaks:
            if model.Par['pEleRetTariffType'][idx[-1]] != 'Hourly':
                optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakGlobalInd')[idx+(peak,)].fix(0.0)
                nFixedVariables += 1
    for idx in model.psnhr:
        for peak in model.Peaks:
            if model.Par['pHydRetTariffType'][idx[-1]] != 'Hourly':
                optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakGlobalInd')[idx+(peak,)].fix(0.0)
                nFixedVariables += 1

    for idx in model.psder:
        for peak in model.Peaks:
            if model.Par['pEleRetTariffType'][idx[-1]] != 'Daily':
                optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakMonthInd')[idx+(peak,)].fix(0.0)
                nFixedVariables += 1
    for idx in model.psdhr:
        for peak in model.Peaks:
            if model.Par['pHydRetTariffType'][idx[-1]] != 'Daily':
                optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakMonthInd')[idx+(peak,)].fix(0.0)
                nFixedVariables += 1
    for idx in model.psdner:
        if model.Par['pEleRetTariffType'][idx[-1]] != 'Daily':
            optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakDayInd')[idx].fix(0.0)
            nFixedVariables += 1
    for idx in model.psdnhr:
        if model.Par['pHydRetTariffType'][idx[-1]] != 'Daily':
            optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}PeakDayInd')[idx].fix(0.0)
            nFixedVariables += 1

    # assign the minimum power for the RES units
    for idx in model.psnegr:
        optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput')[idx].setlb(model.Par['pEleMinPower'][idx[-1]][idx[:(len(idx)-1)]])

    # relax binary condition in unit generation, startup and shutdown decisions
    for idx in model.psnegt:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenBinaryCommitment'][idx[-1]] == 0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].domain = UnitInterval
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenStartUp'   )[idx].domain = UnitInterval
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenShutDown'  )[idx].domain = UnitInterval

    for idx in model.psnhgt:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenBinaryCommitment'][idx[-1]] == 0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].domain = UnitInterval
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenStartUp'   )[idx].domain = UnitInterval
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenShutDown'  )[idx].domain = UnitInterval


    # if min and max power coincide there are second block
    for idx in model.psnegnr:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxPower2ndBlock'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput2ndBlock')[idx].fix(0.0)
            nFixedVariables += 1

    # if min and max outflows coincide there are neither second block, nor operating reserve
    for idx in  model.psnhgt:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxPower2ndBlock'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput2ndBlock')[idx].fix(0.0)
            nFixedVariables += 1

    # ESS with no charge capacity or not storage capacity can't charge
    for idx in model.psnehs:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxCharge'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalCharge')[idx].fix(0.0)
            nFixedVariables += 1
        # ESS with no charge capacity and no inflows can't produce
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxCharge'][idx[-1]][idx[:(len(idx)-1)]] == 0.0 and sum(model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxInflows'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] for n2 in model.n2) == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput2ndBlock')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Spillage')[idx].fix(0.0)
            nFixedVariables += 3
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxCharge2ndBlock'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalCharge2ndBlock')[idx].fix(0.0)
            nFixedVariables += 1
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxStorage'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(0.0)
            nFixedVariables += 1
        # fixing the ESS inventory at the last load level of the stage for every period and scenario if between storage limits in the DA market
        if len(model.n):
            # if model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] >= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MinStorage'][idx[-1]][idx[:(len(idx)-2)]+(model.n.last(),)] and model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] <= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxStorage'][idx[-1]][idx[:(len(idx)-2)]+(model.n.last(),)]:
            #     optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx[:(len(idx)-2)]+(model.n.last(),)+(idx[-1],)].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
            #     nFixedVariables += 1
        # fixing the ESS inventory at the end of the following pCycleTimeStep (daily, weekly, monthly), i.e., for daily ESS is fixed at the end of the week, for weekly/monthly ESS is fixed at the end of the year
            if model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] >= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MinStorage'][idx[-1]][idx[:(len(idx)-1)]]                   and model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] <= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                # if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Hourly' and model.n.ord(idx[-2]) % int(24/model.Par['pParTimeStep']) == 0:
                #     optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                #     nFixedVariables += 1
                # if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Hourly' and model.n.ord(idx[-2]) % int(168/model.Par['pParTimeStep']) == 0:
                #     optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                #     nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Hourly' and model.n.ord(idx[-2]) % int(744/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Weekly' and model.n.ord(idx[-2]) % int(8736/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Monthly' and model.n.ord(idx[-2]) % int(8736/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1

    # if pEleGenNoDayAhead == 1, fix the day-ahead market variables to zero
    for idx in model.psnegnr:
        if model.Par['pEleGenNoDayAhead'][idx[-1]] == 1:
            optmodel.vEleTotalCharge2ndBlock[idx].fix(0.0)
            optmodel.vEleTotalOutput2ndBlock[idx].fix(0.0)

    # if pEleGenNoFCRD == 1, fix the frequency containment reserve variables to zero
    for idx in model.psnegnr:
        if model.Par['pEleGenNoFCRD'][idx[-1]] == 1:
            optmodel.vEleFreqContReserveDisUpwardBid[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisDownwardBid[idx].fix(0.0)
            if idx[-1] in model.egt:
                optmodel.vEleFreqContReserveDisUpGen[idx].fix(0.0)
                optmodel.vEleFreqContReserveDisDownGen[idx].fix(0.0)
                nFixedVariables += 2
            if idx[-1] in model.egs:
                optmodel.vEleFreqContReserveDisUpCha[idx].fix(0.0)
                optmodel.vEleFreqContReserveDisUpDis[idx].fix(0.0)
                optmodel.vEleFreqContReserveDisDownCha[idx].fix(0.0)
                optmodel.vEleFreqContReserveDisDownDis[idx].fix(0.0)
                nFixedVariables += 4
        elif model.Par['pEleGenNoFCRD'][idx[-1]] == 0 and model.Par['pEleGenNoDayAhead'][idx[-1]] == 0 and model.Par['pEleMaxPower'][idx[-1]][idx[:(len(idx) - 1)]] <= 1e-5 and model.Par['pEleGenV2G'][idx[-1]] == 1:
            optmodel.vEleTotalOutput2ndBlock[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisDownDis[idx].fix(0.0)
            nFixedVariables += 2
        elif model.Par['pEleGenNoFCRD'][idx[-1]] == 0 and model.Par['pEleGenNoDayAhead'][idx[-1]] == 0 and model.Par['pEleMaxPower'][idx[-1]][idx[:(len(idx) - 1)]] <= 1e-5 and model.Par['pEleGenV2G'][idx[-1]] == 0:
            optmodel.vEleTotalOutput2ndBlock[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisUpDis[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisDownDis[idx].fix(0.0)
            nFixedVariables += 2
        if model.Par['pEleGenNoFCRN'][idx[-1]] == 1:
            optmodel.vEleFreqContReserveNorBid[idx].fix(0.0)
            if idx[-1] in model.egt:
                optmodel.vEleFreqContReserveNorUpGen[idx].fix(0.0)
                optmodel.vEleFreqContReserveNorDownGen[idx].fix(0.0)
                nFixedVariables += 2
            if idx[-1] in model.egs:
                optmodel.vEleFreqContReserveNorUpCha[idx].fix(0.0)
                optmodel.vEleFreqContReserveNorUpDis[idx].fix(0.0)
                optmodel.vEleFreqContReserveNorDownCha[idx].fix(0.0)
                optmodel.vEleFreqContReserveNorDownDis[idx].fix(0.0)
                nFixedVariables += 4
        elif model.Par['pEleGenNoFCRN'][idx[-1]] == 0 and model.Par['pEleGenNoDayAhead'][idx[-1]] == 0 and model.Par['pEleMaxPower'][idx[-1]][idx[:(len(idx) - 1)]] <= 1e-5 and model.Par['pEleGenV2G'][idx[-1]] == 1:
            optmodel.vEleTotalOutput2ndBlock[idx].fix(0.0)
            optmodel.vEleFreqContReserveNorDownDis[idx].fix(0.0)
            nFixedVariables += 2
        elif model.Par['pEleGenNoFCRN'][idx[-1]] == 0 and model.Par['pEleGenNoDayAhead'][idx[-1]] == 0 and model.Par['pEleMaxPower'][idx[-1]][idx[:(len(idx) - 1)]] <= 1e-5 and model.Par['pEleGenV2G'][idx[-1]] == 0:
            optmodel.vEleTotalOutput2ndBlock[idx].fix(0.0)
            optmodel.vEleFreqContReserveNorUpDis[idx].fix(0.0)
            optmodel.vEleFreqContReserveNorDownDis[idx].fix(0.0)
            nFixedVariables += 2

    # if the electrolyser does not provide FCR (pHydGenNoFCRD / pHydGenNoFCRN == 1),
    # fix its frequency reserve bid and charge-side provision variables to zero. The
    # default flags are 1, so cases without an FCR-providing electrolyser are unchanged.
    for idx in model.psne2h:
        if model.Par['pHydGenNoFCRD'][idx[-1]] == 1:
            optmodel.vEleFreqContReserveDisUpwardBid[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisDownwardBid[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisUpCha[idx].fix(0.0)
            optmodel.vEleFreqContReserveDisDownCha[idx].fix(0.0)
            nFixedVariables += 4
        if model.Par['pHydGenNoFCRN'][idx[-1]] == 1:
            optmodel.vEleFreqContReserveNorBid[idx].fix(0.0)
            optmodel.vEleFreqContReserveNorUpCha[idx].fix(0.0)
            optmodel.vEleFreqContReserveNorDownCha[idx].fix(0.0)
            nFixedVariables += 3

    # RES generators carry FCR bid variables (declared over eg) but appear in no FCR
    # cap, relation, or revenue term, so they are never otherwise constrained. Fix them
    # to zero so they cannot carry arbitrary values into the result tables (audit C32).
    for idx in model.psnegr:
        optmodel.vEleFreqContReserveDisUpwardBid[idx].fix(0.0)
        optmodel.vEleFreqContReserveDisDownwardBid[idx].fix(0.0)
        optmodel.vEleFreqContReserveNorBid[idx].fix(0.0)
        nFixedVariables += 3

    # An electrolyser's hydrogen output is set by eAllEnergy2Hyd from its electricity
    # input, so its H2 second-block output variable is unused; fix it to zero. The
    # electrolyser's state logic uses commitment (on), standby and start-up (cold start);
    # it carries no shut-down transition, so its shut-down variable is fixed to zero too
    # (otherwise it would be a free variable appearing only in the shut-down cost).
    # Audit C36: because the shut-down variable is fixed to zero, a nonzero ShutDownCost on
    # an electrolyser is silently ignored. Warn so the data author is not misled.
    for e2h in model.e2h:
        if model.Par['pHydGenShutDownCost'][e2h] > 0:
            print(f"WARNING (C36): electrolyser '{e2h}' has ShutDownCost > 0, but its shut-down "
                  f"variable is fixed to zero (no shut-down transition is modelled), so the "
                  f"shut-down cost is ignored.")
    for idx in model.psne2h:
        optmodel.vHydTotalOutput2ndBlock[idx].fix(0.0)
        optmodel.vHydGenShutDown[idx].fix(0.0)
        nFixedVariables += 2

    # Audit C35: the three-state (on / standby / off) electrolyser logic is only meaningful
    # with binary unit commitment. Under the LP relaxation (pOptIndBinGenOperat == 0) the
    # commitment and standby variables are continuous, so the standby state is gameable and
    # the reported standby schedule should not be trusted. Warn when both hold.
    if model.Par['pOptIndBinGenOperat'] == 0 and \
            any(e2h in model.e2h and model.Par['pHydGenStandByStatus'][e2h] == 1 for e2h in model.e2h):
        print("WARNING (C35): a standby-capable electrolyser is run with relaxed (continuous) "
              "unit commitment (pOptIndBinGenOperat == 0); the three-state standby logic is "
              "gameable in the LP and standby results need binary UC to be meaningful.")

    # Standby is an electrolyser (e2h) state, available only where StandByStatus is set.
    # Everywhere else the standby variable is fixed to zero, so the three-state model
    # collapses to plain on/off and existing cases are unchanged.
    for idx in model.psnhg:
        hz = idx[-1]
        if not (hz in model.e2h and model.Par['pHydGenStandByStatus'][hz] == 1):
            optmodel.vHydGenStandBy[idx].fix(0.0)
            nFixedVariables += 1

    # A fixed-consumption electrolyser (MinCharge == MaxCharge, so MaxCharge2ndBlock == 0)
    # has no charge decomposition: its total charge is set directly by the fixed-consumption
    # branch of eEleTotalCharge, leaving the 2nd-block charge unused. Pin it to zero so it
    # does not float (C12).
    for idx in model.psne2h:
        if model.Par['pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]] == 0:
            optmodel.vEleTotalCharge2ndBlock[idx].fix(0.0)
            nFixedVariables += 1

    # if there are no energy outflows no variable is needed
    iset = model.psn
    for ehs in model.ehs:
        if sum(model.Par[f'p{model.EnergyPrefix[ehs]}MaxOutflows'][ehs][idx] for idx in iset) == 0.0:
            for idx in iset:
                optmodel.__getattribute__(f'v{model.EnergyPrefix[ehs]}EnergyOutflows')[idx+(ehs,)].fix(0.0)
                nFixedVariables += 1

    # fixing the voltage angle of the reference node for each scenario, period, and load level
    if model.Par['pOptIndBinSingleNode'] == 0:
        for p,sc,n in model.psn:
            optmodel.__getattribute__('vEleNetTheta')[p,sc,n,model.endrf.first()].fix(0.0)
            nFixedVariables += 1

    # fixing the electricity imports/exports in nodes that are not reference nodes.
    # Electricity import at the reference node is priced (grid transfer fee + energy
    # tax in the objective) and closed by the retail balance, so it stays free there.
    if model.Par['pOptIndBinSingleNode'] == 0:
        for idx in model.psnnd:
            if idx[-1] not in model.endrf:
                optmodel.__getattribute__('vEleImport')[idx].fix(0.0)
                optmodel.__getattribute__('vEleExport')[idx].fix(0.0)
                nFixedVariables += 2

    # Hydrogen import/export carries no cost and is linked to a buy/sell only by the
    # retail composition constraints (eHydBuyComposition / eHydSellComposition, gated
    # by pHydRetMaxBuy/Sell > 0). Anywhere a node has no active, priced hydrogen
    # retailer -- which is every node in single-node mode, where the network fixing
    # above does not run -- vHydImport/Export would be a free, unpriced H2 source/sink,
    # so fix them to zero. (Unlike electricity, hydrogen has no retail node balance.)
    hyd_buy_nodes  = {model.Par['pHydRetNode'][hr] for hr in model.hr if model.Par['pHydRetMaxBuy' ][hr] > 0}
    hyd_sell_nodes = {model.Par['pHydRetNode'][hr] for hr in model.hr if model.Par['pHydRetMaxSell'][hr] > 0}
    for idx in model.psnnd:
        if idx[-1] not in hyd_buy_nodes and not optmodel.vHydImport[idx].fixed:
            optmodel.vHydImport[idx].fix(0.0)
            nFixedVariables += 1
        if idx[-1] not in hyd_sell_nodes and not optmodel.vHydExport[idx].fixed:
            optmodel.vHydExport[idx].fix(0.0)
            nFixedVariables += 1

    # fixing the ENS in nodes with no electricity and hydrogen demand in market
    for idx in model.psned:
        if model.Par['pVarMaxDemand'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__('vENS')[idx].fix(0.0)
            nFixedVariables += 1
    for idx in model.psnhd:
        if model.Par['pVarMaxDemand'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__('vHNS')[idx].fix(0.0)
            nFixedVariables += 1

    # remove power plants and lines not installed in this period
    for idx in model.psneg + model.psnhg:
        if idx[-1] not in model.AssetCand[idx[-1]] and (model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenInitialPeriod'][idx[-1]] > model.Par['pParEconomicBaseYear'] or model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenFinalPeriod'][idx[-1]] < model.Par['pParEconomicBaseYear']):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput')[idx].fix(0.0)
            nFixedVariables += 1

    for idx in model.psnegt + model.psnhgt:
        if idx[-1] not in model.AssetCand[idx[-1]] and (model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenInitialPeriod'][idx[-1]] > model.Par['pParEconomicBaseYear'] or model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenFinalPeriod'][idx[-1]] < model.Par['pParEconomicBaseYear']):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalOutput2ndBlock')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenStartUp')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenShutDown')[idx].fix(0.0)
            nFixedVariables += 4

    for idx in model.psnegs + model.psnhgs:
        if idx[-1] not in model.AssetCand[idx[-1]] and (model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenInitialPeriod'][idx[-1]] > model.Par['pParEconomicBaseYear'] or model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenFinalPeriod'][idx[-1]] < model.Par['pParEconomicBaseYear']):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalCharge')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}TotalCharge2ndBlock')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(0.0)
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Spillage')[idx].fix(0.0)
            nFixedVariables += 4

    for idx in model.psnela + model.psnhpa:
        if model.NetCand[idx[-3:]] == 'Ele':
            iset = model.elc  # electricity lines
        elif model.NetCand[idx[-3:]] == 'Hyd':
            iset = model.hpc
        if idx[-3:] not in iset and (model.Par[f'p{model.NetCand[idx[-3:]]}NetInitialPeriod'][idx[-3:]] > model.Par['pParEconomicBaseYear'] or model.Par[f'p{model.NetCand[idx[-3:]]}NetFinalPeriod'][idx[-3:]] < model.Par['pParEconomicBaseYear']):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}NetFlow')[idx].fix(0.0)
            nFixedVariables += 1

    # fixing the initial committed electricity units based on the UpTimeZero and DownTimeZero
    for idx in model.psnegt:
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTimeZero'  ][idx[-1]] > 0 and model.n.ord(idx[-2]) <= max(0,min(model.n.ord(idx[-2]),(model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTime'  ][idx[-1]]-model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTimeZero'  ][idx[-1]]))):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].fix(1)
            nFixedVariables += 1
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTimeZero'][idx[-1]] > 0 and model.n.ord(idx[-2]) <= max(0,min(model.n.ord(idx[-2]),(model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTime'][idx[-1]]-model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTimeZero'][idx[-1]]))):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].fix(0)
            nFixedVariables += 1

    # # fixing electricity buys in hours when electricity cost is equal o greater than 1000
    # for idx in model.psner + model.psnhr:
    #     if model.Par['pVarEnergyCost'][idx[-1]][idx[:(len(idx)-1)]] >= 1000.0:
    #         optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}Buy')[idx].fix(0.0)
    #         nFixedVariables += 1
    #     if model.Par['pVarEnergyPrice'][idx[-1]][idx[:(len(idx)-1)]] <= 0:
    #         optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}Sell')[idx].fix(0.0)
    #         nFixedVariables += 1

    log_time('--- Fixing the variables', StartTime, ind_log=indlog)

    # detecting infeasibility: total min ESS output greater than total inflows, total max ESS charge lower than total outflows
    for es in model.egs:
        # if sum(model.Par['pEleMinPower'][es][idx] for idx in model.psn) - sum(model.Par['pEleMaxInflows'][es][idx] for idx in model.psn) > 0.0:
        #     print('### Total minimum output greater than total inflows for Electricity ESS unit ', es)
        #     assert(0==1)
        if sum(model.Par['pEleMaxCharge'][es][idx] for idx in model.psn) - sum(model.Par['pEleMaxOutflows'][es][idx] for idx in model.psn) < 0.0:
            print('### Total maximum charge lower than total outflows for Electricity ESS unit ', es)
            assert(0==1)

    for es in model.hgs:
        if sum(model.Par['pHydMinPower'][es][idx] for idx in model.psn) - sum(model.Par['pHydMaxInflows'][es][idx] for idx in model.psn) > 0.0:
            print('### Total minimum output greater than total inflows for Hydrogen ESS unit ', es)
            assert(0==1)
        if sum(model.Par['pHydMaxCharge'][es][idx] for idx in model.psn) - sum(model.Par['pHydMaxOutflows'][es][idx] for idx in model.psn) < 0.0:
            print('### Total maximum charge lower than total outflows for Hydrogen ESS unit ', es)
            assert(0==1)

    # detecting inventory infeasibility
    for idx in model.psnegs:
        if model.Par['pEleMaxCharge'][idx[-1]][idx[:(len(idx)-1)]] + model.Par['pEleMaxPower'][idx[-1]][idx[:(len(idx)-1)]] > 0.0:
            if model.n.ord(idx[-2]) == model.Par['pEleCycleTimeStep'][idx[-1]]:
                if model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] + sum(model.Par['pDuration'][idx[:(len(idx)-2)]+(n2,)] * (model.Par['pEleMaxInflows'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] - model.Par['pEleMinPower'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] + model.Par['pEleGenEfficiency'][idx[-1]] * model.Par['pEleMaxCharge'][idx[-1]][idx[:(len(idx)-2)]+(n2,)]) for n2 in list(model.n2)[model.n.ord(idx[-2]) - model.Par['pEleCycleTimeStep'][idx[-1]]:model.n.ord(idx[-2])]) < model.Par['pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    print('### Inventory equation violation ', idx)
                    assert(0==1)
            elif model.n.ord(idx[-2]) > model.Par['pEleCycleTimeStep'][idx[-1]]:
                if model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] + sum(model.Par['pDuration'][idx[:(len(idx)-2)]+(n2,)] * (model.Par['pEleMaxInflows'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] - model.Par['pEleMinPower'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] + model.Par['pEleGenEfficiency'][idx[-1]] * model.Par['pEleMaxCharge'][idx[-1]][idx[:(len(idx)-2)]+(n2,)]) for n2 in list(model.n2)[model.n.ord(idx[-2]) - model.Par['pEleCycleTimeStep'][idx[-1]]:model.n.ord(idx[-2])]) < model.Par['pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    print('### Inventory equation violation ', idx)
                    assert(0==1)

    log_time('--- Checking infeasibility', StartTime, ind_log=indlog)

    # # Fixing the shut down in the first 8 hours of every day
    # for idx in model.psnegt:
    #     if model.Par['pEleGenCommitment'][idx[-1]] != 0 and model.n.ord(idx[-2]) % 24 < 10 and idx[-1] in model.hz:
    #         optmodel.__getattribute__(f'vGenShutDown')[idx].fix(0.0)
    #         optmodel.__getattribute__(f'vHydCommitment')[idx].fix(1.0)
    #         nFixedVariables += 2

    # identify if MaxStorage is equal to MinStorage for some ESS units
    for idx in model.psnegs:
        if model.n.ord(idx[-2]) > 1:
            prev_idx = idx[:(len(idx) - 2)] + (model.n.prev(idx[-2]),)
            if abs(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]) <= 1e-5 and abs(model.Par['pEleMaxStorage'][idx[-1]][prev_idx] - model.Par['pEleMinStorage'][idx[-1]][prev_idx]) <= 1e-5:
                # compare the pEleMaxStorage of the current time step with the one of the previous time step
                if model.Par['pEleMaxStorage'][idx[-1]][prev_idx] > model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].setub(model.Par['pEleMaxStorage'][idx[-1]][prev_idx] - model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]])
                    optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].fix(model.Par['pEleMaxStorage'][idx[-1]][prev_idx] - model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]])
                elif model.Par['pEleMaxStorage'][idx[-1]][prev_idx] < model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    optmodel.__getattribute__(f'vEleEnergyInflows')[idx].setub(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMaxStorage'][idx[-1]][prev_idx])
                    optmodel.__getattribute__(f'vEleEnergyInflows')[idx].fix(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMaxStorage'][idx[-1]][prev_idx])
                # else:
                #     optmodel.__getattribute__(f'vEleEnergyInflows')[idx].fix(0.0)
                #     optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].fix(0.0)
                #     nFixedVariables += 2
        else:
            if abs(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]) <= 1e-5:
                if model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] > model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].setub(model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]])
                    optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].fix(model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]])
                elif model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] < model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    optmodel.__getattribute__(f'vEleEnergyInflows')[idx].setub(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    optmodel.__getattribute__(f'vEleEnergyInflows')[idx].fix(model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] - model.Par['pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                # else:
                #     optmodel.__getattribute__(f'vEleEnergyInflows')[idx].fix(0.0)
                #     optmodel.__getattribute__(f'vEleEnergyOutflows')[idx].fix(0.0)
                #     nFixedVariables += 2

    model.nFixedVariables = Param(initialize=round(nFixedVariables), within=NonNegativeIntegers, doc='Number of fixed variables')

    return optmodel
