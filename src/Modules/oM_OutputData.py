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
import pandas as pd
import ausankey as sky
import matplotlib.pyplot as plt
# import altair_saver
from collections import defaultdict
from pyomo.environ import Var, Param, Constraint


def saving_rawdata(DirName, CaseName, SolverName, model, optmodel):

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
    # %% outputting the results
    # make a condition if Date is a string
    if isinstance(Date, str):
        Date = datetime.datetime.strptime(Date, "%Y-%m-%d %H:%M:%S")

    # splitting the Date into year, month, and day
    year = Date.year
    month = Date.month
    day = Date.day
    hour = Date.hour
    minute = Date.minute

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
    sPNNDEG = [(p,sc,n,nd,eg) for p,sc,n,nd,eg in sPNND*model.eg if (nd,eg ) in model.n2eg]
    sPNNDED = [(p,sc,n,nd,ed) for p,sc,n,nd,ed in sPNND*model.ed if (nd, ed) in model.n2ed]
    sPNNDER = [(p,sc,n,nd,er) for p,sc,n,nd,er in sPNND*model.er if (nd, er) in model.n2er]

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


    # %% outputting the state of charge of the battery energy storage system
    TotalEnergyIn  = pd.Series(data=[sum(optmodel.vEleTotalOutput   [p,sc,n,eg ]()*model.Par['pDuration'][p,sc,n] for eg  in model.eg ) + sum((sum(optmodel.vEleBuy [p,sc,n,er]() for er in model.er if (nd,er) in model.n2er) + sum(optmodel.vENS      [p,sc,n,ed]() for ed in model.ed if (nd,ed) in model.n2ed))*model.Par['pDuration'][p,sc,n] for nd in model.nd) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn)).fillna(1e-05)
    TotalEnergyIn  = TotalEnergyIn.where(TotalEnergyIn   > 0.0, other=1e-05)
    TotalEnergyOut = pd.Series(data=[sum(optmodel.vEleTotalCharge   [p,sc,n,egs]()*model.Par['pDuration'][p,sc,n] for egs in model.egs) + sum((sum(optmodel.vEleSell[p,sc,n,er]() for er in model.er if (nd,er) in model.n2er) + sum(optmodel.vEleDemand[p,sc,n,ed]() for ed in model.ed if (nd,ed) in model.n2ed))*model.Par['pDuration'][p,sc,n] for nd in model.nd) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn)).fillna(1e-05)
    TotalEnergyOut = TotalEnergyOut.where(TotalEnergyOut > 0.0, other=1e-05)

    ShareGenIn     = pd.Series(data=[(   optmodel.vEleTotalOutput   [p,sc,n,eg ]()*model.Par['pDuration'][p,sc,n])/TotalEnergyIn [p,sc,n]  for p,sc,n,eg  in model.psneg ], index=pd.MultiIndex.from_tuples(model.psneg ))
    ShareGenIn     = ShareGenIn.where(   ShareGenIn      > 0.0, other=0.0  )
    ShareMarketIn  = pd.Series(data=[((  optmodel.vEleBuy           [p,sc,n,er ]()*model.Par['pDuration'][p,sc,n])/TotalEnergyIn [p,sc,n]) for p,sc,n,er  in model.psner ], index=pd.MultiIndex.from_tuples(model.psner ))
    ShareMarketIn  = ShareMarketIn.where(ShareMarketIn   > 0.0, other=0.0  )
    ShareENSIn     = pd.Series(data=[((  optmodel.vENS              [p,sc,n,ed ]()*model.Par['pDuration'][p,sc,n])/TotalEnergyIn [p,sc,n]) for p,sc,n,ed  in model.psned ], index=pd.MultiIndex.from_tuples(model.psned ))

    ShareGenOut    = pd.Series(data=[sum(((optmodel.vEleTotalCharge [p,sc,n,egs]()*model.Par['pDuration'][p,sc,n])/TotalEnergyOut[p,sc,n]) for egs in model.egs if egs in model.eg) for p,sc,n,nd,eg in sPNNDEG], index=pd.Index(sPNNDEG)).to_frame(name='EleSpillage').reset_index().pivot_table(index=['level_0', 'level_1', 'level_2', 'level_4'], values='EleSpillage', aggfunc='sum').reset_index().set_index(['level_0', 'level_1', 'level_2', 'level_4'])['EleSpillage']
    ShareDemOut    = pd.Series(data=[    ((optmodel.vEleDemand      [p,sc,n,ed ]()*model.Par['pDuration'][p,sc,n])/TotalEnergyOut[p,sc,n])                                          for p,sc,n,nd,ed in sPNNDED], index=pd.Index(sPNNDED)).to_frame(name='EleDemand').reset_index().pivot_table(index=['level_0', 'level_1', 'level_2', 'level_4'], values='EleDemand', aggfunc='sum').reset_index().set_index(['level_0', 'level_1', 'level_2', 'level_4'])['EleDemand']
    ShareMarketOut = pd.Series(data=[    ((optmodel.vEleSell        [p,sc,n,er ]()*model.Par['pDuration'][p,sc,n])/TotalEnergyOut[p,sc,n])                                          for p,sc,n,nd,er in sPNNDER], index=pd.Index(sPNNDER)).to_frame(name='EleSell').reset_index().pivot_table(index=['level_0', 'level_1', 'level_2', 'level_4'], values='EleSell', aggfunc='sum').reset_index().set_index(['level_0', 'level_1', 'level_2', 'level_4'])['EleSell']

    def get_series_with_fallback(dataframe, label):
        if label in dataframe.index.get_level_values(-1):  # Adjust -1 for correct index level
            return dataframe.loc[:, :, :, label]
        else:
            # Create a zero-filled series with the same MultiIndex structure but only for the specified level
            zero_filled = dataframe.loc[:, :, :, dataframe.index.levels[-1][0]].copy() * 0  # Copy the structure
            zero_filled.index = zero_filled.index.set_levels([label if level == dataframe.index.levels[-1][0] else level
                                                              for level in zero_filled.index.levels[-1]], level=-1)
            return zero_filled

    ShareGenInBESS  = sum(get_series_with_fallback(ShareGenIn, label) for label in [i for i in model.egg if "BESS" in i])
    ShareGenInFV    = sum(get_series_with_fallback(ShareGenIn, label) for label in [i for i in model.egg if "Solar" in i])
    ShareGenInEV    = sum(get_series_with_fallback(ShareGenIn, label) for label in [i for i in model.egg if "EV" in i])
    ShareENSIn      = sum(get_series_with_fallback(ShareENSIn, label) for label in [i for i in model.edd if "EleD" in i])
    ShareMarketIn   = sum(get_series_with_fallback(ShareMarketIn, label) for label in [i for i in model.err if "EleR" in i])

    ShareGenOutBESS  = sum(get_series_with_fallback(ShareGenOut, label) for label in [i for i in model.egg if "BESS" in i])
    ShareGenOutEV    = sum(get_series_with_fallback(ShareGenOut, label) for label in [i for i in model.egg if "EV" in i])
    ShareMarketOut   = sum(get_series_with_fallback(ShareMarketOut, label) for label in [i for i in model.err if "EleR" in i])
    ShareDemOut      = sum(get_series_with_fallback(ShareDemOut, label) for label in [i for i in model.edd if "EleD" in i])

    FVtoEV          = pd.Series(data=[(ShareGenInFV[p,sc,n]     * ShareGenOutEV  [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoBESS        = pd.Series(data=[(ShareGenInFV[p,sc,n]     * ShareGenOutBESS[p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoMkt         = pd.Series(data=[(ShareGenInFV[p,sc,n]     * ShareMarketOut [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoDem         = pd.Series(data=[(ShareGenInFV[p,sc,n]     * ShareDemOut    [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    ENStoEV         = pd.Series(data=[(ShareENSIn  [p,sc,n]     * ShareGenOutEV  [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    ENStoBESS       = pd.Series(data=[(ShareENSIn  [p,sc,n]     * ShareGenOutBESS[p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    ENStoDem        = pd.Series(data=[(ShareENSIn  [p,sc,n]     * ShareDemOut    [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    BESStoEV        = pd.Series(data=[(ShareGenInBESS[p,sc,n]   * ShareGenOutEV  [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    BESStoMkt       = pd.Series(data=[(ShareGenInBESS[p,sc,n]   * ShareMarketOut [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    BESStoDem       = pd.Series(data=[(ShareGenInBESS[p,sc,n]   * ShareDemOut    [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    EVtoBESS        = pd.Series(data=[(ShareGenInEV[p,sc,n]     * ShareGenOutBESS[p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EVtoMkt         = pd.Series(data=[(ShareGenInEV[p,sc,n]     * ShareMarketOut [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EVtoDem         = pd.Series(data=[(ShareGenInEV[p,sc,n]     * ShareDemOut    [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    MkttoEV         = pd.Series(data=[(ShareMarketIn [p,sc,n]   * ShareGenOutEV  [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    MkttoDem        = pd.Series(data=[(ShareMarketIn [p,sc,n]   * ShareDemOut    [p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    MkttoBESS       = pd.Series(data=[(ShareMarketIn [p,sc,n]   * ShareGenOutBESS[p,sc,n] * TotalEnergyIn[p,sc,n] * (1/model.factor1)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    SellPrice = pd.Series(data=[(sum(  model.Par['pVarEnergyPrice'][er][p,sc,n] * model.Par['pEleRetSellingRatio'][er]                                                                                                                                                 *1e0 for er in model.er)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    BuyCost   = pd.Series(data=[(sum(((model.Par['pVarEnergyCost' ][er][p,sc,n] * model.Par['pEleRetBuyingRatio' ][er] + model.Par['pEleRetelcertifikat'][er] + model.Par['pEleRetpaslag'][er]) * (1+model.Par['pEleRetmoms'][er]) + model.Par['pEleRetnetavgift'][er])*1e0 for er in model.er)) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    AvgPrice  = (SellPrice + BuyCost)/2

    FVtoEV_Val      = pd.Series(data=[(FVtoEV   [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoBESS_Val    = pd.Series(data=[(FVtoBESS [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoMkt_Val     = pd.Series(data=[(FVtoMkt  [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    FVtoDem_Val     = pd.Series(data=[(FVtoDem  [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    ENStoEV_Val     = pd.Series(data=[(ENStoEV  [p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    ENStoBESS_Val   = pd.Series(data=[(ENStoBESS[p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    ENStoDem_Val    = pd.Series(data=[(ENStoDem [p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    BESStoEV_Val    = pd.Series(data=[(BESStoEV [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    BESStoMkt_Val   = pd.Series(data=[(BESStoMkt[p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    BESStoDem_Val   = pd.Series(data=[(BESStoDem[p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    MkttoEV_Val     = pd.Series(data=[(MkttoEV  [p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    MkttoDem_Val    = pd.Series(data=[(MkttoDem [p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    MkttoBESS_Val   = pd.Series(data=[(MkttoBESS[p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    EVtoBESS_Val    = pd.Series(data=[(EVtoBESS [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EVtoMkt_Val     = pd.Series(data=[(EVtoMkt  [p,sc,n] * 1e0 * SellPrice[p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EVtoDem_Val     = pd.Series(data=[(EVtoDem  [p,sc,n] * 1e0 * BuyCost  [p,sc,n]) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))

    FVtoEVp         = pd.Series(data=[ FVtoEV.  loc[p].sum() for p in model.p], index=pd.Index(model.p))
    FVtoBESSp       = pd.Series(data=[ FVtoBESS.loc[p].sum() for p in model.p], index=pd.Index(model.p))
    FVtoMktp        = pd.Series(data=[ FVtoMkt. loc[p].sum() for p in model.p], index=pd.Index(model.p))
    FVtoDemp        = pd.Series(data=[ FVtoDem. loc[p].sum() for p in model.p], index=pd.Index(model.p))

    ENStoEVp        = pd.Series(data=[ENStoEV.  loc[p].sum() for p in model.p], index=pd.Index(model.p))
    ENStoBESSp      = pd.Series(data=[ENStoBESS.loc[p].sum() for p in model.p], index=pd.Index(model.p))
    ENStoDemp       = pd.Series(data=[ENStoDem. loc[p].sum() for p in model.p], index=pd.Index(model.p))

    BESStoEVp       = pd.Series(data=[BESStoEV. loc[p].sum() for p in model.p], index=pd.Index(model.p))
    BESStoMktp      = pd.Series(data=[BESStoMkt.loc[p].sum() for p in model.p], index=pd.Index(model.p))
    BESStoDemp      = pd.Series(data=[BESStoDem.loc[p].sum() for p in model.p], index=pd.Index(model.p))

    MkttoEVp        = pd.Series(data=[MkttoEV.  loc[p].sum() for p in model.p], index=pd.Index(model.p))
    MkttoDemp       = pd.Series(data=[MkttoDem. loc[p].sum() for p in model.p], index=pd.Index(model.p))
    MkttoBESSp      = pd.Series(data=[MkttoBESS.loc[p].sum() for p in model.p], index=pd.Index(model.p))

    EVtoBESSp       = pd.Series(data=[EVtoBESS. loc[p].sum() for p in model.p], index=pd.Index(model.p))
    EVtoMktp        = pd.Series(data=[EVtoMkt.  loc[p].sum() for p in model.p], index=pd.Index(model.p))
    EVtoDemp        = pd.Series(data=[EVtoDem.  loc[p].sum() for p in model.p], index=pd.Index(model.p))

    FVtoEV_Valp     = pd.Series(data=[ FVtoEV_Val.  loc[p].sum() for p in model.p], index=pd.Index(model.p)) / FVtoEVp
    FVtoBESS_Valp   = pd.Series(data=[ FVtoBESS_Val.loc[p].sum() for p in model.p], index=pd.Index(model.p)) / FVtoBESSp
    FVtoMkt_Valp    = pd.Series(data=[ FVtoMkt_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / FVtoMktp
    FVtoDem_Valp    = pd.Series(data=[ FVtoDem_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / FVtoDemp

    ENStoEV_Valp    = pd.Series(data=[ENStoEV_Val.  loc[p].sum() for p in model.p], index=pd.Index(model.p)) / ENStoEVp
    ENStoBESS_Valp  = pd.Series(data=[ENStoBESS_Val.loc[p].sum() for p in model.p], index=pd.Index(model.p)) / ENStoBESSp
    ENStoDem_Valp   = pd.Series(data=[ENStoDem_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / ENStoDemp

    BESStoEV_Valp   = pd.Series(data=[BESStoEV_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / BESStoEVp
    BESStoMkt_Valp  = pd.Series(data=[BESStoMkt_Val.loc[p].sum() for p in model.p], index=pd.Index(model.p)) / BESStoMktp
    BESStoDem_Valp  = pd.Series(data=[BESStoDem_Val.loc[p].sum() for p in model.p], index=pd.Index(model.p)) / BESStoDemp

    MkttoEV_Valp    = pd.Series(data=[MkttoEV_Val.  loc[p].sum() for p in model.p], index=pd.Index(model.p)) / MkttoEVp
    MkttoDem_Valp   = pd.Series(data=[MkttoDem_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / MkttoDemp
    MkttoBESS_Valp  = pd.Series(data=[MkttoBESS_Val.loc[p].sum() for p in model.p], index=pd.Index(model.p)) / MkttoBESSp

    EVtoBESS_Valp   = pd.Series(data=[EVtoBESS_Val. loc[p].sum() for p in model.p], index=pd.Index(model.p)) / EVtoBESSp
    EVtoMkt_Valp    = pd.Series(data=[EVtoMkt_Val.  loc[p].sum() for p in model.p], index=pd.Index(model.p)) / EVtoMktp
    EVtoDem_Valp    = pd.Series(data=[EVtoDem_Val.  loc[p].sum() for p in model.p], index=pd.Index(model.p)) / EVtoDemp

    dfEnergyBalance    = pd.DataFrame({'Period': FVtoEVp.index, 'FV_to_EV [KWh]': FVtoEVp.values, 'FV_to_BESS [KWh]': FVtoBESSp.values, 'FV_to_Mkt [KWh]': FVtoMktp.values, 'FV_to_Dem [KWh]': FVtoDemp.values, 'ENS_to_EV [KWh]': ENStoEVp.values, 'ENS_to_BESS [KWh]': ENStoBESSp.values, 'ENS_to_Dem [KWh]': ENStoDemp.values, 'BESS_to_EV [KWh]': BESStoEVp.values, 'BESS_to_Mkt [KWh]': BESStoMktp.values, 'BESS_to_Dem [KWh]': BESStoDemp.values, 'Mkt_to_EV [KWh]': MkttoEVp.values, 'Mkt_to_Dem [KWh]': MkttoDemp.values, 'Mkt_to_BESS [KWh]': MkttoBESSp.values, 'EV_to_BESS [KWh]': EVtoBESSp.values, 'EV_to_Mkt [KWh]': EVtoMktp.values, 'EV_to_Dem [KWh]': EVtoDemp.values})
    dfEnergyBalanceVal = pd.DataFrame({'Period': FVtoEV_Valp.index, 'FV_to_EV [SEK/KWh]': FVtoEV_Valp.values, 'FV_to_BESS [SEK/KWh]': FVtoBESS_Valp.values, 'FV_to_Mkt [SEK/KWh]': FVtoMkt_Valp.values, 'FV_to_Dem [SEK/KWh]': FVtoDem_Valp.values, 'ENS_to_EV [SEK/KWh]': ENStoEV_Valp.values, 'ENS_to_BESS [SEK/KWh]': ENStoBESS_Valp.values, 'ENS_to_Dem [SEK/KWh]': ENStoDem_Valp.values, 'BESS_to_EV [SEK/KWh]': BESStoEV_Valp.values, 'BESS_to_Mkt [SEK/KWh]': BESStoMkt_Valp.values, 'BESS_to_Dem [SEK/KWh]': BESStoDem_Valp.values, 'Mkt_to_EV [SEK/KWh]': MkttoEV_Valp.values, 'Mkt_to_Dem [SEK/KWh]': MkttoDem_Valp.values, 'Mkt_to_BESS [SEK/KWh]': MkttoBESS_Valp.values, 'EV_to_BESS [SEK/KWh]': EVtoBESS_Valp.values, 'EV_to_Mkt [SEK/KWh]': EVtoMkt_Valp.values, 'EV_to_Dem [SEK/KWh]': EVtoDem_Valp.values})
    dfEnergyBalance.to_csv(_path + '/oM_Result_08_rEnergyBalance_' + CaseName + '.csv', sep=',', header=True, index=False)
    dfEnergyBalanceVal.to_csv(_path + '/oM_Result_09_rEnergyBalanceVal_' + CaseName + '.csv', sep=',', header=True, index=False)

    print('Outputting the shares of energy balance  ... ', round(time.time() - StartTime), 's')
    StartTime = time.time()

    dfSankey = dfEnergyBalance.set_index(['Period']).stack().reset_index()
    dfSankey[['Component', 'Unit']] = dfSankey['level_1'].str.split(' ', expand=True)

    # replace FV by SolarPV, Mkt by Market, and Dem by Demand in the strings of rows of the column Component
    dfSankey['Component'] = dfSankey['Component'].str.replace('FV', 'SolarPV')
    dfSankey['Component'] = dfSankey['Component'].str.replace('Mkt', 'Market')
    dfSankey['Component'] = dfSankey['Component'].str.replace('Dem', 'Demand')

    # split the column Component
    dfSankey[['Source', 'C2', 'Target']] = dfSankey['Component'].str.split('_', expand=True)

    dfSankey = dfSankey[['Period', 'Source', 'Target', 0]].set_index(['Period', 'Source', 'Target'])

    # sum values in column flow_value and have Source as index
    source_sum = dfSankey.reset_index().pivot_table(index=['Period', 'Source'], values=0, aggfunc='sum')

    # sum values in column flow_value and have Target as index
    target_sum = dfSankey.reset_index().pivot_table(index=['Period', 'Target'], values=0, aggfunc='sum')

    # add column Source %, Target %, using values of column flow_value. Source % is the value divided by the sum of the values of the column flow_value for the same case, period and target. Target % is the value divided by the sum of the values of the columm source have the same value in the row.
    dfSankey['Source_%'] = 0
    dfSankey['Target_%'] = 0

    # Ensure no division by zero or NaN in source_sum
    dfSankey['Source_%'] = dfSankey.apply(
        lambda row: (row[0] / source_sum.loc[(row.name[0], row.name[1])][0] * 100)
        if source_sum.loc[(row.name[0], row.name[1])][0] != 0 else 0,
        axis=1
    )
    # Ensure no division by zero or NaN in target_sum
    dfSankey['Target_%'] = dfSankey.apply(
        lambda row: (row[0] / target_sum.loc[(row.name[0], row.name[2])][0] * 100)
        if target_sum.loc[(row.name[0], row.name[2])][0] != 0 else 0,
        axis=1
    )

    dfSankey.fillna(0, inplace=True)

    dfSankey = dfSankey.reset_index()

    dfSankey['flow_value'] = dfSankey[0]
    data = dfSankey.copy()

    # Remove zero-flow rows
    data = data[data['flow_value'] > 0]

    # Function to sort strings in a column
    def sort_strings(column):
        return column.apply(lambda x: ', '.join(sorted(x.split(', '))))

    # Apply the function to the specified columns
    data['Source'] = sort_strings(data['Source'])
    data['Target'] = sort_strings(data['Target'])

    # Function to create Sankey diagram for each unique case in level_0
    def create_sankey_for_case(case_data, case_name):
        # Convert data to ausankey's required structure
        sankey_data = pd.DataFrame({
            "Stage1": case_data["Source"],
            "Value1": case_data["Source_%"],
            # "Value1": case_data["flow_value"],
            "Stage2": case_data["Target"],
            "Value2": case_data["Target_%"],
            # "Value2": case_data["flow_value"],
            # "Stage3": case_data["Target"]  # Repeat the target to fill in for a 3-stage view
        })

        # Plot Sankey diagram for each case
        # plt.figure(figsize=(5, 3))
        plt.figure()
        sky.sankey(
            sankey_data,
            sort="top",
            titles=["Source", "Target"],
            valign="center"
        )
        plt.title(f"Case: {CaseName}, values in %")
        # save the plot
        plt.savefig(os.path.join(_path, 'oM_Plot_rSankey_' + CaseName + '.png'), format='png')
        # plt.show()
        # close plt
        plt.close()
    #
    # Generate Sankey diagrams for each unique value in 'level_0'
    for case in data['Period'].unique():
        case_data = data[data['Period'] == case]
        create_sankey_for_case(case_data, case)

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