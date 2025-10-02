# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import csv
import os
import time
import datetime
import altair as alt
import numpy as np
import pandas as pd
# import ausankey as sky
import matplotlib.pyplot as plt
# import altair_saver
from collections import defaultdict
from pyomo.environ import Var, Param, Constraint
try:
    import ausankey as sky
except Exception:
    sky = None

def saving_rawdata(DirName, CaseName, SolverName, model, optmodel):
    """
    Save raw optimization model data to CSV files.

    This function iterates through all active variables, parameters, and constraints
    in the optimization model and saves their data to separate CSV files.

    - Variables are saved with their values, lower bounds, and upper bounds.
    - Parameters are saved with their values.
    - Constraints are saved with their dual values.

    Args:
        DirName (str): The directory where the result files will be saved.
        CaseName (str): The name of the case, used for subdirectory and file naming.
        SolverName (str): The name of the solver used.
        model: The optimization model object.
        optmodel: The concrete optimization model instance.

    Returns:
        model: The original optimization model object.
    """
    _path = os.path.join(DirName, CaseName)
    StartTime = time.time()

    for var in optmodel.component_objects(Var, active=True):
        with open(_path+'/oM_Result_'+var.name+'_'+CaseName+'.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Index', 'Value', 'Lower Bound', 'Upper Bound'])
            var_object = getattr(optmodel, str(var))
            for index in var_object:
                writer.writerow([str(var), index, var_object[index].value, str(var_object[index].lb), str(var_object[index].ub)])

    # Extract and write parameters from the case
    for par in optmodel.component_objects(Param):
        with open(_path+'/oM_Result_'+par.name+'_'+CaseName+'.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Index', 'Value'])
            par_object = getattr(optmodel, str(par))
            if par_object.is_indexed():
                for index in par_object:
                    if (isinstance(index, tuple) and par_object.mutable == False) or par_object.mutable == False:
                        writer.writerow([str(par), index, par_object[index]])
                    else:
                        writer.writerow([str(par), index, par_object[index].value])
            else:
                writer.writerow        ([str(par), 'NA',  par_object.value])

    # Extract and write dual variables
    for con in optmodel.component_objects(Constraint, active=True):
        with open(_path+'/oM_Result_'+con.name+'_'+CaseName+'.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Index', 'Value', 'Lower Bound', 'Upper Bound'])
            con_object = getattr(optmodel, str(con))
            if con.is_indexed():
                for index in con_object:
                    writer.writerow([str(con), index, model.dual[con_object[index]], str(con_object[index].lb), str(con_object[index].ub)])

    SavingDataTime = time.time() - StartTime
    print('Output variable to CSV file                     ... ', round(SavingDataTime), 's')

    return model

