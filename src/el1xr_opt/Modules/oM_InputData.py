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
import pandas            as pd
from   pyomo.environ     import Set, Param, Var, Binary, UnitInterval, NonNegativeIntegers, PositiveIntegers, NonNegativeReals, Reals, Any, PositiveReals, RangeSet
from   pyomo.dataportal  import DataPortal

def data_processing(DirName, CaseName, DateModel, model):
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

    dictSets = DataPortal()

    # Reading dictionaries from CSV and adding elements to the dictSets
    for set_name, (file_set_name, set_key) in set_definitions.items():
        filename = f'oM_Dict_{file_set_name}_{CaseName}.csv'
        dictSets.load(filename=os.path.join(path_to_read, filename), set=set_key, format='set')

    # Defining sets in the model
    for set_name, (file_set_name, set_key) in set_definitions.items():
        is_ordered = set_name not in {'egg', 'hgg', 'edd', 'hdd', 'err', 'hrr', 'st', 'gt', 'nd', 'ni', 'nf', 'cc', 'c2', 'ndzn'}
        setattr(model, set_name, Set(initialize=dictSets[set_key], ordered=is_ordered, doc=f'{file_set_name}'))

    #%% Reading the input data
    data_frames = {}

    files_list = [file.split("_")[2] for file in os.listdir(os.path.join(path_to_read)) if 'oM_Data' in file]

    for file_set_name in files_list:
        file_name = f'oM_Data_{file_set_name}_{CaseName}.csv'
        data_frames[f'df{file_set_name}'] = pd.read_csv(os.path.join(path_to_read, file_name))
        unnamed_columns = [col for col in data_frames[f'df{file_set_name}'].columns if 'Unnamed' in col]
        data_frames[f'df{file_set_name}'].set_index(unnamed_columns, inplace=True)
        data_frames[f'df{file_set_name}'].index.names = [None] * len(unnamed_columns)

    # substitute NaN by 0
    for df in data_frames.values():
        df.fillna(0.0, inplace=True)

    # Define prefixes and suffixes
    model.reserves_prefixes     = ['Up_SR', 'Down_SR','Up_TR', 'Down_TR']
    model.SR_reserves           = ['Up_SR', 'Down_SR']
    model.TR_reserves           = ['Up_TR', 'Down_TR']
    model.gen_frames_suffixes   = ['VarMinGeneration', 'VarMaxGeneration',
                                   'VarMinConsumption', 'VarMaxConsumption',
                                   'VarMinStorage', 'VarMaxStorage',
                                   'VarMinInflows', 'VarMaxInflows',
                                   'VarMinOutflows', 'VarMaxOutflows',
                                   'VarMinEnergy', 'VarMaxEnergy',
                                   'VarMinFuelCost', 'VarMaxFuelCost',
                                   'VarMinEmissionCost', 'VarMaxEmissionCost',
                                   'VarPositionConsumption', 'VarPositionGeneration',
                                   'VarStartUp', 'VarShutDown',]
    model.demand_frames_suffixes = ['VarMaxDemand', 'VarMinDemand']
    model.retail_frames_suffixes = ['VarEnergyCost', 'VarEnergyPrice']

    # Apply the condition to each specified column
    for keys, df in data_frames.items():
        if [1 for suffix in model.gen_frames_suffixes if suffix in keys]:
            data_frames[keys] = df.where(df > 0.0, 0.0)

    # Apply the condition to each specified column
    for column in model.gen_frames_suffixes:
        data_frames[f'df{column}'] = data_frames[f'df{column}'].where(data_frames[f'df{column}'] > 0.0)

    reading_time = round(time.time() - start_time)
    print('--- Reading the CSV files:                                             {} seconds'.format(reading_time))
    start_time = time.time()

    # Constants
    factor1 = 1e-0  # Conversion factor
    factor2 = 1e-3  # Conversion factor
    model.factor1 = factor1
    model.factor2 = factor2

    # Option Indicators
    option_ind = data_frames['dfOption'].columns.to_list()

    # Extract and cast option indicators
    parameters_dict = {f'pOpt{indicator}': data_frames['dfOption'][indicator].iloc[0].astype('int') for indicator in option_ind}

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
    # Extract and cast generation parameters
    for suffix in model.gen_frames_suffixes:
        # print(suffix)
        # parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'][model.ehg] * factor1
        parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'].reindex(columns=model.ehg, fill_value=0.0) * factor1

    # Merging sets gg and hh
    model.ehr = model.err | model.hrr
    # Extract and cast retail parameters
    for suffix in model.retail_frames_suffixes:
        parameters_dict[f'p{suffix}'] = data_frames[f'df{suffix}'].reindex(columns=model.ehr, fill_value=0.0) * factor1

    # Extract and cast operating reserve parameters for RM and RT markets
    for ind in model.reserves_prefixes:
        parameters_dict[f'pOperatingReservePrice_{ind}'     ] = data_frames[f'dfOperatingReservePrice'     ][ind] * factor1
        parameters_dict[f'pOperatingReserveRequire_{ind}'   ] = data_frames[f'dfOperatingReserveRequire'   ][ind] * factor1
        parameters_dict[f'pOperatingReserveActivation_{ind}'] = data_frames[f'dfOperatingReserveActivation'][ind]

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
    idx_gen_factoring  = ['MaximumPower', 'MinimumPower', 'StandByPower', 'MaximumCharge', 'MinimumCharge', 'OMVariableCost', 'ProductionFunction', 'MaxCompressorConsumption',
                      'RampUp', 'RampDown', 'CO2EmissionRate', 'MaxOutflowsProd', 'MinOutflowsProd', 'MaxInflowsCons', 'MinInflowsCons', 'OutflowsRampDown', 'OutflowsRampUp']
    # demand indicators
    EleDemand_ind = data_frames['dfElectricityDemand'].columns.to_list()
    HydDemand_ind = data_frames['dfHydrogenDemand'].columns.to_list()
    idx_dem_factoring = ['MaximumPower']

    # retail indicators
    EleRetail_ind = data_frames['dfElectricityRetail'].columns.to_list()
    HydRetail_ind = data_frames['dfHydrogenRetail'].columns.to_list()
    idx_retail_factoring = ['MaximumEnergyBuy', 'MinimumEnergyBuy', 'MaximumEnergySell', 'MinimumEnergySell']

    def update_parameters(indices, factoring_indices, data_key, prefix):
        for idx in indices:
            if idx in factoring_indices:
                parameters_dict[f'{prefix}{idx}'] = data_frames[data_key][idx] * factor1
            else:
                parameters_dict[f'{prefix}{idx}'] = data_frames[data_key][idx]

    # Update electricity-related parameters
    update_parameters(EleGeneration_ind, idx_gen_factoring, 'dfElectricityGeneration', 'pEleGen')
    update_parameters(EleDemand_ind, idx_dem_factoring, 'dfElectricityDemand', 'pEleDem')
    update_parameters(EleRetail_ind, idx_retail_factoring, 'dfElectricityRetail', 'pEleRet')

    # Update hydrogen-related parameters
    update_parameters(HydGeneration_ind, idx_gen_factoring, 'dfHydrogenGeneration', 'pHydGen')
    update_parameters(HydDemand_ind, idx_dem_factoring, 'dfHydrogenDemand', 'pHydDem')
    update_parameters(HydRetail_ind, idx_retail_factoring, 'dfHydrogenRetail', 'pHydRet')

    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector[0:3]}GenLinearVarCost'     ] = parameters_dict[f'p{sector[0:3]}GenLinearTerm'          ] * model.factor1 * parameters_dict[f'p{sector[0:3]}GenFuelCost'] + parameters_dict[f'p{sector[0:3]}GenOMVariableCost'] * model.factor1  # linear   term variable cost             [MEUR/GWh]
        parameters_dict[f'p{sector[0:3]}GenConstantVarCost'   ] = parameters_dict[f'p{sector[0:3]}GenConstantTerm'        ] * model.factor2 * parameters_dict[f'p{sector[0:3]}GenFuelCost']                                                                        # constant term variable cost             [MEUR/h]
        parameters_dict[f'p{sector[0:3]}GenCO2EmissionCost'   ] = parameters_dict[f'p{sector[0:3]}GenCO2EmissionRate'     ] * model.factor1 * parameters_dict[f'pParCO2Cost']                                                                                      # CO2 emission cost                       [MEUR/GWh]
        parameters_dict[f'p{sector[0:3]}GenStartUpCost'       ] = parameters_dict[f'p{sector[0:3]}GenStartUpCost'         ] * model.factor2                                                                                                                        # generation startup cost                 [MEUR]
        parameters_dict[f'p{sector[0:3]}GenShutDownCost'      ] = parameters_dict[f'p{sector[0:3]}GenShutDownCost'        ] * model.factor2                                                                                                                        # generation shutdown cost                [MEUR]
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
    parameters_dict[f'pEleNetSwOnTime' ] = round(parameters_dict[f'pEleNetSwOnTime' ] / parameters_dict['pParTimeStep']).astype('int')

    transforming_time = round(time.time() - start_time)
    print('--- Transforming the dataframes:                                       {} seconds'.format(transforming_time))
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
    parameters_dict['pEleGenNoOperatingReserve'] = parameters_dict['pEleGenNoOperatingReserve'].map(idxDict)
    parameters_dict['pEleGenMaxCommitment'     ] = parameters_dict['pEleGenMaxCommitment'     ].map(idxDict)
    parameters_dict['pHydGenStandByStatus'     ] = parameters_dict['pHydGenStandByStatus'     ].map(idxDict)
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
    model.hd   = Set(doc='hydrogen demand        units ', initialize=[hdd    for hdd  in           model.hdd if  parameters_dict['pHydDemMaximumPower']     [hdd]  == 0.0])
    model.hr   = Set(doc='hydrogen retail        units ', initialize=[hrr    for hrr  in           model.hrr if  parameters_dict['pHydRetMaximumEnergyBuy'] [hrr]  >  0.0 or   parameters_dict['pHydRetMaximumEnergySell'] [hrr] >  0.0 or  parameters_dict['pHydRetMinimumEnergyBuy']  [hrr] >  0.0 or parameters_dict['pHydRetMinimumEnergySell'][hrr] > 0.0])
    model.hgs  = Set(doc='hydrogen storage       units ', initialize=[hgs    for hgs  in           model.hg  if  parameters_dict['pHydGenMaximumStorage']   [hgs]  >  0.0 and (parameters_dict['pVarMaxInflows'].sum()     [hgs] >  0.0 or  parameters_dict['pVarMaxOutflows'].sum()    [hgs] >  0.0 or parameters_dict['pHydGenMaximumCharge'][hgs] > 0.0)])
    model.hgc  = Set(doc='hydrogen candidate     units ', initialize=[hgc    for hgc  in           model.hg  if  parameters_dict['pHydGenInvestCost']       [hgc]  >  0.0])
    model.hgsc = Set(doc='hydrogen storage       units ', initialize=[hgsc   for hgsc in           model.hgs if  parameters_dict['pHydGenInvestCost']      [hgsc]  >  0.0])
    model.e2h  = Set(doc='ele2hyd                units ', initialize=[hg     for hg   in           model.hg  if  parameters_dict['pHydGenProductionFunction'][hg]  >  0.0])
    model.h2e  = Set(doc='hyd2ele                units ', initialize=[eg     for eg   in           model.eg  if  parameters_dict['pEleGenProductionFunction'][eg]  >  0.0])
    model.ebr  = Set(doc='all input branches           ', initialize=[(ni,nf) for ni,nf in sEleBrList])
    model.eln  = Set(doc='all input lines              ', initialize=data_frames['dfElectricityNetwork'].index.to_list())
    model.ela  = Set(doc='all real lines               ', initialize=[el for el in model.eln if parameters_dict['pEleNetReactance'][el] != 0.0 and  parameters_dict['pEleNetTTC'][el] > 0.0 and parameters_dict['pEleNetTTCBck'][el] > 0.0 and parameters_dict['pEleNetInitialPeriod'][el] <= parameters_dict['pParEconomicBaseYear'] and parameters_dict['pEleNetFinalPeriod'][el] >= parameters_dict['pParEconomicBaseYear']])
    model.els  = Set(doc='all real switch lines        ', initialize=[el for el in model.ela if parameters_dict['pEleNetSwitching'][el]])
    model.elc  = Set(doc='candidate lines              ', initialize=[el for el in model.ela if parameters_dict['pEleNetFixedInvestmentCost'][el] > 0.0])
    model.ndrf = Set(doc='reference node               ', initialize=[nd for nd in model.nd  if nd in parameters_dict['pParReferenceNode']])
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


    print('--- Defining the sets:                                                 {} seconds'.format(round(time.time() - start_time)))
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
    model.psnesc   = [(p, sc, n, es        )     for p, sc, n, es             in model.psc   * model.esc ]
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

    # inverse index node to electricity/hydrogen demand
    model.n2ed       = Set(initialize=sorted((parameters_dict['pEleDemNode'][ed], ed)   for     ed     in model.ed                                                                ), ordered=False, doc='node to demand'         )
    model.z2ed       = Set(initialize=sorted((zn,ed)                                   for (nd,ed,zn) in model.n2ed * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to demand'         )

    model.n2hd       = Set(initialize=sorted((parameters_dict['pHydDemNode'][hd], hd)   for     hd     in model.hd                                                                ), ordered=False, doc='node to demand'         )
    model.z2hd       = Set(initialize=sorted((zn,hd)                                   for (nd,hd,zn) in model.n2hd * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to demand'         )

    # inverse index node to electricity/hydrogen retail
    model.n2er       = Set(initialize=sorted((parameters_dict['pEleRetNode'][er], er)   for     er     in model.er                                                                ), ordered=False, doc='node to retail'         )
    model.z2er       = Set(initialize=sorted((zn,er)                                   for (nd,er,zn) in model.n2er * model.zn if (nd,zn) in model.ndzn                           ), ordered=False, doc='zone to retail'         )

    model.n2hr       = Set(initialize=sorted((parameters_dict['pHydRetNode'][hr], hr)   for     hr     in model.hr                                                                ), ordered=False, doc='node to retail'         )
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

    print('--- Defining the instrumental sets:                                    {} seconds'.format(round(time.time() - start_time)))
    start_time = time.time()

    ## Defining the temporal reference for the model
    # Hour of the day
    hour_of_day   = DateModel.hour
    # Day of the year
    day_of_year   = DateModel.timetuple().tm_yday
    # Hour of the year
    hour_of_year = (day_of_year - 1) * 24 + hour_of_day
    # create a dataframe with model.n as index and columns like hour of the year, day of the year and month of the year taking from argument DateModel
    # Convert 'DateTime' to a datetime object if it isn't already
    parameters_dict['pDate'] = pd.DataFrame(index=pd.Index(model.psn), columns=['DateTime'])

    # Generate DateTime for each psn based on hour difference from hour_of_year
    parameters_dict['pDate']['DateTime'] = parameters_dict['pDate'].index.get_level_values(2).map(lambda x: DateModel + pd.Timedelta(hours=(int(x[1:]) - hour_of_year)))

    # Convert 'DateTime' to a datetime object if it isn't already
    parameters_dict['pDate']['DateTime'] = pd.to_datetime(parameters_dict['pDate']['DateTime'])

    # Calculate Month, Day of Year, Hour, and Hour of Year
    parameters_dict['pDate']['Month'] = parameters_dict['pDate']['DateTime'].dt.month
    parameters_dict['pDate']['Day'] = parameters_dict['pDate']['DateTime'].dt.dayofyear
    parameters_dict['pDate']['Hour'] = parameters_dict['pDate']['DateTime'].dt.hour
    parameters_dict['pDate']['HourOfYear'] = (parameters_dict['pDate']['Day'] - 1) * 24 + parameters_dict['pDate']['Hour']

    # Define set of hours of the year
    model.hoy = [int(i) for i in parameters_dict['pDate']['HourOfYear'].unique()]
    # Define set of days of the year
    model.doy = [int(i) for i in parameters_dict['pDate']['Day'].unique()]
    # Define set of months of the year
    model.moy = [int(i) for i in parameters_dict['pDate']['Month'].unique()]
    # Define the relationship between loadlevel and month
    model.n2m = [(idx[2], int(parameters_dict['pDate']['Month'][idx])) for idx in model.psn]
    # Define the relationship between loadlevel and day of the year
    model.n2d = [(idx[2], int(parameters_dict['pDate']['Day'][idx])) for idx in model.psn]

    model.psm = [(p, sc, m) for p, sc, m in model.ps * model.moy]
    model.psd = [(p, sc, d) for p, sc, d in model.ps * model.doy]

    print('--- Defining the temporal reference for the model:                     {} seconds'.format(round(time.time() - start_time)))
    start_time = time.time()

    # minimum and maximum variable power, charge, and storage capacity
    dict_sector = {'Ele': model.eg, 'Hyd': model.hg}
    for sector in ['Ele', 'Hyd']:
        parameters_dict[f'p{sector}MinPower'   ] = parameters_dict[f'pVarMinGeneration'  ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumPower'   ])
        parameters_dict[f'p{sector}MaxPower'   ] = parameters_dict[f'pVarMaxGeneration'  ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumPower'   ])
        parameters_dict[f'p{sector}MinCharge'  ] = parameters_dict[f'pVarMinConsumption' ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumCharge'  ])
        parameters_dict[f'p{sector}MaxCharge'  ] = parameters_dict[f'pVarMaxConsumption' ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumCharge'  ])
        parameters_dict[f'p{sector}MinStorage' ] = parameters_dict[f'pVarMinStorage'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinimumStorage' ])
        parameters_dict[f'p{sector}MaxStorage' ] = parameters_dict[f'pVarMaxStorage'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaximumStorage' ])
        parameters_dict[f'p{sector}MinInflows' ] = parameters_dict[f'pVarMinInflows'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinInflowsCons' ])
        parameters_dict[f'p{sector}MaxInflows' ] = parameters_dict[f'pVarMaxInflows'     ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaxInflowsCons' ])
        parameters_dict[f'p{sector}MinOutflows'] = parameters_dict[f'pVarMinOutflows'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMinOutflowsProd'])
        parameters_dict[f'p{sector}MaxOutflows'] = parameters_dict[f'pVarMaxOutflows'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenMaxOutflowsProd'])
        parameters_dict[f'p{sector}MinFuelCost'] = parameters_dict[f'pVarMinFuelCost'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenLinearVarCost'  ])
        parameters_dict[f'p{sector}MaxFuelCost'] = parameters_dict[f'pVarMaxFuelCost'    ][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenLinearVarCost'  ])
        parameters_dict[f'p{sector}MinCO2Cost' ] = parameters_dict[f'pVarMinEmissionCost'][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenCO2EmissionCost'])
        parameters_dict[f'p{sector}MaxCO2Cost' ] = parameters_dict[f'pVarMaxEmissionCost'][dict_sector[sector]].replace(0.0, parameters_dict[f'p{sector}GenCO2EmissionCost'])

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
        parameters_dict[f'p{sector}InitialInventory'] = pd.DataFrame([parameters_dict[f'p{sector}GenInitialStorage']] * len(parameters_dict[f'p{sector}MinStorage'].index), index=parameters_dict[f'p{sector}MinStorage'].index, columns=parameters_dict[f'p{sector}GenInitialStorage'].index)

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
        parameters_dict[f'p{sector}CycleTimeStep'   ] = parameters_dict[f'p{sector}GenStorageType' ].map(idxCycle                                                                                                                                                            ).astype('int')
        parameters_dict[f'p{sector}OutflowsTimeStep'] = parameters_dict[f'p{sector}GenOutflowsType'].map(idxOutflows).where(parameters_dict['pVarMinOutflows'][dict_sector[sector]].sum() + parameters_dict['pVarMaxOutflows'][dict_sector[sector]].sum() > 0.0, other = 8736).astype('int')
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
    parameters_dict['pVarEnergyCost'    ] = parameters_dict['pVarEnergyCost'    ].loc[model.psn]
    parameters_dict['pVarEnergyPrice'   ] = parameters_dict['pVarEnergyPrice'   ].loc[model.psn]
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

    def apply_mask_and_set_zero(parameter_dict, key, sector_key, threshold):
        selected_rows = parameter_dict[key].loc[:, sector_key]
        mask = selected_rows < threshold
        parameter_dict[key].loc[:,sector_key] = selected_rows.where(~mask, 0.0)

    # these parameters are in GW or tH2
    for sector in ['Ele', 'Hyd']:
        if sector == 'Ele':
            pEpsilon = pEleEpsilon
        else:
            pEpsilon = pHydEpsilon

        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinPower'        , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxPower'        , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinCharge'       , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxCharge'       , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinStorage'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxStorage'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinInflows'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxInflows'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinOutflows'     , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxOutflows'     , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinFuelCost'     , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxFuelCost'     , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MinCO2Cost'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}MaxCO2Cost'      , dict_sector[sector], pEpsilon)
        apply_mask_and_set_zero(parameters_dict, f'p{sector}InitialInventory', dict_sector[sector], pEpsilon)

    apply_mask_and_set_zero(parameters_dict, 'pVarMaxDemand'     , model.ed, pEleEpsilon)
    apply_mask_and_set_zero(parameters_dict, 'pVarMinDemand'     , model.ed, pEleEpsilon)
    apply_mask_and_set_zero(parameters_dict, 'pVarMaxDemand'     , model.hd, pHydEpsilon)
    apply_mask_and_set_zero(parameters_dict, 'pVarMinDemand'     , model.hd, pHydEpsilon)

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
    parameters_dict['pEleInitialOutput'] = pd.Series([0.0]*len(model.eg), model.ps * model.eg)
    parameters_dict['pEleInitialUC'    ] = pd.Series([0  ]*len(model.eg), model.ps * model.eg)
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
            if parameters_dict['pEleGenUpTime'][go] - parameters_dict['pEleGenUpTimeZero'][go] > 0:
                parameters_dict['pEleInitialUC'][p,sc,go] = 1
            if parameters_dict['pEleGenDownTime'][go] - parameters_dict['pEleGenDownTimeZero'][go] > 0:
                parameters_dict['pEleInitialUC'][p,sc,go] = 0

    # determine the initial committed hydrogen units and their output
    parameters_dict['pHydInitialOutput'] = pd.Series([0.0]*len(model.hg), model.ps * model.hg)
    parameters_dict['pHydInitialUC'    ] = pd.Series([0  ]*len(model.hg), model.ps * model.hg)
    for p,sc in model.ps:
        parameters_dict['pHydSystemOutput'] = 0.0
        for hg in model.hg:
            n1 = next(iter(model.n))
            if parameters_dict['pHydSystemOutput'] < sum(parameters_dict['pVarMaxDemand'][hd][p,sc,n1] for hd in model.hd):
                if   hg in model.hgr:
                    parameters_dict['pHydInitialOutput'][p,sc,hg] = parameters_dict['pHydMaxPower'][hg][p,sc,n1]
                elif hg in model.hg:
                    parameters_dict['pHydInitialOutput'][p,sc,hg] = parameters_dict['pHydMinPower'][hg][p,sc,n1]
                parameters_dict['pHydInitialUC'    ][p,sc,hg] = 1
                parameters_dict['pHydSystemOutput' ]     += parameters_dict['pHydInitialOutput'][p,sc,hg]
            # calculating if the unit was committed before of the time periods or not
            if parameters_dict['pHydGenUpTime'][hg] - parameters_dict['pHydGenUpTimeZero'][hg] > 0:
                parameters_dict['pHydInitialUC'][p,sc,hg] = 1
            if parameters_dict['pHydGenDownTime'][hg] - parameters_dict['pHydGenDownTimeZero'][hg] > 0:
                parameters_dict['pHydInitialUC'][p,sc,hg] = 0

    # load levels multiple of cycles for each ESS/generator
    model.negs         = [(n,egs ) for n,egs  in model.n * model.egs  if model.n.ord(n) %     parameters_dict['pEleCycleTimeStep'   ][egs ] == 0]
    model.negsc        = [(n,egsc) for n,egsc in model.n * model.egsc if model.n.ord(n) %     parameters_dict['pEleCycleTimeStep'   ][egsc] == 0]
    model.negso        = [(n,egs)  for n,egs  in model.n * model.egs  if model.n.ord(n) %     parameters_dict['pEleOutflowsTimeStep'][egs] == 0]

    for sector in ['Ele', 'Hyd']:
        if sector == 'Ele':
            retail = model.er
        else:
            retail = model.hr
        # small values are converted to 0
        pGenerationPeak   = parameters_dict[f'p{sector}MaxPower'].sum(axis=1).max()
        pEpsilon_capacity = pGenerationPeak * 1e-5
        pCostPeak         = parameters_dict[f'p{sector}GenLinearTerm'].max()
        pEpsilon_cost     = pCostPeak * model.factor1
        pPricePeak        = parameters_dict['pVarEnergyPrice'][retail].max()         # electricity price
        pEpsilon_price    = pPricePeak * model.factor1

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

    # calculating the availability of the unit
    parameters_dict['pVarStartUp' ] *= model.factor1
    parameters_dict['pVarShutDown'] *= model.factor1
    parameters_dict['pVarFixedAvailability'] = parameters_dict['pVarStartUp'].copy()

    # Loop through each sector and set the appropriate sector set
    for sector in ['Ele', 'Hyd']:
        set_sector = model.psneg if sector == 'Ele' else model.psnhg

        # Iterate over each index in the set
        for idx in set_sector:
            parameters_dict['pVarFixedAvailability'].loc[idx[:3], idx[-1]] = 1
            # Check if the fixed availability for the generator is enabled
            if parameters_dict[f'p{sector}GenFixedAvailability'][idx[-1]] == 1:
                # Define variables for readability
                start_up = int(parameters_dict['pVarStartUp'][idx[-1]][idx[:3]])
                shut_down = int(parameters_dict['pVarShutDown'][idx[-1]][idx[:3]])
                if idx[2] == model.n.first():
                    parameters_dict['pVarFixedAvailability'].loc[idx[:3], idx[-1]] = 1  # first load level
                else:
                    parameters_dict['pVarFixedAvailability'].loc[idx[:3], idx[-1]] = parameters_dict['pVarFixedAvailability'].loc[(idx[0], idx[1], model.n.prev(idx[2])), idx[-1]] + shut_down - start_up

            # print(f'Fixed availability, start-up, and shut-down for {sector} unit {idx[-1]} in period {idx[0]}, scenario {idx[1]}, and load level {idx[2]}: {parameters_dict["pVarFixedAvailability"][idx[-1]][idx[:3]]}, {parameters_dict["pVarStartUp"][idx[-1]][idx[:3]]}, and {parameters_dict["pVarShutDown"][idx[-1]][idx[:3]]}')

    # save parameters_dict['pVarFixedAvailability'], parameters_dict['pVarStartUp'], and parameters_dict['pVarShutDown'] by creating a df of merging the three dfs and save in only one csv file
    df_fixed_availability = parameters_dict['pVarFixedAvailability'].stack().to_frame(name='Value')
    df_fixed_availability['Type'] = 'FixedAvailability'
    df_start_up = parameters_dict['pVarStartUp'].stack().to_frame(name='Value')
    df_start_up['Type'] = 'StartUp'
    df_shut_down = parameters_dict['pVarShutDown'].stack().to_frame(name='Value')
    df_shut_down['Type'] = 'ShutDown'
    df = pd.concat([df_fixed_availability, df_start_up, df_shut_down], axis=0)
    # df.reset_index().rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Unit'}).to_csv(os.path.join(path_to_read, 'oM_Validation_FixedAvailability.csv'), index=False)

    model.Par = parameters_dict

    print('--- Defining the parameters:                                           {} seconds'.format(round(time.time() - start_time)))

    return model

def create_variables(model, optmodel):

    #
    print('-- Defining the variables')
    #%% start time
    StartTime = time.time()

    # model.Peaks   = Set(initialize=[ i for i in range(1,4,1)]) # number of selected peaks hours
    if model.Par['pParNumberPowerPeaks'] == 0:
        model.Peaks   = RangeSet(1)
    else:
        model.Peaks   = RangeSet(model.Par['pParNumberPowerPeaks']) # number of selected peaks hours

    #%% total variables
    setattr(optmodel, 'vTotalSCost',             Var(                      within=            Reals, doc='total system                         cost [MEUR]'))

    setattr(optmodel, 'vTotalEleMCost',          Var(model.psn,   within=             Reals, doc='total variable electricity market    cost [MEUR]'))
    setattr(optmodel, 'vTotalHydMCost',          Var(model.psn,   within=             Reals, doc='total variable hydrogen    market    cost [MEUR]'))
    setattr(optmodel, 'vTotalEleGCost',          Var(model.psn,   within=             Reals, doc='total variable electricity prod      cost [MEUR]'))
    setattr(optmodel, 'vTotalHydGCost',          Var(model.psn,   within=             Reals, doc='total variable hydrogen    prod      cost [MEUR]'))
    setattr(optmodel, 'vTotalEleCCost',          Var(model.psn,   within=             Reals, doc='total variable electricity cons      cost [MEUR]'))
    setattr(optmodel, 'vTotalHydCCost',          Var(model.psn,   within=             Reals, doc='total variable hydrogen    cons      cost [MEUR]'))
    setattr(optmodel, 'vTotalECost',             Var(model.psn,   within=             Reals, doc='total system   emission              cost [MEUR]'))
    setattr(optmodel, 'vTotalEleRCost',          Var(model.psn,   within=             Reals, doc='total system electricity reliability cost [MEUR]'))
    setattr(optmodel, 'vTotalHydRCost',          Var(model.psn,   within=             Reals, doc='total system hydrogen    reliability cost [MEUR]'))
    setattr(optmodel, 'vTotalEleTradeCost',      Var(model.psn,   within=             Reals, doc='total energy buy                     cost [MEUR]'))
    setattr(optmodel, 'vTotalEleTradeProfit',    Var(model.psn,   within=             Reals, doc='total energy sell                  profit [MEUR]'))
    setattr(optmodel, 'vTotalHydTradeCost',      Var(model.psn,   within=             Reals, doc='total hydrogen buy                   cost [MEUR]'))
    setattr(optmodel, 'vTotalHydTradeProfit',    Var(model.psn,   within=             Reals, doc='total hydrogen sell                profit [MEUR]'))
    setattr(optmodel, 'vTotalElePeakCost',       Var(model.ps ,   within=             Reals, doc='total electricity peak               cost [MEUR]'))
    setattr(optmodel, 'vTotalHydPeakCost',       Var(model.ps ,   within=             Reals, doc='total hydrogen    peak               cost [MEUR]'))

    setattr(optmodel, 'vElePeak',                Var(model.psm, model.er, model.Peaks, within=PositiveReals, doc='electricity peak            [GW]'))
    # setattr(optmodel, 'vElePeakBuyAux',          Var(model.psner,         model.Peaks, within=PositiveReals, doc='electricity peak buy        [GW]'))
    setattr(optmodel, 'vHydPeak',                Var(model.psm, model.hr, model.Peaks, within=PositiveReals, doc='hydrogen    peak           [tH2]'))
    # setattr(optmodel, 'vHydPeakBuyAux',          Var(model.psnhr,         model.Peaks, within=PositiveReals, doc='hydrogen    peak buy       [tH2]'))

    # Define continuous variables
    setattr(optmodel, 'vEleBuy',                 Var(model.psner,   within=NonNegativeReals, doc='energy buy                                  [GW]'))
    setattr(optmodel, 'vEleSell',                Var(model.psner,   within=NonNegativeReals, doc='energy sell                                 [GW]'))
    setattr(optmodel, 'vEleDemand',              Var(model.psned,   within=NonNegativeReals, doc='electricity demand                          [GW]'))
    setattr(optmodel, 'vENS',                    Var(model.psned,   within=NonNegativeReals, doc='energy demand                               [GW]'))
    setattr(optmodel, 'vEleTotalOutput',         Var(model.psneg,   within=NonNegativeReals, doc='total electricity output of the unit        [GW]'))
    setattr(optmodel, 'vEleTotalOutput2ndBlock', Var(model.psnegnr, within=NonNegativeReals, doc='second block of the unit                    [GW]'))
    setattr(optmodel, 'vEleTotalCharge',         Var(model.psneh,   within=NonNegativeReals, doc='ESS total charge power                      [GW]'))
    setattr(optmodel, 'vEleTotalCharge2ndBlock', Var(model.psneh,   within=NonNegativeReals, doc='ESS       charge power                      [GW]'))
    setattr(optmodel, 'vEleEnergyInflows',       Var(model.psnegs,  within=NonNegativeReals, doc='unscheduled inflows  of all ESS units      [GWh]'))
    setattr(optmodel, 'vEleEnergyOutflows',      Var(model.psnegs,  within=NonNegativeReals, doc='scheduled   outflows of all ESS units      [GWh]'))
    setattr(optmodel, 'vEleInventory',           Var(model.psnegs,  within=NonNegativeReals, doc='ESS inventory                              [GWh]'))
    setattr(optmodel, 'vEleSpillage',            Var(model.psnegs,  within=NonNegativeReals, doc='ESS spillage                               [GWh]'))

    setattr(optmodel, 'vHydBuy',                 Var(model.psnhr,   within=NonNegativeReals, doc='hydrogen buy        in node                [tH2]'))
    setattr(optmodel, 'vHydSell',                Var(model.psnhr,   within=NonNegativeReals, doc='hydrogen sell       in node                [tH2]'))
    setattr(optmodel, 'vHydDemand',              Var(model.psnhd,   within=NonNegativeReals, doc='hydrogen demand                            [tH2]'))
    setattr(optmodel, 'vHNS',                    Var(model.psnhd,   within=NonNegativeReals, doc='hydrogen demand                            [tH2]'))
    setattr(optmodel, 'vHydTotalOutput',         Var(model.psnhg,   within=NonNegativeReals, doc='total hydrogen output of the unit          [tH2]'))
    setattr(optmodel, 'vHydTotalOutput2ndBlock', Var(model.psnhg,   within=NonNegativeReals, doc='second block of the unit                   [tH2]'))
    setattr(optmodel, 'vHydTotalCharge',         Var(model.psnhe,   within=NonNegativeReals, doc='H2S total charge power                     [tH2]'))
    setattr(optmodel, 'vHydTotalCharge2ndBlock', Var(model.psnhe,   within=NonNegativeReals, doc='H2S       charge power                     [tH2]'))
    setattr(optmodel, 'vHydEnergyInflows',       Var(model.psnhgs,  within=NonNegativeReals, doc='unscheduled inflows  of all H2S units      [tH2]'))
    setattr(optmodel, 'vHydEnergyOutflows',      Var(model.psnhgs,  within=NonNegativeReals, doc='scheduled   outflows of all H2S units      [tH2]'))
    setattr(optmodel, 'vHydInventory',           Var(model.psnhgs,  within=NonNegativeReals, doc='H2S inventory                              [tH2]'))
    setattr(optmodel, 'vHydSpillage',            Var(model.psnhgs,  within=NonNegativeReals, doc='H2S spillage                               [tH2]'))

    setattr(optmodel, 'vEleNetFlow',             Var(model.psnela,  within=           Reals, doc='electricity net flow                        [GW]'))
    setattr(optmodel, 'vHydNetFlow',             Var(model.psnhpa,  within=           Reals, doc='hydrogen    net flow                       [tH2]'))
    setattr(optmodel, 'vEleNetTheta',            Var(model.psnnd,   within=           Reals, doc='electricity net theta                       [GW]'))

    if sum(model.Par['pEleDemFlexible'][idx] for idx in model.ed) > 0:
        setattr(optmodel, 'vEleDemFlex',          Var(model.psned,  within=           Reals, doc='flexible electricity demand                 [GW]'))

    print('--- Defining the continuous variables:                                 {} seconds'.format(round(time.time() - StartTime)))

    # Define binary variables
    if model.Par['pOptIndBinGenOperat'] == 0:
        setattr(optmodel, 'vEleGenCommitment',   Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vEleGenStartUp',      Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vEleGenShutDown',     Var(model.psnegt,             within=UnitInterval, initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vEleStorOperat',      Var(model.psnegs,             within=UnitInterval, initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vElePeakHourInd',     Var(model.psner, model.Peaks, within=UnitInterval, initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vHydGenCommitment',   Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vHydGenStartUp',      Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vHydGenShutDown',     Var(model.psnhg,              within=UnitInterval, initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vHydStorOperat',      Var(model.psnhgs,             within=UnitInterval, initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vHydPeakHourInd',     Var(model.psner, model.Peaks, within=UnitInterval, initialize=0, doc='peak hour indicator                   '))
    else:
        setattr(optmodel, 'vEleGenCommitment',   Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vEleGenStartUp',      Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vEleGenShutDown',     Var(model.psnegt,             within=Binary,       initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vEleStorOperat',      Var(model.psnegs,             within=Binary,       initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vElePeakHourInd',     Var(model.psner, model.Peaks, within=Binary,       initialize=0, doc='peak hour indicator                   '))
        setattr(optmodel, 'vHydGenCommitment',   Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary commitment           '))
        setattr(optmodel, 'vHydGenStartUp',      Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary start-up             '))
        setattr(optmodel, 'vHydGenShutDown',     Var(model.psnhg,              within=Binary,       initialize=0, doc='generator binary shut-down            '))
        setattr(optmodel, 'vHydStorOperat',      Var(model.psnhgs,             within=Binary,       initialize=0, doc='storage   binary operation            '))
        setattr(optmodel, 'vHydPeakHourInd',     Var(model.psner, model.Peaks, within=Binary,       initialize=0, doc='peak hour indicator                   '))

    if model.Par['pOptIndBinNetOperat'] == 0:
        setattr(optmodel, 'vEleNetCommit',       Var(model.psnela,  within=UnitInterval, initialize=0, doc='network binary operation              '))
        setattr(optmodel, 'vHydNetCommit',       Var(model.psnela,  within=UnitInterval, initialize=0, doc='network binary operation              '))
    else:
        setattr(optmodel, 'vEleNetCommit',       Var(model.psnela,  within=Binary,       initialize=0, doc='network binary operation              '))
        setattr(optmodel, 'vHydNetCommit',       Var(model.psnela,  within=Binary,       initialize=0, doc='network binary operation              '))

    print('--- Defining the binary variables:                                     {} seconds'.format(round(time.time() - StartTime)))

    # Precompute the bounds
    # psn
    std_upper_bound = 1e4
    std_lower_bound = -1e4

    # List of variables to set bounds
    cost_vars = [optmodel.vTotalEleMCost, optmodel.vTotalEleGCost, optmodel.vTotalEleCCost, optmodel.vTotalEleRCost,
                 optmodel.vTotalHydMCost, optmodel.vTotalHydGCost, optmodel.vTotalHydCCost, optmodel.vTotalHydRCost,
                 optmodel.vTotalECost, optmodel.vTotalEleTradeCost, optmodel.vTotalEleTradeProfit,
                 optmodel.vTotalHydTradeCost, optmodel.vTotalHydTradeProfit, optmodel.vTotalElePeakCost, optmodel.vTotalHydPeakCost]

    ed_vars = [optmodel.vENS]

    # Set bounds for each variable
    # Objective function
    for var in cost_vars:
        var.setlb(std_lower_bound)
        var.setub(std_upper_bound)

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
            optmodel.vEleTotalCharge2ndBlock[idx].setub(model.Par['pEleMaxCharge2ndBlock'][idx[-1]][idx[:3]])
        elif idx[-1] in model.hg:
            optmodel.vEleTotalCharge[idx].setub(model.Par['pHydMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vEleTotalCharge2ndBlock[idx].setub(model.Par['pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]])

    for idx in model.psnegs:
        optmodel.vEleEnergyInflows[idx].setlb(model.Par['pEleMinInflows'][idx[-1]][idx[:3]])
        optmodel.vEleEnergyInflows[idx].setub(model.Par['pEleMaxInflows'][idx[-1]][idx[:3]])
        optmodel.vEleEnergyOutflows[idx].setlb(model.Par['pEleMinOutflows'][idx[-1]][idx[:3]])
        optmodel.vEleEnergyOutflows[idx].setub(model.Par['pEleMaxOutflows'][idx[-1]][idx[:3]])
        optmodel.vEleInventory[idx].setlb(model.Par['pEleMinStorage'][idx[-1]][idx[:3]] * 1e3 * model.factor1)
        optmodel.vEleInventory[idx].setub(model.Par['pEleMaxStorage'][idx[-1]][idx[:3]] * 1e3 * model.factor1)

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
        if idx in model.hg:
            optmodel.vHydTotalCharge[idx].setub(model.Par['pHydMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vHydTotalCharge2ndBlock[idx].setub(model.Par['pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]])
        elif idx in model.eg:
            optmodel.vHydTotalCharge[idx].setub(model.Par['pEleMaxCharge'][idx[-1]][idx[:3]])
            optmodel.vHydTotalCharge2ndBlock[idx].setub(model.Par['pEleMaxCharge2ndBlock'][idx[-1]][idx[:3]])

    for idx in model.psnhgs:
        optmodel.vHydEnergyInflows[idx].setlb(model.Par['pHydMinInflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyInflows[idx].setub(model.Par['pHydMaxInflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyOutflows[idx].setlb(model.Par['pHydMinOutflows'][idx[-1]][idx[:3]])
        optmodel.vHydEnergyOutflows[idx].setub(model.Par['pHydMaxOutflows'][idx[-1]][idx[:3]])
        optmodel.vHydInventory[idx].setlb(model.Par['pHydMinStorage'][idx[-1]][idx[:3]])
        optmodel.vHydInventory[idx].setub(model.Par['pHydMaxStorage'][idx[-1]][idx[:3]])

    for idx in model.psnhpa:
        if model.Par['pOptIndBinSingleNode'] == 0:
            optmodel.vHydNetFlow[idx].setlb(-model.Par['pHydNetTTCBck' ][idx[-3:]])
            optmodel.vHydNetFlow[idx].setub( model.Par['pHydNetTTC'    ][idx[-3:]])
        else:
            optmodel.vHydNetFlow[idx].setlb(std_lower_bound)
            optmodel.vHydNetFlow[idx].setub(std_upper_bound)

    print('--- Setting the bounds for the variables:                              {} seconds'.format(round(time.time() - StartTime)))

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
            if model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] >= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MinStorage'][idx[-1]][idx[:(len(idx)-2)]+(model.n.last(),)] and model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] <= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxStorage'][idx[-1]][idx[:(len(idx)-2)]+(model.n.last(),)]:
                optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx[:(len(idx)-2)]+(model.n.last(),)+(idx[-1],)].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                nFixedVariables += 1
        # fixing the ESS inventory at the end of the following pCycleTimeStep (daily, weekly, monthly), i.e., for daily ESS is fixed at the end of the week, for weekly/monthly ESS is fixed at the end of the year
            if model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] >= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MinStorage'][idx[-1]][idx[:(len(idx)-1)]]                   and model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]] <= model.Par[f'p{model.EnergyPrefix[idx[-1]]}MaxStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Hourly' and model.n.ord(idx[-2]) % int(24/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Daily' and model.n.ord(idx[-2]) % int(168/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Weekly' and model.n.ord(idx[-2]) % int(8736/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
                    nFixedVariables += 1
                if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenStorageType'][idx[-1]] == 'Monthly' and model.n.ord(idx[-2]) % int(8736/model.Par['pParTimeStep']) == 0:
                    optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}Inventory')[idx].fix(model.Par[f'p{model.EnergyPrefix[idx[-1]]}InitialInventory'][idx[-1]][idx[:(len(idx)-1)]])
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
            optmodel.__getattribute__('vEleNetTheta')[p,sc,n,model.ndrf.first()].fix(0.0)
            nFixedVariables += 1

    # fixing the ENS in nodes with no electricity and hydrogen demand in market
    for idx in model.psned:
        if model.Par[f'pVarMaxDemand'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'vENS')[idx].fix(0.0)
            nFixedVariables += 1
    for idx in model.psnhd:
        if model.Par[f'pVarMaxDemand'][idx[-1]][idx[:(len(idx)-1)]] == 0.0:
            optmodel.__getattribute__(f'vHNS')[idx].fix(0.0)
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
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTimeZero'  ][idx[-1]] > 0 and model.n.ord(n) <= max(0,min(model.n.ord(n),(model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTime'  ][idx[-1]]-model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenUpTimeZero'  ][idx[-1]]))):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].fix(1)
            nFixedVariables += 1
        if model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTimeZero'][idx[-1]] > 0 and model.n.ord(n) <= max(0,min(model.n.ord(n),(model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTime'][idx[-1]]-model.Par[f'p{model.EnergyPrefix[idx[-1]]}GenDownTimeZero'][idx[-1]]))):
            optmodel.__getattribute__(f'v{model.EnergyPrefix[idx[-1]]}GenCommitment')[idx].fix(0)
            nFixedVariables += 1

    # fixing electricity buys in hours when electricity cost is equal o greater than 1000
    for idx in model.psner + model.psnhr:
        if model.Par['pVarEnergyCost'][idx[-1]][idx[:(len(idx)-1)]] >= 1000.0:
            optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}Buy')[idx].fix(0.0)
            nFixedVariables += 1
        if model.Par['pVarEnergyPrice'][idx[-1]][idx[:(len(idx)-1)]] <= 0:
            optmodel.__getattribute__(f'v{model.RetailPrefix[idx[-1]]}Sell')[idx].fix(0.0)
            nFixedVariables += 1

    print('--- Fixing the variables:                                              {} seconds'.format(round(time.time() - StartTime)))

    # detecting infeasibility: total min ESS output greater than total inflows, total max ESS charge lower than total outflows
    for es in model.egs:
        if sum(model.Par['pEleMinPower'][es][idx] for idx in model.psn) - sum(model.Par[f'pEleMaxInflows'][es][idx] for idx in model.psn) > 0.0:
            print('### Total minimum output greater than total inflows for Electricity ESS unit ', es)
            assert(0==1)
        if sum(model.Par['pEleMaxCharge'][es][idx] for idx in model.psn) - sum(model.Par[f'pEleMaxOutflows'][es][idx] for idx in model.psn) < 0.0:
            print('### Total maximum charge lower than total outflows for Electricity ESS unit ', es)
            assert(0==1)

    for es in model.hgs:
        if sum(model.Par['pHydMinPower'][es][idx] for idx in model.psn) - sum(model.Par[f'pHydMaxInflows'][es][idx] for idx in model.psn) > 0.0:
            print('### Total minimum output greater than total inflows for Hydrogen ESS unit ', es)
            assert(0==1)
        if sum(model.Par['pHydMaxCharge'][es][idx] for idx in model.psn) - sum(model.Par[f'pHydMaxOutflows'][es][idx] for idx in model.psn) < 0.0:
            print('### Total maximum charge lower than total outflows for Hydrogen ESS unit ', es)
            assert(0==1)

    # detecting inventory infeasibility
    for idx in model.psnegs:
        if model.Par['pEleMaxCharge'][idx[-1]][idx[:(len(idx)-1)]] + model.Par[f'pEleMaxPower'][idx[-1]][idx[:(len(idx)-1)]] > 0.0:
            if model.n.ord(idx[-2]) == model.Par['pEleCycleTimeStep'][idx[-1]]:
                if model.Par[f'pEleInitialInventory'][idx[-1]][idx[:(len(idx)-1)]] + sum(model.Par['pDuration'][idx[:(len(idx)-2)]+(n2,)] * (model.Par[f'pEleMaxInflows'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] - model.Par[f'pEleMinPower'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] + model.Par['pEleGenEfficiency'][idx[-1]] * model.Par[f'pEleMaxCharge'][idx[-1]][idx[:(len(idx)-2)]+(n2,)]) for n2 in list(model.n2)[model.n.ord(idx[-2]) - model.Par['pEleCycleTimeStep'][idx[-1]]:model.n.ord(idx[-2])]) < model.Par[f'pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    print('### Inventory equation violation ', idx)
                    assert(0==1)
            elif model.n.ord(idx[-2]) > model.Par['pEleCycleTimeStep'][idx[-1]]:
                if model.Par['pEleMaxStorage'][idx[-1]][idx[:(len(idx)-1)]] + sum(model.Par['pDuration'][idx[:(len(idx)-2)]+(n2,)] * (model.Par[f'pEleMaxInflows'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] - model.Par[f'pEleMinPower'][idx[-1]][idx[:(len(idx)-2)]+(n2,)] + model.Par['pEleGenEfficiency'][idx[-1]] * model.Par[f'pEleMaxCharge'][idx[-1]][idx[:(len(idx)-2)]+(n2,)]) for n2 in list(model.n2)[model.n.ord(idx[-2]) - model.Par['pEleCycleTimeStep'][idx[-1]]:model.n.ord(idx[-2])]) < model.Par[f'pEleMinStorage'][idx[-1]][idx[:(len(idx)-1)]]:
                    print('### Inventory equation violation ', idx)
                    assert(0==1)

    print('--- Checking infeasibility:                                            {} seconds'.format(round(time.time() - StartTime)))

    # # Fixing the shut down in the first 8 hours of every day
    # for idx in model.psnegt:
    #     if model.Par['pEleGenCommitment'][idx[-1]] != 0 and model.n.ord(idx[-2]) % 24 < 10 and idx[-1] in model.hz:
    #         optmodel.__getattribute__(f'vGenShutDown')[idx].fix(0.0)
    #         optmodel.__getattribute__(f'vHydCommitment')[idx].fix(1.0)
    #         nFixedVariables += 2

    model.nFixedVariables = Param(initialize=round(nFixedVariables), within=NonNegativeIntegers, doc='Number of fixed variables')

    return optmodel