def saving_results(DirName, CaseName, Date, model, optmodel):
    """
    Save processed optimization results to CSV files and generate plots.

    This function processes the results from the optimization model to generate
    a series of CSV files and Altair plots for analysis. It covers:

    - Total costs (hourly and general)
    - Electricity balance (generation, consumption, flows)
    - Net and original electricity demand
    - State of energy for storage systems
    - Fixed availability of assets
    - A summary of all key output metrics

    It also generates Sankey diagrams and duration curves for various metrics.

    Args:
        DirName (str): The directory where the result files will be saved.
        CaseName (str): The name of the case, used for subdirectory and file naming.
        Date (str or datetime): The starting date for the results, used to calculate
                                time-series data.
        model: The optimization model object.
        optmodel: The concrete optimization model instance.

    Returns:
        model: The original optimization model object.
    """
    # %% outputting the results
    # make a condition if Date is a string
    if isinstance(Date, str):
        Date = datetime.datetime.strptime(Date, "%Y-%m-%d %H:%M:%S")

    # splitting the Date into year, month, and day
    # year = Date.year
    # month = Date.month
    # day = Date.day
    # hour = Date.hour
    # minute = Date.minute

    hour_of_year = f't{((Date.timetuple().tm_yday-1) * 24 + Date.timetuple().tm_hour):04d}'

    _path = os.path.join(DirName, CaseName)
    StartTime = time.time()
    print('Objective function value                  ', model.eTotalSCost.expr())

    if sum(model.Par['pEleDemFlexible'][ed] for ed in model.ed) != 0.0:
        # saving the variable electricity demand and vEleDemand
        Output_VarMaxDemand = pd.Series(data=[model.Par['pVarMaxDemand'][ed][p,sc,n] for p,sc,n,ed in model.psned], index=pd.Index(model.psned)).to_frame(name='KWh').reset_index()
        Output_vEleDemand   = pd.Series(data=[optmodel.vEleDemand[p,sc,n,ed]()       for p,sc,n,ed in model.psned], index=pd.Index(model.psned)).to_frame(name='KWh').reset_index()
        Output_VarMaxDemand['Type'] = 'BaseDemand'
        Output_vEleDemand  ['Type'] = 'ShiftedDemand'
        # concatenate the results
        Output_vDemand = pd.concat([Output_VarMaxDemand, Output_vEleDemand], axis=0).set_index(['level_0', 'level_1', 'level_2', 'level_3', 'Type'], inplace=False)
        Output_vDemand['Date'] = Output_vDemand.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
        Output_vDemand = Output_vDemand.reset_index().rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Demand'}, inplace=False)
        Output_vDemand.to_csv(_path+'/oM_Result_00_rElectricityDemand_'+CaseName+'.csv', index=False, sep=',')

    # Define the cost types and corresponding attribute names in a dictionary
    cost_components = {
        'Electricity Market Cost'     : 'vTotalEleMCost',
        'Electricity Generation Cost' : 'vTotalEleGCost',
        'Electricity Emission Cost'   : 'vTotalECost',
        'Electricity Consumption Cost': 'vTotalEleCCost',
        'Electricity Reliability Cost': 'vTotalEleRCost',
        'Hydrogen    Market Cost'     : 'vTotalHydMCost',
        'Hydrogen    Generation Cost' : 'vTotalHydGCost',
        'Hydrogen    Consumption Cost': 'vTotalHydCCost',
        'Hydrogen    Reliability Cost': 'vTotalHydRCost'
    }

    # Initialize a dictionary to store each output DataFrame
    output_results = {}

    # Iterate through each component, calculate the result and store in the dictionary
    for name, attr in cost_components.items():
        output_results[name] = pd.Series(
            data=[getattr(optmodel, attr)[p,sc,n]() * model.Par['pDuration'][p,sc,n] for p,sc,n in model.psn],
            index=pd.Index(model.psn)
        ).to_frame(name=name)

    # Concatenate all results into a single DataFrame and reshape
    OutputResults = pd.concat(output_results.values(), axis=1).stack().to_frame(name='EUR')

    # select the third level of the index and create a new column date using the Date as a initial date with format YYYY-MM-DD HH:MM:SS
    OutputResults['Date'] = OutputResults.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')

    Output_TotalCost = OutputResults.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Component', 'Date'], axis=0).reset_index().rename(columns={0: 'EUR'}, inplace=False)
    Output_TotalCost.to_csv(_path+'/oM_Result_01_rTotalCost_Hourly_'+CaseName+'.csv', index=False, sep=',')
    model.Output_TotalCost = Output_TotalCost

    OutputTotalCost1 = Output_TotalCost.pivot_table(index=['Period', 'Scenario', 'Component'], values='EUR', aggfunc='sum').reset_index()
    OutputTotalCost2 = pd.Series(data=[optmodel.vTotalElePeakCost[idx]() for idx in model.ps], index=pd.Index(model.ps)).to_frame(name='EUR').reset_index()
    OutputTotalCost2['Component'] = 'Electricity Peak Cost'
    OutputTotalCost2 = OutputTotalCost2.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'Component': 'Component', 0: 'EUR'}, inplace=False)

    OutputTotalCost = pd.concat([OutputTotalCost1, OutputTotalCost2], axis=0)
    OutputTotalCost.to_csv(_path+'/oM_Result_01_rTotalCost_General_'+CaseName+'.csv', index=False, sep=',')

    # %% outputting the electrical energy balance
    #%%  Power balance per period, scenario, and load level
    # incoming and outgoing lines (lin) (lout)
    lin   = defaultdict(list)
    lout  = defaultdict(list)
    for ni,nf,cc in model.ela:
        lin  [nf].append((ni,cc))
        lout [ni].append((nf,cc))

    hin   = defaultdict(list)
    hout  = defaultdict(list)
    for ni,nf,cc in model.hpa:
        hin  [nf].append((ni,cc))
        hout [ni].append((nf,cc))

    sPNND   = [(p,sc,n,nd)    for p,sc,n,nd    in model.psn*model.nd                      ]
    sPNNDGT = [(p,sc,n,nd,gt) for p,sc,n,nd,gt in sPNND*model.gt                          ]
    # sPNNDEG = [(p,sc,n,nd,eg) for p,sc,n,nd,eg in sPNND*model.eg if (nd,eg ) in model.n2eg]
    # sPNNDED = [(p,sc,n,nd,ed) for p,sc,n,nd,ed in sPNND*model.ed if (nd, ed) in model.n2ed]
    # sPNNDER = [(p,sc,n,nd,er) for p,sc,n,nd,er in sPNND*model.er if (nd, er) in model.n2er]

    OutputResults1     = pd.Series(data=[ sum(optmodel.vEleTotalOutput          [p,sc,n,eg      ]() * model.Par['pDuration'][p,sc,n] for eg  in model.eg  if (nd,eg ) in model.n2eg and (gt,eg ) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='GenerationEle'     ).reset_index().pivot_table(index=['level_0','level_1','level_2','level_3'], columns='level_4', values='GenerationEle'     , aggfunc='sum')
    # OutputResults1     = pd.Series(data=[ sum(optmodel.vEleTotalOutput          [p,sc,n,eg      ]() * model.Par['pDuration'][p,sc,n] for eg  in model.eg  if (nd,eg ) in model.n2eg and (gt,eg ) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='GenerationEle'     ).reset_index().groupby(['level_0','level_1','level_2','level_3'])[['GenerationEle']].sum().reset_index().rename(columns={'GenerationEle': 'GenerationEle'})
    OutputResults2     = pd.Series(data=[-sum(optmodel.vEleTotalCharge          [p,sc,n,egs     ]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='ConsumptionEle'    ).reset_index().pivot_table(index=['level_0','level_1','level_2','level_3'], columns='level_4', values='ConsumptionEle'    , aggfunc='sum')
    OutputResults3     = pd.Series(data=[-sum(optmodel.vEleTotalCharge          [p,sc,n,e2h     ]() * model.Par['pDuration'][p,sc,n] for e2h in model.e2h if (nd,e2h) in model.n2hg and (gt,e2h) in model.t2hg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='ConsumptionEle2Hyd').reset_index().pivot_table(index=['level_0','level_1','level_2','level_3'], columns='level_4', values='ConsumptionEle2Hyd', aggfunc='sum')
    OutputResults4     = pd.Series(data=[ sum(optmodel.vENS                     [p,sc,n,ed      ]() * model.Par['pDuration'][p,sc,n] for ed  in model.ed  if (nd,ed ) in model.n2ed                           ) for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ENS'               )
    OutputResults5     = pd.Series(data=[-sum(optmodel.vEleDemand               [p,sc,n,ed      ]() * model.Par['pDuration'][p,sc,n] for ed  in model.ed  if (nd,ed ) in model.n2ed                           ) for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ElectricityDemand' )
    OutputResults6     = pd.Series(data=[ sum(optmodel.vEleBuy                  [p,sc,n,er      ]() * model.Par['pDuration'][p,sc,n] for er  in model.er  if (nd,er ) in model.n2er                           ) for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ElectricityBuy'    )
    OutputResults7     = pd.Series(data=[-sum(optmodel.vEleSell                 [p,sc,n,er      ]() * model.Par['pDuration'][p,sc,n] for er  in model.er  if (nd,er ) in model.n2er                           ) for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ElectricitySell'   )
    OutputResults8     = pd.Series(data=[-sum(optmodel.vEleNetFlow              [p,sc,n,nd,nf,cc]() * model.Par['pDuration'][p,sc,n] for (nf,cc) in lout [nd])                                            for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='PowerFlowOut'      )
    OutputResults9     = pd.Series(data=[ sum(optmodel.vEleNetFlow              [p,sc,n,ni,nd,cc]() * model.Par['pDuration'][p,sc,n] for (ni,cc) in lin  [nd])                                            for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='PowerFlowIn'       )
    OutputResults  = pd.concat([OutputResults1, OutputResults2, OutputResults3, OutputResults4, OutputResults5, OutputResults6, OutputResults7, OutputResults8, OutputResults9], axis=1).stack().to_frame(name='MWh')
    # set the index names
    OutputResults.index.names = ['Period', 'Scenario', 'LoadLevel', 'Node', 'Component']
    OutputResults = OutputResults.groupby(['Period', 'Scenario', 'LoadLevel', 'Node', 'Component'])[['MWh']].sum()

    # select the third level of the index and create a new column date using the Date as an initial date
    OutputResults['Date'] = OutputResults.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')

    Output_EleBalance = OutputResults.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Node', 'Component', 'Date'], axis=0).reset_index().rename(columns={0: 'MWh'}, inplace=False)
    # scaling the results to KWh
    Output_EleBalance['KWh'] = (1/model.factor1) * Output_EleBalance['MWh']
    Output_EleBalance.to_csv(_path+'/oM_Result_02_rElectricityBalance_'+CaseName+'.csv', index=False, sep=',')
    model.Output_EleBalance = Output_EleBalance

    # removing the component 'PowerFlowOut' and 'PowerFlowIn' from the Output_EleBalance
    Output_EleBalance = Output_EleBalance[~Output_EleBalance['Component'].isin(['PowerFlowOut', 'PowerFlowIn', 'Electrolyzer', 'H2ESS'])]
    # chart for the electricity balance using Altair and bars
    # Base chart for KWh with the primary y-axis
    kwh_chart = alt.Chart(Output_EleBalance).mark_bar().encode(
        # x='Date:T',
        x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
        y=alt.Y('sum(KWh):Q', axis=alt.Axis(title='KWh')),
        color='Component:N'
    ).properties(
        width=800,
        height=400
    ).interactive()

    kwh_chart.save(_path + '/oM_Plot_rElectricityBalance_' + CaseName + '.html', embed_options={'renderer':'svg'})
    ##kwh_chart.save(_path + '/oM_Plot_rElectricityBalance_' + CaseName + '.png')

    print('Outputting the electrical energy balance ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # net demand by filtering Solar-PV, BESS, and ElectricityDemand in Output_EleBalance, column Component
    Output_NetDemand = Output_EleBalance[Output_EleBalance['Component'].isin(['BESS', 'Solar-PV', 'EV', 'ElectricityDemand'])]
    # aggregate the columns 'Period', 'Scenario', 'LoadLevel', 'Date', 'MWh' and 'KWh'
    Output_NetDemand = Output_NetDemand.groupby(['Period', 'Scenario', 'LoadLevel', 'Date'])[['MWh', 'KWh']].sum().reset_index()
    # changing the sign of the values in the column 'MWh' and 'KWh'
    Output_NetDemand['MWh'] = Output_NetDemand['MWh'].apply(lambda x: x)
    Output_NetDemand['KWh'] = Output_NetDemand['KWh'].apply(lambda x: x)
    # save the results to a csv file
    Output_NetDemand.to_csv(_path+'/oM_Result_03_rElectricityNetDemand_'+CaseName+'.csv', index=False, sep=',')

    print('Outputting the electrical net demand     ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    model.Output_NetDemand = Output_NetDemand
    Output_NetDemand['Type'] ='NetDemand'
    Output_OrgDemand = Output_EleBalance[Output_EleBalance['Component'].isin(['ElectricityDemand'])]
    Output_OrgDemand = Output_OrgDemand.groupby(['Period', 'Scenario', 'LoadLevel', 'Date'])[['MWh', 'KWh']].sum().reset_index()
    # changing the sign of the values in the column 'MWh' and 'KWh'
    Output_OrgDemand['MWh'] = Output_OrgDemand['MWh'].apply(lambda x: x)
    Output_OrgDemand['KWh'] = Output_OrgDemand['KWh'].apply(lambda x: x)
    Output_OrgDemand['Type'] ='OrgDemand'
    # series of the electricity cost
    Output_EleCost = pd.Series(data=[((model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetelcertifikat'][er] + model.Par['pEleRetpaslag'][er]) * (1+model.Par['pEleRetmoms'][er]) + model.Par['pEleRetnetavgift'][er]) for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    Output_EleCost = Output_EleCost.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Component'}, inplace=False).set_index(['Period', 'Scenario', 'LoadLevel', 'Component'], inplace=False)
    # select the third level of the index and create a new column date using the Date as a initial date
    Output_EleCost['Date'] = Output_EleCost.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    Output_EleCost = Output_EleCost.reset_index().groupby(['Period', 'Scenario', 'LoadLevel', 'Date'])[['EUR/KWh']].sum().reset_index()
    Output_EleCost['Type'] ='ElectricityCost'

    # merge the results of the original demand with the net demand and electricity cost
    Output_Demand = pd.concat([Output_NetDemand, Output_OrgDemand], axis=0)
    # save the results to a csv file
    Output_Demand.to_csv(_path+'/oM_Result_04_rAllElectricityDemand_'+CaseName+'.csv', index=False, sep=',')
    model.Output_Demand = Output_Demand

    print('Outputting the electrical all demand     ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Base chart for KWh with the primary y-axis
    kwh_chart = alt.Chart(Output_Demand).mark_line(color='blue', point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        # x='Date:T',
        x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
        y=alt.Y('KWh:Q', axis=alt.Axis(title='KWh')),
        color='Type:N'
    )

    # Layered chart for EUR/KWh with a secondary y-axis and dashed line style
    eur_chart = alt.Chart(Output_EleCost).mark_line(color='orange', strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        # x='Date:T',
        x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
        # y=alt.Y('EUR/KWh:Q', axis=alt.Axis(title='SEK/KWh', orient='right'), scale=alt.Scale(domain=[1, 1.5])),
        y=alt.Y('EUR/KWh:Q', axis=alt.Axis(title='SEK/KWh', orient='right')),
        color='Type:N'
    )

    # Combine the two charts
    chart1 = alt.layer(kwh_chart, eur_chart).resolve_scale(
        y='independent'  # Ensures each chart has its own y-axis
    ).properties(
        width=800,
        height=400
    ).interactive()

    # Save the chart to an HTML file
    chart1.save(_path + '/oM_Plot_rEleDemand_' + CaseName + '.html', embed_options={'renderer':'svg'})
    # Save the chart to a PNG file
    #chart.save(_path + '/oM_Plot_rElectricityDemand_' + CaseName + '.png')
    if sum(model.Par['pEleDemFlexible'][ed] for ed in model.ed) != 0.0:
        vDemand_chart = alt.Chart(Output_vDemand).mark_line(color='blue', point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
            # x='Date:T',
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
            y=alt.Y('KWh:Q', axis=alt.Axis(title='KWh')),
            color='Type:N'
        )

        # Combine the two charts
        chart2 = alt.layer(vDemand_chart, eur_chart).resolve_scale(
            y='independent'  # Ensures each chart has its own y-axis
        ).properties(
            width=800,
            height=400
        ).interactive()

        # Save the chart to an HTML file
        chart2.save(_path + '/oM_Plot_rEleFlexDemand_' + CaseName + '.html', embed_options={'renderer':'svg'})

    # %% outputting the state of charge of the battery energy storage system
    #%%  State of charge of the battery energy storage system per period, scenario, and load level
    sPSNEGS = [(p, sc, n, egs) for p, sc, n, egs in model.ps * model.negs if (p, egs) in model.pegs]
    if sPSNEGS:
        OutputResults1     = pd.Series(data=[ optmodel.vEleInventory[p,sc,n,egs]() for p,sc,n,egs in sPSNEGS], index=pd.Index(sPSNEGS)).to_frame(name='SOC').reset_index().pivot_table(index=['level_0','level_1','level_2'], columns='level_3', values='SOC', aggfunc='sum')
        OutputResults1['Date'] = OutputResults1.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
        Output_EleSOE = OutputResults1.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Date'], axis=0).stack().reset_index().rename(columns={'level_3': 'Component', 0: 'SOE'}, inplace=False)
        Output_EleSOE['SOE'] *= (1/model.factor1)
        Output_EleSOE.to_csv(_path+'/oM_Result_05_rEleStateOfEnergy_'+CaseName+'.csv', index=False, sep=',')

        print('Outputting the electrical state of energy... ', round(time.time() - StartTime), 's')
        StartTime = time.time()

        # plot
        # Base chart for SOC with the primary y-axis and dashed line style
        ele_soe_chart = alt.Chart(Output_EleSOE).mark_line(color='green', strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
            y=alt.Y('SOE:Q', axis=alt.Axis(title='SOE')),
            color = 'Component:N'
        )

    if len(model.egv):
        # Base chart of VarFixedAvailability with the primary y-axis
        Output_FixedAvailability = model.Par['pVarFixedAvailability'].loc[model.psn]
        Output_FixedAvailability['Date'] = Output_FixedAvailability.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
        Output_FixedAvailability = Output_FixedAvailability.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Date'], axis=0).stack().reset_index().rename(columns={'level_4': 'Component', 0: 'FixedAvailability'}, inplace=False)
        Output_FixedAvailability.to_csv(_path+'/oM_Result_06_rFixedAvailability_'+CaseName+'.csv', index=False, sep=',')

        print('Outputting the electrical fixed available... ', round(time.time() - StartTime), 's')
        StartTime = time.time()

        # filter component 'EV_01' and 'EV_02' from the Output_FixedAvailability
        Output_FixedAvailability = Output_FixedAvailability[Output_FixedAvailability['Component'].isin(['EV_01'])]
        # Base chart for FixedAvailability with the primary y-axis and dashed line style
        ele_fAv_chart = alt.Chart(Output_FixedAvailability).mark_point(color='red').encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%A, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
            y=alt.Y('FixedAvailability:Q', axis=alt.Axis(title='FixedAvailability', orient='right')),
        )

        chart = alt.layer(ele_soe_chart, ele_fAv_chart).resolve_scale(
            y='independent'  # Ensures each chart has its own y-axis
        ).properties(
            width=800,
            height=400
        ).interactive()

        # Save the chart to an HTML file
        chart.save(_path + '/oM_Plot_rEleStateOfEnergy_' + CaseName + '.html', embed_options={'renderer':'svg'})
        # Save the chart to a PNG file
        #chart.save(_path + '/oM_Plot_rEleStateOfEnergy_' + CaseName + '.png')

    # Creating dataframe with outputs like electricity buy, electricity sell, total production, total consumption, Inventory, energy outflows, VarStartUp, VarShutDown, FixedAvailability, EleDemand, ElectricityCost, ElectricityPrice
    # series of electricity production
    OutputResults1 = pd.Series(data=[ sum(optmodel.vEleTotalOutput[p,sc,n,eg ]() * model.Par['pDuration'][p,sc,n] for eg  in model.eg  if (nd,eg ) in model.n2eg and (gt,eg ) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleGeneration' ).reset_index()
    OutputResults1['Component'] = 'Production/Discharge [KWh]'
    OutputResults1['EleGeneration'] *= (1/model.factor1)
    OutputResults1 = OutputResults1.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults1 = OutputResults1.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleGeneration', aggfunc='sum')
    # series of electricity consumption
    OutputResults2 = pd.Series(data=[-sum(optmodel.vEleTotalCharge[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleConsumption').reset_index()
    OutputResults2['Component'] = 'Consumption/Charge [KWh]'
    OutputResults2['EleConsumption'] *= (1/model.factor1)
    OutputResults2 = OutputResults2.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults2 = OutputResults2.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleConsumption', aggfunc='sum')
    # series of electricity inventory
    OutputResults3 = pd.Series(data=[ sum(optmodel.vEleInventory[p,sc,n,egs]() for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleInventory').reset_index()
    OutputResults3['Component'] = 'Inventory [KWh]'
    OutputResults3['EleInventory'] *= (1/model.factor1)
    OutputResults3 = OutputResults3.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults3 = OutputResults3.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleInventory', aggfunc='sum')
    # series of ENS
    OutputResults4 = pd.Series(data=[ sum(optmodel.vENS[p,sc,n,ed]() * model.Par['pDuration'][p,sc,n] for ed in model.ed if (nd,ed) in model.n2ed) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='ENS').reset_index()
    OutputResults4['Component'] = 'ENS [KWh]'
    OutputResults4['ENS'] *= (1/model.factor1)
    OutputResults4 = OutputResults4.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults4 = OutputResults4.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='ENS', aggfunc='sum')
    # series of energy outflows
    OutputResults5 = pd.Series(data=[-sum(optmodel.vEleEnergyOutflows[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleEnergyOutflows').reset_index()
    OutputResults5['Component'] = 'Outflows/Driving [KWh]'
    OutputResults5['EleEnergyOutflows'] *= (1/model.factor1)
    OutputResults5 = OutputResults5.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults5 = OutputResults5.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleEnergyOutflows', aggfunc='sum')
    # series of load home
    OutputResults6 = pd.Series(data=[-sum(optmodel.vEleDemand[p,sc,n,ed]() * model.Par['pDuration'][p,sc,n] for ed in model.ed if (nd,ed) in model.n2ed) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleDemand').reset_index()
    OutputResults6['Component'] = 'Load/Home [KWh]'
    OutputResults6['EleDemand'] *= (1/model.factor1)
    OutputResults6 = OutputResults6.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults6 = OutputResults6.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleDemand', aggfunc='sum')
    # series of the electricity buy
    OutputResults7 = pd.Series(data=[ sum(optmodel.vEleBuy[p,sc,n,er]() * model.Par['pDuration'][p,sc,n] for er in model.er if (nd,er) in model.n2er) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleBuy').reset_index()
    OutputResults7['Component'] = 'Electricity Buy [KWh]'
    OutputResults7['EleBuy'] *= (1/model.factor1)
    OutputResults7 = OutputResults7.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults7 = OutputResults7.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleBuy', aggfunc='sum')
    # series of the electricity sell
    OutputResults8 = pd.Series(data=[-sum(optmodel.vEleSell[p,sc,n,er]() * model.Par['pDuration'][p,sc,n] for er in model.er if (nd,er) in model.n2er) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleSell').reset_index()
    OutputResults8['Component'] = 'Electricity Sell [KWh]'
    OutputResults8['EleSell'] *= (1/model.factor1)
    OutputResults8 = OutputResults8.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults8 = OutputResults8.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleSell', aggfunc='sum')
    # series of the spot price
    OutputResults9 = pd.Series(data=[  model.Par['pVarEnergyCost' ] [er][p,sc,n] for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults9['Component'] = 'Spot Price [EUR/KWh]'
    OutputResults9 = OutputResults9.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults9 = OutputResults9.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of the electricity cost
    OutputResults10 = pd.Series(data=[((model.Par['pVarEnergyCost' ] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetelcertifikat'][er] * model.factor1 + model.Par['pEleRetpaslag'][er] * model.factor1) * (1+model.Par['pEleRetmoms'][er] * model.factor1) + model.Par['pEleRetnetavgift'][er] * model.factor1) for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults10['Component'] = 'EleCost [EUR/KWh]'
    OutputResults10['EUR/KWh'] *= (1/model.factor1)
    OutputResults10 = OutputResults10.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults10 = OutputResults10.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of the electricity price
    OutputResults11 = pd.Series(data=[  model.Par['pVarEnergyPrice'] [er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults11['Component'] = 'ElePrice [EUR/KWh]'
    OutputResults11['EUR/KWh'] *= (1/model.factor1)
    OutputResults11 = OutputResults11.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults11 = OutputResults11.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of VarStartUp
    OutputResults12 = pd.Series(data=[ sum(model.Par['pVarStartUp'][egs][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='VarStartUp').reset_index()
    OutputResults12['Component'] = 'Departure [0,1]'
    OutputResults12 = OutputResults12.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults12 = OutputResults12.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='VarStartUp', aggfunc='sum')
    # series of VarShutDown
    OutputResults13 = pd.Series(data=[ sum(model.Par['pVarShutDown'][egs][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='VarShutDown').reset_index()
    OutputResults13['Component'] = 'Arrival [0,1]'
    OutputResults13 = OutputResults13.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults13 = OutputResults13.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='VarShutDown', aggfunc='sum')
    # series of FixedAvailability
    OutputResults14 = pd.Series(data=[ sum(model.Par['pVarFixedAvailability'][egs][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='FixedAvailability').reset_index()
    OutputResults14['Component'] = 'Availability [0,1]'
    OutputResults14 = OutputResults14.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults14 = OutputResults14.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='FixedAvailability', aggfunc='sum')
    # series of spillage
    OutputResults15 = pd.Series(data=[ sum(optmodel.vEleSpillage[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleSpillage').reset_index()
    OutputResults15['Component'] = 'Spillage [KWh]'
    OutputResults15['EleSpillage'] *= (1/model.factor1)
    OutputResults15 = OutputResults15.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults15 = OutputResults15.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleSpillage', aggfunc='sum')

    if len(model.egs):
        if len(model.egv):
            OutputResults = pd.concat([OutputResults1, OutputResults2, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults12, OutputResults13, OutputResults14, OutputResults3, OutputResults5, OutputResults15, OutputResults9, OutputResults10, OutputResults11], axis=1)
        else:
            OutputResults = pd.concat([OutputResults1, OutputResults2, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults3, OutputResults15, OutputResults9, OutputResults10, OutputResults11], axis=1)
    else:
        OutputResults = pd.concat([OutputResults1, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults9, OutputResults10, OutputResults11], axis=1)
    OutputResults['Date'] = OutputResults.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    OutputResults = OutputResults.set_index('Date', append=True)
    OutputResults.index.names = [None, None, None, None]
    OutputResults.columns.names = [None, None]
    OutputResults.to_csv(_path+'/oM_Result_07_rEleOutputSummary_'+CaseName+'.csv', index=True, sep=',')

    # ---- Index & small helpers --------------------------------------------------
    I_psn = pd.MultiIndex.from_tuples(model.psn)
    idx_p = pd.Index(model.p)
    dur = {(p, sc, n): float(model.Par['pDuration'][p, sc, n]) for (p, sc, n) in model.psn}

    def has(name):
        return hasattr(optmodel, name) and len(getattr(optmodel, name)) > 0

    def re_psn(s):
        return s.reindex(I_psn, fill_value=0.0)

    def pos_guard(s):
        return s.where(s > 0.0, 1e-5)  # avoid 0-div

    # Availability (avoid nested loops over nodes)
    n2er_any = {er for (nd, er) in getattr(model, "n2er", set())}
    n2ed_any = {ed for (nd, ed) in getattr(model, "n2ed", set())}

    # ---- Totals -----------------------------------------------------------------
    def total_in():
        acc = defaultdict(float)
        if has("vEleTotalOutput"):
            for (p, sc, n, eg), var in optmodel.vEleTotalOutput.items():
                acc[(p, sc, n)] += optmodel.vEleTotalOutput[p,sc,n,eg]() * dur[(p, sc, n)]
        if has("vEleBuy"):
            for (p, sc, n, er), var in optmodel.vEleBuy.items():
                if er in n2er_any:
                    acc[(p, sc, n)] += optmodel.vEleBuy[p,sc,n,er]() * dur[(p, sc, n)]
        if has("vENS"):
            for (p, sc, n, ed), var in optmodel.vENS.items():
                if ed in n2ed_any:
                    acc[(p, sc, n)] += optmodel.vENS[p,sc,n,ed]() * dur[(p, sc, n)]
        return pos_guard(re_psn(pd.Series(acc, dtype=float)))

    def total_out():
        acc = defaultdict(float)
        if has("vEleTotalCharge"):
            for (p, sc, n, egs), var in optmodel.vEleTotalCharge.items():
                acc[(p, sc, n)] += optmodel.vEleTotalCharge[p,sc,n,egs]() * dur[(p, sc, n)]
        if has("vEleSell"):
            for (p, sc, n, er), var in optmodel.vEleSell.items():
                if er in n2er_any:
                    acc[(p, sc, n)] += optmodel.vEleSell[p,sc,n,er]() * dur[(p, sc, n)]
        if has("vEleDemand"):
            for (p, sc, n, ed), var in optmodel.vEleDemand.items():
                if ed in n2ed_any:
                    acc[(p, sc, n)] += optmodel.vEleDemand[p,sc,n,ed]() * dur[(p, sc, n)]
        return pos_guard(re_psn(pd.Series(acc, dtype=float)))

    TEI, TEO = total_in(), total_out()

    # ---- Shares In/Out (robust to missing techs) --------------------------------
    def share_gen_in(tags):
        num = defaultdict(float)
        if has("vEleTotalOutput") and hasattr(model, "egg"):
            wanted = {eg for eg in model.egg if any(t in str(eg) for t in tags)}
            if wanted:
                for (p, sc, n, eg), var in optmodel.vEleTotalOutput.items():
                    if eg in wanted:
                        num[(p, sc, n)] += optmodel.vEleTotalOutput[p,sc,n,eg]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEI).clip(lower=0.0)

    def share_market_in():
        num = defaultdict(float)
        if has("vEleBuy"):
            for (p, sc, n, er), var in optmodel.vEleBuy.items():
                num[(p, sc, n)] += optmodel.vEleBuy[p,sc,n,er]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEI).clip(lower=0.0)

    def share_ens():
        num = defaultdict(float)
        if has("vENS"):
            for (p, sc, n, ed), var in optmodel.vENS.items():
                num[(p, sc, n)] += optmodel.vENS[p,sc,n,ed]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEI).clip(lower=0.0)

    def share_to_storage(tags):
        num = defaultdict(float)
        if has("vEleTotalCharge") and hasattr(model, "egs"):
            wanted = {e for e in model.egs if any(t in str(e) for t in tags)}
            if wanted:
                for (p, sc, n, egs), var in optmodel.vEleTotalCharge.items():
                    if egs in wanted:
                        num[(p, sc, n)] += optmodel.vEleTotalCharge[p,sc,n,egs]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEO).clip(lower=0.0)

    def share_market_out():
        num = defaultdict(float)
        if has("vEleSell"):
            for (p, sc, n, er), var in optmodel.vEleSell.items():
                num[(p, sc, n)] += optmodel.vEleSell[p,sc,n,er]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEO).clip(lower=0.0)

    def share_dem_out():
        num = defaultdict(float)
        if has("vEleDemand"):
            for (p, sc, n, ed), var in optmodel.vEleDemand.items():
                num[(p, sc, n)] += optmodel.vEleDemand[p,sc,n,ed]() * dur[(p, sc, n)]
        return (re_psn(pd.Series(num, dtype=float)) / TEO).clip(lower=0.0)

    ShareGenInFV = share_gen_in(["Solar"])  # FV
    ShareGenInBESS = share_gen_in(["BESS"])
    ShareGenInEV = share_gen_in(["EV"])
    ShareMarketIn = share_market_in()
    ShareENSIn = share_ens()

    ShareGenOutBESS = share_to_storage(["BESS"])
    ShareGenOutEV = share_to_storage(["EV"])
    ShareMarketOut = share_market_out()
    ShareDemOut = share_dem_out()

    # ---- Flows (kWh at (p,sc,n)) -----------------------------------------------
    f1 = float(getattr(model, "factor1", 1.0))
    flow = lambda src, dst: (src * dst * TEI) * (1.0 / f1)

    FVtoEV = flow(ShareGenInFV, ShareGenOutEV)
    FVtoBESS = flow(ShareGenInFV, ShareGenOutBESS)
    FVtoMkt = flow(ShareGenInFV, ShareMarketOut)
    FVtoDem = flow(ShareGenInFV, ShareDemOut)

    ENStoEV = flow(ShareENSIn, ShareGenOutEV)
    ENStoBESS = flow(ShareENSIn, ShareGenOutBESS)
    ENStoDem = flow(ShareENSIn, ShareDemOut)

    BESStoEV = flow(ShareGenInBESS, ShareGenOutEV)
    BESStoMkt = flow(ShareGenInBESS, ShareMarketOut)
    BESStoDem = flow(ShareGenInBESS, ShareDemOut)

    EVtoBESS = flow(ShareGenInEV, ShareGenOutBESS)
    EVtoMkt = flow(ShareGenInEV, ShareMarketOut)
    EVtoDem = flow(ShareGenInEV, ShareDemOut)

    MkttoEV = flow(ShareMarketIn, ShareGenOutEV)
    MkttoDem = flow(ShareMarketIn, ShareDemOut)
    MkttoBESS = flow(ShareMarketIn, ShareGenOutBESS)

    # ---- Aggregate to Period (p) -----------------------------------------------
    def sum_by_p(s):
        if s.empty: return pd.Series(0.0, index=idx_p)
        g = s.to_frame("v").reset_index().groupby("level_0")["v"].sum()
        return g.reindex(idx_p, fill_value=0.0)

    flows = {
        "FV_to_EV [KWh]": FVtoEV, "FV_to_BESS [KWh]": FVtoBESS, "FV_to_Mkt [KWh]": FVtoMkt, "FV_to_Dem [KWh]": FVtoDem,
        "ENS_to_EV [KWh]": ENStoEV, "ENS_to_BESS [KWh]": ENStoBESS, "ENS_to_Dem [KWh]": ENStoDem,
        "BESS_to_EV [KWh]": BESStoEV, "BESS_to_Mkt [KWh]": BESStoMkt, "BESS_to_Dem [KWh]": BESStoDem,
        "EV_to_BESS [KWh]": EVtoBESS, "EV_to_Mkt [KWh]": EVtoMkt, "EV_to_Dem [KWh]": EVtoDem,
        "Mkt_to_EV [KWh]": MkttoEV, "Mkt_to_Dem [KWh]": MkttoDem, "Mkt_to_BESS [KWh]": MkttoBESS,
    }
    dfEnergyBalance = pd.DataFrame({"Period": idx_p})
    for name, s in flows.items():
        dfEnergyBalance[name] = sum_by_p(s).values

    # ===== Sankey: always save a figure (even if all flows are zero) =============
    ALLOWED = {"SolarPV", "Market", "EV", "ENS", "BESS", "Demand"}

    def _normalize(df):
        if "Period" not in df.columns: raise ValueError("dfEnergyBalance needs 'Period'")
        m = df.melt(id_vars="Period", var_name="Component", value_name="flow_value")
        # strip units and normalize names
        m["Component"] = m["Component"].str.replace(r"\s*\[.*\]$", "", regex=True)
        m["Component"] = (m["Component"]
                          .str.replace("FV", "SolarPV", regex=False)
                          .str.replace("Mkt", "Market", regex=False)
                          .str.replace("Dem", "Demand", regex=False))
        # extract edges
        split = m["Component"].str.extract(r"^(?P<Source>[^_]+)_to_(?P<Target>.+)$")
        m = pd.concat([m, split], axis=1).dropna(subset=["Source", "Target"])
        # keep allowed that actually appear (if any)
        present = set(m["Source"]).union(m["Target"])
        allowed_present = ALLOWED & present
        if allowed_present:
            m = m[m["Source"].isin(allowed_present) & m["Target"].isin(allowed_present)]
        return m

    def _percentify(m):
        if m.empty:
            m = m.copy()
            m["Source_%"] = 0.0;
            m["Target_%"] = 0.0
            return m
        g_src = m.groupby(["Period", "Source"])["flow_value"].transform("sum").replace(0, np.nan)
        g_tgt = m.groupby(["Period", "Target"])["flow_value"].transform("sum").replace(0, np.nan)
        m = m.assign(**{"Source_%": (m["flow_value"] / g_src * 100).fillna(0.0),
                        "Target_%": (m["flow_value"] / g_tgt * 100).fillna(0.0)})
        return m

    def save_sankey_always(dfEnergyBalance, out_dir, case_name, mode="percent", prefix="oM_Plot_rSankey"):
        os.makedirs(out_dir, exist_ok=True)
        m = _normalize(dfEnergyBalance)
        # Plot per period, always save a PNG
        for per in dfEnergyBalance["Period"]:
            d = m[m["Period"] == per]
            outfile = os.path.join(out_dir, f"{prefix}_{case_name}_{per}.png")
            if sky is None:
                # Fallback: save a placeholder
                plt.figure(figsize=(6, 4))
                plt.title(f"Case: {case_name}, Period: {per}\n(ausankey not available)")
                plt.text(0.5, 0.5, "Install 'ausankey' to draw Sankey", ha='center', va='center')
                plt.axis('off');
                plt.savefig(outfile, dpi=150, bbox_inches="tight");
                plt.close()
                print(f"Sankey placeholder saved: {outfile}")
                continue

            d = d[d["flow_value"].fillna(0) > 0]
            if d.empty:
                # Save an empty-note figure for this period
                plt.figure(figsize=(6, 4))
                plt.title(f"Case: {case_name}, Period: {per}")
                plt.text(0.5, 0.5, "No non-zero flows", ha='center', va='center')
                plt.axis('off');
                plt.savefig(outfile, dpi=150, bbox_inches="tight");
                plt.close()
                print(f"Sankey (no flows) saved: {outfile}")
                continue

            if mode == "percent":
                d = _percentify(d)
                vals1, vals2, unit = d["Source_%"], d["Target_%"], "%"
            else:
                vals1, vals2, unit = d["flow_value"], d["flow_value"], "KWh"

            sankey_data = pd.DataFrame({"Stage1": d["Source"], "Value1": vals1,
                                        "Stage2": d["Target"], "Value2": vals2})
            plt.figure(figsize=(7, 5))
            sky.sankey(sankey_data, sort="top", titles=["Source", "Target"], valign="center")
            plt.title(f"Case: {case_name}, Period: {per} ({unit})")
            plt.savefig(outfile, format="png", dpi=150, bbox_inches="tight");
            plt.close()
            print(f"Sankey saved: {outfile}")

    # --- Save CSVs & plots -------------------------------------------------------
    dfEnergyBalance.to_csv(os.path.join(_path, f"oM_Result_08_rEnergyBalance_{CaseName}.csv"), index=False)
    save_sankey_always(dfEnergyBalance, out_dir=_path, case_name=CaseName, mode="percent")

    print('Outputting the Sankey diagrams           ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Duration curve of the EV total output and the total charge
    EV_TotalOutput = pd.Series(data=[sum(optmodel.vEleTotalOutput[p,sc,n,egv]() for egv in model.egv) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EV_TotalCharge = pd.Series(data=[sum(optmodel.vEleTotalCharge[p,sc,n,egs]() for egs in model.egs) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    # make different dataframes for the EV total output and the total charge, total charge is positive and total output is negative
    EV_NetCharge = EV_TotalCharge - EV_TotalOutput
    # sort values in the dataframe from the largest to the smallest
    EV_NetCharge = EV_NetCharge.sort_values(ascending=False)
    # from series to dataframe
    EV_NetCharge = EV_NetCharge.to_frame(name='NetCharge')
    # add a column with the date
    EV_NetCharge['Date'] = EV_NetCharge.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    EV_NetCharge = EV_NetCharge.reset_index()
    # rename the columns
    EV_NetCharge = EV_NetCharge.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, inplace=False)
    # save the dataframe to a csv file
    EV_NetCharge.to_csv(_path+'/oM_Result_10_rDurationCurve_NetCharge_' + CaseName + '.csv', sep=',', header=True, index=False)
    # plot the duration curve using altair
    EV_NetCharge['Counter'] = range(len(EV_NetCharge['NetCharge']))
    chart = alt.Chart(EV_NetCharge).mark_line(point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        x=alt.X('Counter', title='Time', sort=None),
        y=alt.Y('NetCharge', title='Charge and discharge [KWh]')
    ).properties(
        title='Duration Curve of the Charge and Discharge of the EV',
        width=800,
        height=400
    )
    chart.save(_path+'/oM_Plot_rDurationCurve_NetCharge_' + CaseName + '.html')

    print('Outputting the duration curve of the EV  ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Duration curve of the Solar PV total output
    SolarPV_TotalOutput = pd.Series(data=[sum(optmodel.vEleTotalOutput[p,sc,n,egr]() for egr in model.egr) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    # sort values in the dataframe from the largest to the smallest
    SolarPV_TotalOutput = SolarPV_TotalOutput.sort_values(ascending=False)
    # from series to dataframe
    SolarPV_TotalOutput = SolarPV_TotalOutput.to_frame(name='TotalOutput')
    # add a column with the date
    SolarPV_TotalOutput['Date'] = SolarPV_TotalOutput.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    SolarPV_TotalOutput = SolarPV_TotalOutput.reset_index()
    # rename the columns
    SolarPV_TotalOutput = SolarPV_TotalOutput.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, inplace=False)
    # save the dataframe to a csv file
    SolarPV_TotalOutput.to_csv(_path+'/oM_Result_11_rDurationCurve_TotalOutput_' + CaseName + '.csv', sep=',', header=True, index=False)
    # plot the duration curve using altair
    SolarPV_TotalOutput['Counter'] = range(len(SolarPV_TotalOutput['TotalOutput']))
    chart = alt.Chart(SolarPV_TotalOutput).mark_line(point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        x=alt.X('Counter', title='Time', sort=None),
        y=alt.Y('TotalOutput', title='Total Output [KWh]')
    ).properties(
        title='Duration Curve of the Total Output of the Solar PV',
        width=800,
        height=400
    )
    chart.save(_path+'/oM_Plot_rDurationCurve_TotalOutput_' + CaseName + '.html')

    print('Outputting the duration curve of the PV  ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Duration curve of the electricity demand
    EleDemand = pd.Series(data=[sum(optmodel.vEleDemand[p,sc,n,ed]() for ed in model.ed) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    # sort values in the dataframe from the largest to the smallest
    EleDemand = EleDemand.sort_values(ascending=False)
    # from series to dataframe
    EleDemand = EleDemand.to_frame(name='Demand')
    # add a column with the date
    EleDemand['Date'] = EleDemand.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    EleDemand = EleDemand.reset_index()
    # rename the columns
    EleDemand = EleDemand.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, inplace=False)
    # save the dataframe to a csv file
    EleDemand.to_csv(_path+'/oM_Result_12_rDurationCurve_Demand_' + CaseName + '.csv', sep=',', header=True, index=False)
    # plot the duration curve using altair
    EleDemand['Counter'] = range(len(EleDemand['Demand']))
    chart = alt.Chart(EleDemand).mark_line(point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        x=alt.X('Counter', title='Time', sort=None),
        y=alt.Y('Demand', title='Demand [KWh]')
    ).properties(
        title='Duration Curve of the Demand',
        width=800,
        height=400
    )
    chart.save(_path+'/oM_Plot_rDurationCurve_Demand_' + CaseName + '.html')

    print('Outputting the duration curve of the Load... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Duration curve of the electricity bought from the market
    EleBuy = pd.Series(data=[sum(optmodel.vEleBuy[p,sc,n,er]() for er in model.er) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    # sort values in the dataframe from the largest to the smallest
    EleBuy = EleBuy.sort_values(ascending=False)
    # from series to dataframe
    EleBuy = EleBuy.to_frame(name='Buy')
    # add a column with the date
    EleBuy['Date'] = EleBuy.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    EleBuy = EleBuy.reset_index()
    # rename the columns
    EleBuy = EleBuy.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, inplace=False)
    # save the dataframe to a csv file
    EleBuy.to_csv(_path+'/oM_Result_13_rDurationCurve_EleBuy_' + CaseName + '.csv', sep=',', header=True, index=False)
    # plot the duration curve using altair
    EleBuy['Counter'] = range(len(EleBuy['Buy']))
    chart = alt.Chart(EleBuy).mark_line(point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        x=alt.X('Counter', title='Time', sort=None),
        y=alt.Y('Buy', title='Buy [KWh]')
    ).properties(
        title='Duration Curve of the Buy',
        width=800,
        height=400
    )
    chart.save(_path+'/oM_Plot_rDurationCurve_EleBuy_' + CaseName + '.html')

    print('Outputting the duration curve of the Buy ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    # Duration curve of the electricity sold to the market
    EleSell = pd.Series(data=[sum(optmodel.vEleSell[p,sc,n,er]() for er in model.er) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    # sort values in the dataframe from the largest to the smallest
    EleSell = EleSell.sort_values(ascending=False)
    # from series to dataframe
    EleSell = EleSell.to_frame(name='Sell')
    # add a column with the date
    EleSell['Date'] = EleSell.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    EleSell = EleSell.reset_index()
    # rename the columns
    EleSell = EleSell.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, inplace=False)
    # save the dataframe to a csv file
    EleSell.to_csv(_path+'/oM_Result_14_rDurationCurve_EleSell_' + CaseName + '.csv', sep=',', header=True, index=False)
    # plot the duration curve using altair
    EleSell['Counter'] = range(len(EleSell['Sell']))
    chart = alt.Chart(EleSell).mark_line(point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
        x=alt.X('Counter', title='Time', sort=None),
        y=alt.Y('Sell', title='Sell [KWh]')
    ).properties(
        title='Duration Curve of the Sell',
        width=800,
        height=400
    )
    chart.save(_path+'/oM_Plot_rDurationCurve_EleSell_' + CaseName + '.html')

    print('Outputting the duration curve of the Sell... ', round(time.time() - StartTime), 's')

    return model