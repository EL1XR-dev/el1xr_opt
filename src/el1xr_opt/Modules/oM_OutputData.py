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
import plotly.graph_objects as go
# import altair_saver
from  collections import defaultdict
from  pyomo.environ import Var, Param, Constraint
from .utils.oM_Utils import log_time
try:
    import ausankey as sky
except Exception:
    sky = None

# ============================================================================
# REUSABLE HELPER FUNCTIONS FOR CSV EXPORT
# ============================================================================

def save_to_csv(df, path, filename, index=False):
    """
    Save a DataFrame to CSV file.
    
    Args:
        df (pd.DataFrame): DataFrame to save
        path (str): Directory path
        filename (str): Filename including extension
        index (bool): Whether to include index in CSV
    """
    filepath = os.path.join(path, filename)
    df.to_csv(filepath, index=index, sep=',')

# ============================================================================
# REUSABLE HELPER FUNCTIONS FOR PLOTTING
# ============================================================================

def create_line_chart(df, x_col, y_col, color_col=None, title='', x_title='', y_title='', 
                      width=800, height=400, date_format="%a, %b %d, %H:%M", strokeDash=None):
    """
    Create a reusable Altair line chart.
    
    Args:
        df (pd.DataFrame): Data to plot
        x_col (str): Column name for x-axis
        y_col (str): Column name for y-axis
        color_col (str, optional): Column name for color encoding
        title (str): Chart title
        x_title (str): X-axis title
        y_title (str): Y-axis title
        width (int): Chart width
        height (int): Chart height
        date_format (str): Format string for date axis
        strokeDash (list, optional): Dash pattern for line [5, 5]
    
    Returns:
        alt.Chart: Altair chart object
    """
    mark_opts = {'point': alt.OverlayMarkDef(filled=False, fill='white')}
    if strokeDash:
        mark_opts['strokeDash'] = strokeDash
    
    chart = alt.Chart(df).mark_line(**mark_opts)
    
    encoding = {
        'x': alt.X(f'{x_col}:T' if ':T' not in x_col else x_col,
                   axis=alt.Axis(title=x_title, labelAngle=-90, format=date_format, 
                               tickCount=30, labelLimit=1000)),
        'y': alt.Y(f'{y_col}:Q' if ':Q' not in y_col else y_col,
                   axis=alt.Axis(title=y_title))
    }
    
    if color_col:
        encoding['color'] = alt.Color(f'{color_col}:N', legend=alt.Legend(title=''))
    
    return chart.encode(**encoding).properties(width=width, height=height, title=title)

def create_bar_chart(df, x_col, y_col, color_col, title='', x_title='', y_title='',
                     width=800, height=400, date_format="%a, %b %d, %H:%M"):
    """
    Create a reusable Altair bar chart.
    
    Args:
        df (pd.DataFrame): Data to plot
        x_col (str): Column name for x-axis
        y_col (str): Column name for y-axis (use 'sum(...)' for aggregation)
        color_col (str): Column name for color encoding
        title (str): Chart title
        x_title (str): X-axis title
        y_title (str): Y-axis title
        width (int): Chart width
        height (int): Chart height
        date_format (str): Format string for date axis
    
    Returns:
        alt.Chart: Altair chart object
    """
    return (alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(f'{x_col}:T', axis=alt.Axis(title=x_title, labelAngle=-90, 
                       format=date_format, tickCount=30, labelLimit=1000)),
                y=alt.Y(y_col, axis=alt.Axis(title=y_title)),
                color=alt.Color(f'{color_col}:N', legend=alt.Legend(title=''))
            )
            .properties(width=width, height=height, title=title))

def create_duration_curve(df, value_col, date_col, title, y_label, path, filename):
    """
    Create and save a duration curve plot.
    
    Args:
        df (pd.DataFrame): Input dataframe
        value_col (str): Column name containing values to plot
        date_col (str): Column name containing dates
        title (str): Chart title
        y_label (str): Y-axis label
        path (str): Directory path to save chart
        filename (str): Output filename
    
    Returns:
        pd.DataFrame: DataFrame sorted by value (descending) with counter column
    """
    df_sorted = df.sort_values(by=value_col, ascending=False).reset_index(drop=True)
    df_sorted['Counter'] = range(len(df_sorted))
    
    chart = (alt.Chart(df_sorted)
             .mark_line(point=alt.OverlayMarkDef(filled=False, fill='white'))
             .encode(
                 x=alt.X('Counter', title='Time', sort=None),
                 y=alt.Y(value_col, title=y_label)
             )
             .properties(title=title, width=800, height=400))
    
    chart.save(os.path.join(path, filename))
    return df_sorted

def save_chart(chart, path, filename, embed_options=None):
    """
    Save an Altair chart to HTML file.
    
    Args:
        chart: Altair chart object
        path (str): Directory path
        filename (str): Filename including extension
        embed_options (dict, optional): Options for embedding the chart. Defaults to {'renderer': 'svg'}.
    """
    if embed_options is None:
        embed_options = {'renderer': 'svg'}
    filepath = os.path.join(path, filename)
    chart.save(filepath, embed_options=embed_options)

def create_and_save_duration_curve(series_data, index_tuples, value_col_name, Date, hour_of_year,
                                   path, csv_filename, html_filename, title, y_label):
    """
    Create and save a duration curve with both CSV and HTML outputs.
    
    Args:
        series_data (list): List of values
        index_tuples: Index tuples (e.g., from model.psn)
        value_col_name (str): Name for the value column  
        Date: Starting date
        hour_of_year (str): Hour of year reference
        path (str): Output directory
        csv_filename (str): CSV filename
        html_filename (str): HTML filename
        title (str): Chart title
        y_label (str): Y-axis label
    
    Returns:
        pd.DataFrame: Processed dataframe with counter
    """
    # Create series and sort
    df = pd.Series(series_data, index=pd.MultiIndex.from_tuples(index_tuples))
    df = df.sort_values(ascending=False).to_frame(name=value_col_name)
    
    # Add date column
    df['Date'] = df.index.get_level_values(2).map(
        lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))
    ).strftime('%Y-%m-%d %H:%M:%S')
    
    # Reset index and rename
    df = df.reset_index().rename(
        columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel'}, 
        inplace=False
    )
    
    # Save CSV
    save_to_csv(df, path, csv_filename, index=False)
    
    # Create and save plot with counter
    df['Counter'] = range(len(df))
    chart = (alt.Chart(df)
             .mark_line(point=alt.OverlayMarkDef(filled=False, fill='white'))
             .encode(
                 x=alt.X('Counter', title='Time', sort=None),
                 y=alt.Y(value_col_name, title=y_label)
             )
             .properties(title=title, width=800, height=400))
    
    save_chart(chart, path, html_filename)
    
    return df

def _write_variable_to_csv(path, var, var_name, case_name):
    """Helper function to write a variable component to CSV."""
    filename = f'oM_Result_{var_name}_{case_name}.csv'
    with open(os.path.join(path, filename), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Index', 'Value', 'Lower Bound', 'Upper Bound'])
        for index in var:
            writer.writerow([var_name, index, var[index].value, 
                           str(var[index].lb), str(var[index].ub)])

def _write_parameter_to_csv(path, par, par_name, case_name):
    """Helper function to write a parameter component to CSV."""
    filename = f'oM_Result_{par_name}_{case_name}.csv'
    with open(os.path.join(path, filename), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Index', 'Value'])
        if par.is_indexed():
            for index in par:
                value = par[index] if (isinstance(index, tuple) and not par.mutable) or not par.mutable else par[index].value
                writer.writerow([par_name, index, value])
        else:
            writer.writerow([par_name, 'NA', par.value])

def _write_constraint_to_csv(path, con, con_name, case_name, model):
    """Helper function to write a constraint component to CSV."""
    filename = f'oM_Result_{con_name}_{case_name}.csv'
    with open(os.path.join(path, filename), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Index', 'Value', 'Lower Bound', 'Upper Bound'])
        if con.is_indexed():
            for index in con:
                writer.writerow([con_name, index, model.dual[con[index]], 
                               str(con[index].lb), str(con[index].ub)])

def saving_rawdata(DirName, CaseName, SolverName, model, optmodel, indlog):
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
        indlog: Logging indicator.

    Returns:
        model: The original optimization model object.
    """
    _path = os.path.join(DirName, CaseName)
    StartTime = time.time()

    # Write variables
    for var in optmodel.component_objects(Var, active=True):
        var_object = getattr(optmodel, str(var))
        _write_variable_to_csv(_path, var_object, var.name, CaseName)

    # Write parameters
    for par in optmodel.component_objects(Param):
        par_object = getattr(optmodel, str(par))
        _write_parameter_to_csv(_path, par_object, par.name, CaseName)

    # Write constraints (dual variables)
    for con in optmodel.component_objects(Constraint, active=True):
        con_object = getattr(optmodel, str(con))
        _write_constraint_to_csv(_path, con_object, con.name, CaseName, model)

    log_time('-- Total time for outputting the raw data:', StartTime, ind_log=indlog)

    return model

def saving_results(DirName, CaseName, Date, model, optmodel, indlog):
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
        save_to_csv(Output_vDemand, _path, f'oM_Result_00_rElectricityDemand_{CaseName}.csv')

    granular_components = {
        'EleNCost': 'vTotalEleNCost', 'EleXCost': 'vTotalEleXCost', 'EleMCost': 'vTotalEleMCost',
        'EleOCost': 'vTotalEleOCost', 'HydMCost': 'vTotalHydMCost',
        'HydOCost': 'vTotalHydOCost', 'EleXRev': 'vTotalEleXRev',
        # 'EleOCost': 'vTotalEleOCost', 'EleDCost': 'vTotalEleDCost', 'HydMCost': 'vTotalHydMCost',
        # 'HydOCost': 'vTotalHydOCost', 'HydDCost': 'vTotalHydDCost', 'EleXRev': 'vTotalEleXRev',
        'EleMRev': 'vTotalEleMRev', 'HydMRev': 'vTotalHydMRev',
    }
    static_vars = ['vTotalEleNCost', 'vTotalEleXCost', 'vTotalEleXRev']
    static_components = {k: v for k, v in granular_components.items() if v in static_vars}
    dynamic_components = {k: v for k, v in granular_components.items() if v not in static_vars}

    # Fetch static data
    static_data = {}
    for name, attr in static_components.items():
        var_object = getattr(optmodel, attr)
        data = [var_object[p, sc]() for p, sc in model.ps]
        index = pd.MultiIndex.from_tuples(model.ps, names=['Period', 'Scenario'])
        static_data[name] = pd.Series(data, index=index)
    df_static = pd.DataFrame(static_data)

    # Fetch dynamic data
    dynamic_data = {}
    for name, attr in dynamic_components.items():
        var_object = getattr(optmodel, attr)
        data = [var_object[p, sc, n]() * model.Par['pDuration'][p, sc, n] for p, sc, n in model.psn]
        index = pd.MultiIndex.from_tuples(model.psn, names=['Period', 'Scenario', 'LoadLevel'])
        dynamic_data[name] = pd.Series(data, index=index)
    df_dynamic = pd.DataFrame(dynamic_data)

    # Aggregate dynamic data to static level (by Period, Scenario)
    df_dynamic_agg = df_dynamic.groupby(['Period', 'Scenario']).sum()

    # --- Create Hierarchical Aggregations ---
    # Level 3: Cost/Revenue Categories
    market_cost = df_dynamic_agg['EleMCost'] + df_dynamic_agg['HydMCost']
    # operational_cost = (df_dynamic_agg['EleOCost'] + df_dynamic_agg['HydOCost'] +
    #                     df_dynamic_agg['EleDCost'] + df_dynamic_agg['HydDCost'])
    operational_cost = (df_dynamic_agg['EleOCost'] + df_dynamic_agg['HydOCost'])
    system_cost = df_static['EleNCost'] + df_static['EleXCost']
    market_revenue = df_dynamic_agg['EleMRev'] + df_dynamic_agg['HydMRev']
    system_revenue = df_static['EleXRev']

    # Level 2: Total Cost/Revenue
    total_cost = market_cost + operational_cost + system_cost
    total_revenue = market_revenue + system_revenue

    # Combine all results into a single DataFrame for static output
    df_results = pd.DataFrame({
        'MarketCost': market_cost,
        'OperationalCost': operational_cost,
        'SystemCost': system_cost,
        'MarketRevenue': market_revenue,
        'SystemRevenue': system_revenue,
        'TotalCost': total_cost,
        'TotalRevenue': total_revenue
    }).join(df_static) # aappend original static granular components

    Output_TotalCost_Static = df_results.stack().to_frame(name='EUR').rename_axis(['Period', 'Scenario', 'Component']).reset_index()
    Output_TotalCost_Static.to_csv(f"{_path}/oM_Result_01_rTotalCost_Static_{CaseName}.csv", index=False, sep=',')

    # -- Plotting helper function ---
    def get(df, comp):
        out = df.loc[df.Component == comp, 'EUR']
        return out.iloc[0] if not out.empty else 0.0

    links = [
        # COST hierarchy
        ("TotalCost", "MarketCost", get(Output_TotalCost_Static, "MarketCost")),
        ("TotalCost", "OperationalCost", get(Output_TotalCost_Static, "OperationalCost")),
        ("TotalCost", "SystemCost", get(Output_TotalCost_Static, "SystemCost")),
        ("SystemCost", "EleNCost", get(Output_TotalCost_Static, "EleNCost")),
        ("SystemCost", "EleXCost", get(Output_TotalCost_Static, "EleXCost")),

        # REVENUE hierarchy
        ("TotalRevenue", "MarketRevenue", get(Output_TotalCost_Static, "MarketRevenue")),
        ("TotalRevenue", "SystemRevenue", get(Output_TotalCost_Static, "SystemRevenue")),
        ("SystemRevenue", "EleXRev", get(Output_TotalCost_Static, "EleXRev"))
    ]

    df_links = pd.DataFrame(links, columns=["source", "target", "value"])

    labels = pd.unique(df_links[['source', 'target']].values.ravel('K')).tolist()
    id_map = {label: i for i, label in enumerate(labels)}

    df_links['source_id'] = df_links['source'].map(id_map)
    df_links['target_id'] = df_links['target'].map(id_map)

    colors = ["#8e24aa" if "Cost" in lbl else "#2e7d32" for lbl in labels]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=15,
            thickness=12,
            line=dict(color="black", width=0.4),
            label=labels,
            color=colors
        ),
        link=dict(
            source=df_links['source_id'],
            target=df_links['target_id'],
            value=df_links['value']
        )
    ))

    fig.update_layout(
        title_text="Cost and Revenue Hierarchy (auto-generated from raw_data)",
        font=dict(size=13),
        height=600
    )

    fig.write_html(f"{_path}/oM_Plot_01_rTotalCost_Sankey_{CaseName}.html", include_plotlyjs="cdn", full_html=True)

    # --- Prepare Hourly (Dynamic) Output ---
    def compute_date(x):
        try:
            if isinstance(x, str) and x.startswith('t'):
                return Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))
            else: return pd.NaT
        except Exception: return pd.NaT

    df_dynamic_output = df_dynamic.stack().to_frame(name='EUR').rename_axis(['Period', 'Scenario', 'LoadLevel', 'Component']).reset_index()
    df_dynamic_output['Date'] = df_dynamic_output['LoadLevel'].map(compute_date).dt.strftime('%Y-%m-%d %H:%M:%S')

    Output_TotalCost_Hourly = df_dynamic_output
    Output_TotalCost_Hourly.to_csv(f"{_path}/oM_Result_01_rTotalCost_Hourly_{CaseName}.csv", index=False, sep=',')

    def extract_cost_or_rev(optmodel, model, var_name, set_name, multiplier=False, timeline=None, revenue=False, component_name=None):
        """
        Generic extractor for cost or revenue components.

        Parameters:
            optmodel: Pyomo model with variable values
            model: Pyomo model with parameter sets
            var_name (str): Name of the variable (string)
            set_name (str): Name of the index set ('ps' or 'psn')
            multiplier (bool): Whether to multiply by duration
            revenue (bool): If True, multiply values by -1
            component_name (str): Label for the output DataFrame

        Returns:
            pd.DataFrame: DataFrame with Period, Scenario, EUR, and Component columns
        """
        var       = getattr(optmodel, var_name)
        index_set = getattr(model, set_name)
        index_len = len(next(iter(index_set)))

        # Compute values
        if multiplier and index_len == 3 and timeline == "Hourly":
            data = [var[p, sc, n]() * model.Par['pDuration'][p, sc, n] for p, sc, n in index_set]
            df = pd.DataFrame(index_set, columns=['Period', 'Scenario', 'Hour'])
        elif multiplier and index_len == 3 and timeline == "Daily":
            data = [var[p, sc, d]() for p, sc, d in index_set]
            df = pd.DataFrame(index_set, columns=['Period', 'Scenario', 'Day'])
        else:
            data = [var[p, sc]() for p, sc in index_set]
            df = pd.DataFrame(index_set, columns=['Period', 'Scenario'])

        df['EUR'] = data

        # Aggregate if necessary (collapse over Time)
        if 'Hour' or 'Day' in df.columns:
            df = df.groupby(['Period', 'Scenario'], as_index=False)['EUR'].sum()

        # Apply sign convention
        if revenue:
            df['EUR'] *= -1

        # Add component label
        df['Component'] = component_name
        return df

    # === Extract all components ===
    Output_vTotalEleMrkDACost     = extract_cost_or_rev(optmodel, model, 'vTotalEleMrkDACost',     'psn', multiplier=True, timeline="Hourly", revenue=False, component_name='Day-Ahead Market Cost'   )
    Output_vTotalEleNetUseFixCost = extract_cost_or_rev(optmodel, model, 'vTotalEleNetUseFixCost', 'ps',                                      revenue=False, component_name='Network Fixed Cost'      )
    Output_vTotalEleNetUseVarCost = extract_cost_or_rev(optmodel, model, 'vTotalEleNetUseVarCost', 'ps',                                      revenue=False, component_name='Network Variable Cost'   )
    Output_vTotalElePeakCost      = extract_cost_or_rev(optmodel, model, 'vTotalElePeakCost',      'ps',                                      revenue=False, component_name='Power Peak Cost'         )
    Output_vTotalEleEnergyTaxCost = extract_cost_or_rev(optmodel, model, 'vTotalEleEnergyTaxCost', 'ps',                                      revenue=False, component_name='Energy Tax Cost'         )
    Output_vTotalEleDCost         = extract_cost_or_rev(optmodel, model, 'vTotalEleDCost',         'psd', multiplier=True, timeline="Daily",  revenue=False, component_name='Depth of Discharge Cost' )
    Output_vTotalEleMrkDARev      = extract_cost_or_rev(optmodel, model, 'vTotalEleMrkDARev',      'psn', multiplier=True, timeline="Hourly", revenue=True,  component_name='Day-Ahead Market Revenue')
    Output_vTotalEleFCRDUpRev     = extract_cost_or_rev(optmodel, model, 'vTotalEleFCRDUpRev',     'psn', multiplier=True, timeline="Hourly", revenue=True,  component_name='FCR-D Upwards Revenue'   )
    Output_vTotalEleFCRDDwRev     = extract_cost_or_rev(optmodel, model, 'vTotalEleFCRDDwRev',     'psn', multiplier=True, timeline="Hourly", revenue=True,  component_name='FCR-D Downwards Revenue' )

    # === Combine and export ===
    Output_AdditionalCosts = pd.concat([Output_vTotalEleMrkDACost, Output_vTotalEleNetUseFixCost, Output_vTotalEleNetUseVarCost, Output_vTotalElePeakCost, Output_vTotalEleEnergyTaxCost, Output_vTotalEleDCost, Output_vTotalEleMrkDARev, Output_vTotalEleFCRDUpRev, Output_vTotalEleFCRDDwRev], ignore_index=True)
    Output_AdditionalCosts.to_csv(f"{_path}/oM_Result_01_rObjFunComponents_{CaseName}.csv", index=False)

    df = Output_AdditionalCosts.copy()

    # --- 1. Separate cost and revenue ---
    df["Type"] = df["EUR"].apply(lambda x: "Cost" if x >= 0 else "Revenue")
    df["AbsEUR"] = df["EUR"].abs()

    # --- 2. Compute percentages within each Type ---
    df["Percentage"] = df.groupby("Type")["AbsEUR"].transform(lambda x: x / x.sum())

    # --- 3. Split for plotting ---
    df_cost = df[df["Type"] == "Cost"]
    df_rev = df[df["Type"] == "Revenue"]

    def pie_chart(df_sub, title):
        base  = alt.Chart(df_sub).encode(theta=alt.Theta("AbsEUR:Q", type="quantitative", stack=True), color=alt.Color("Component:N", type="nominal", legend=alt.Legend(title=title))).properties(width=400, height=400)
        pie   = base.mark_arc(outerRadius=120)
        text  = base.mark_text(radius=150, size=15).encode(text=alt.Text("Percentage:Q", format=".1%"))
        chart = pie+text
        # chart = chart.resolve_scale(theta="independent")
        chart = alt.layer(pie, text, data=df_sub).resolve_scale(theta="independent")

        return chart

    # --- 5. Build charts ---
    chart_cost = pie_chart(df_cost, "Cost Breakdown")
    chart_rev = pie_chart(df_rev, "Revenue Breakdown")

    # --- 6. Show side by side ---
    main_chart = (chart_cost | chart_rev).resolve_scale(color="independent")

    # Save the chart
    save_chart(main_chart, _path, f'oM_Plot_01_rObjFunComponents_{CaseName}.html')

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
    OutputResults6     = pd.Series(data=[     optmodel.vEleImport               [p,sc,n,nd      ]() * model.Par['pDuration'][p,sc,n]                                                                            for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ElectricityImport' )
    OutputResults7     = pd.Series(data=[    -optmodel.vEleExport               [p,sc,n,nd      ]() * model.Par['pDuration'][p,sc,n]                                                                            for p,sc,n,nd    in sPNND  ], index=pd.Index(sPNND  )).to_frame(name='ElectricityExport' )
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
    save_to_csv(Output_EleBalance, _path, f'oM_Result_02_rElectricityBalance_{CaseName}.csv')
    model.Output_EleBalance = Output_EleBalance

    # removing the component 'PowerFlowOut' and 'PowerFlowIn' from the Output_EleBalance
    Output_EleBalance = Output_EleBalance[~Output_EleBalance['Component'].isin(['PowerFlowOut', 'PowerFlowIn', 'Electrolyzer', 'H2ESS'])]
    # chart for the electricity balance using Altair and bars
    brush = alt.selection_interval(encodings=['x'])
    # Base chart for KWh with the primary y-axis
    main_chart = alt.Chart(Output_EleBalance).mark_bar().encode(
        # x='Date:T',
        x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
        y=alt.Y('sum(KWh):Q', axis=alt.Axis(title='KWh')),
        color='Component:N'
    ).properties(
        width=800,
        height=400
    ).transform_filter(brush)

    slider_chart = alt.Chart(Output_EleBalance).mark_bar().encode(
        x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
        y=alt.Y('sum(KWh):Q', axis=alt.Axis(title='KWh')),
        color='Component:N'
    ).properties(
        width=800,
        height=100
    ).add_params(brush)

    kwh_chart = main_chart & slider_chart

    save_chart(kwh_chart, _path, f'oM_Plot_02_rElectricityBalance_{CaseName}.html')

    log_time('-- Total time for outputting the electricity balance:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # net demand by filtering Solar-PV, BESS, and ElectricityDemand in Output_EleBalance, column Component
    Output_NetDemand = Output_EleBalance[Output_EleBalance['Component'].isin(['BESS', 'Solar-PV', 'EV', 'ElectricityDemand'])]
    # aggregate the columns 'Period', 'Scenario', 'LoadLevel', 'Date', 'MWh' and 'KWh'
    Output_NetDemand = Output_NetDemand.groupby(['Period', 'Scenario', 'LoadLevel', 'Date'])[['MWh', 'KWh']].sum().reset_index()
    # changing the sign of the values in the column 'MWh' and 'KWh'
    Output_NetDemand['MWh'] = Output_NetDemand['MWh'].apply(lambda x: x)
    Output_NetDemand['KWh'] = Output_NetDemand['KWh'].apply(lambda x: x)
    # save the results to a csv file
    save_to_csv(Output_NetDemand, _path, f'oM_Result_03_rElectricityNetDemand_{CaseName}.csv')

    log_time('-- Total time for outputting the net electricity demand:', StartTime, ind_log=indlog)
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
    Output_EleCost = pd.Series(data=[(model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetOverforingsavgift'][er] + model.Par['pEleRetPaslag'][er] + model.Par['pEleRetEnergyTax'][er]) for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    Output_EleCost = Output_EleCost.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Component'}, inplace=False).set_index(['Period', 'Scenario', 'LoadLevel', 'Component'], inplace=False)
    # select the third level of the index and create a new column date using the Date as a initial date
    Output_EleCost['Date'] = Output_EleCost.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    Output_EleCost = Output_EleCost.reset_index().groupby(['Period', 'Scenario', 'LoadLevel', 'Date'])[['EUR/KWh']].sum().reset_index()
    Output_EleCost['Type'] ='ElectricityCost'

    # merge the results of the original demand with the net demand and electricity cost
    Output_Demand = pd.concat([Output_NetDemand, Output_OrgDemand], axis=0)
    # save the results to a csv file
    save_to_csv(Output_Demand, _path, f'oM_Result_04_rAllElectricityDemand_{CaseName}.csv')
    model.Output_Demand = Output_Demand

    log_time('-- Total time for outputting the all electricity demand:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # Base chart for KWh with the primary y-axis
    # --- Common formatting options ---
    x_axis = alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format='%a, %b %d, %H:%M', tickCount=30, labelLimit=1000))

    # --- KWh Chart (Main Energy Use) ---
    kwh_chart = (
        alt.Chart(Output_Demand)
        .mark_line(color='steelblue', point=alt.OverlayMarkDef(filled=False, fill='white'))
        .encode(
            x=x_axis,
            y=alt.Y('KWh:Q', axis=alt.Axis(title='Energy [kWh]')),
            color=alt.Color('Type:N', legend=alt.Legend(title='Type'))
        )
    )

    # --- EUR/kWh Chart (Cost) ---
    eur_chart = (
        alt.Chart(Output_EleCost)
        .mark_line(color='orange', strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False, fill='white'))
        .encode(
            x=x_axis,
            y=alt.Y('EUR/KWh:Q', axis=alt.Axis(title='Price [SEK/kWh]', orient='right')),
            color=alt.Color('Type:N', legend=None)
        )
    )

    # --- Combine charts with independent Y-axes ---
    main_chart = (
        alt.layer(kwh_chart, eur_chart)
        .resolve_scale(y='independent')
        .properties(width=900, height=400, title='Electricity Demand and Price Over Time')
    )

    # --- Save chart as HTML (SVG embedded) ---
    save_chart(main_chart, _path, f'oM_Plot_03_rEleDemand_{CaseName}.html')
    if sum(model.Par['pEleDemFlexible'][ed] for ed in model.ed) != 0.0:
        vDemand_chart = alt.Chart(Output_vDemand).mark_line(color='blue', point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
            # x='Date:T',
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000)),
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
        chart2.save(_path + '/oM_Plot_04_rEleFlexDemand_' + CaseName + '.html', embed_options={'renderer':'svg'})

    # %% outputting the state of charge of the battery energy storage system
    #%%  State of charge of the battery energy storage system per period, scenario, and load level
    sPSNEGS = [(p, sc, n, egs) for p, sc, n, egs in model.ps * model.negs if (p, egs) in model.pegs]
    if sPSNEGS:
        OutputResults1     = pd.Series(data=[ optmodel.vEleInventory[p,sc,n,egs]() for p,sc,n,egs in sPSNEGS], index=pd.Index(sPSNEGS)).to_frame(name='SOC').reset_index().pivot_table(index=['level_0','level_1','level_2'], columns='level_3', values='SOC', aggfunc='sum')
        OutputResults1['Date'] = OutputResults1.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
        Output_EleSOE = OutputResults1.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Date'], axis=0).stack().reset_index().rename(columns={'level_3': 'Component', 0: 'SOE'}, inplace=False)
        Output_EleSOE['SOE'] *= (1/model.factor1)
        save_to_csv(Output_EleSOE, _path, f'oM_Result_05_rEleStateOfEnergy_{CaseName}.csv')

        log_time('-- Total time for outputting the electrical state of energy:', StartTime, ind_log=indlog)
        StartTime = time.time()

        # plot
        # Base chart for SOC with the primary y-axis and dashed line style
        ele_soe_chart = alt.Chart(Output_EleSOE).mark_line(color='green', strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000, labelFontSize=16, titleFontSize=18)),
            y=alt.Y('SOE:Q', axis=alt.Axis(title='SOE', labelFontSize=16, titleFontSize=18)),
            color=alt.Color('Component:N', legend=alt.Legend(title='Component', labelFontSize=16, titleFontSize=18))
        )

    if len(model.egv):
        # Base chart of VarFixedAvailability with the primary y-axis
        Output_FixedAvailability = model.Par['pVarFixedAvailability'].loc[model.psn]
        Output_FixedAvailability['Date'] = Output_FixedAvailability.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
        Output_FixedAvailability = Output_FixedAvailability.set_index('Date', append=True).rename_axis(['Period', 'Scenario', 'LoadLevel', 'Date'], axis=0).stack().reset_index().rename(columns={'level_4': 'Component', 0: 'FixedAvailability'}, inplace=False)
        save_to_csv(Output_FixedAvailability, _path, f'oM_Result_06_rFixedAvailability_{CaseName}.csv')

        log_time('-- Total time for outputting the electrical fixed availability:', StartTime, ind_log=indlog)
        StartTime = time.time()

        # filter component 'EV_01' and 'EV_02' from the Output_FixedAvailability
        Output_FixedAvailability = Output_FixedAvailability[Output_FixedAvailability['Component'].isin([list(model.egs)[0]])]
        # Base chart for FixedAvailability with the primary y-axis and dashed line style
        ele_fAv_chart = alt.Chart(Output_FixedAvailability).mark_point(color='red').encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000, labelFontSize=16, titleFontSize=18)),
            y=alt.Y('FixedAvailability:Q', axis=alt.Axis(title='FixedAvailability', orient='right', labelFontSize=16, titleFontSize=18)),
        )

        chart = alt.layer(ele_soe_chart, ele_fAv_chart).resolve_scale(
            y='independent'  # Ensures each chart has its own y-axis
        ).properties(
            width=800,
            height=400
        ).interactive()

        # Save the chart to an HTML file
        save_chart(chart, _path, f'oM_Plot_05_rEleStateOfEnergy_{CaseName}.html')

        # --- Ensure 'Date' is datetime ---
        Output_EleSOE['Date'] = pd.to_datetime(Output_EleSOE['Date'])
        Output_FixedAvailability['Date'] = pd.to_datetime(Output_FixedAvailability['Date'])

        # --- Filter for first 7 days ---
        start_date = Output_EleSOE['Date'].min()
        end_date = start_date + pd.Timedelta(days=7)

        soe_data_7days = Output_EleSOE[(Output_EleSOE['Date'] >= start_date) & (Output_EleSOE['Date'] < end_date)]
        ava_data_7days = Output_FixedAvailability[(Output_FixedAvailability['Date'] >= start_date) & (Output_FixedAvailability['Date'] < end_date)]

        ele_soe_chart = alt.Chart(soe_data_7days).mark_line(color='green', strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False, fill="white")).encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000, labelFontSize=16, titleFontSize=18)),
            y=alt.Y('SOE:Q', axis=alt.Axis(title='SOE', labelFontSize=16, titleFontSize=18)),
            color = alt.Color('Component:N', legend=alt.Legend(title='Component', labelFontSize=16, titleFontSize=18))
        )

        ele_fAv_chart = alt.Chart(ava_data_7days).mark_point(color='red').encode(
            x=alt.X('Date:T', axis=alt.Axis(title='', labelAngle=-90, format="%a, %b %d, %H:%M", tickCount=30, labelLimit=1000, labelFontSize=16, titleFontSize=18)),
            y=alt.Y('FixedAvailability:Q', axis=alt.Axis(title='FixedAvailability', orient='right', labelFontSize=16, titleFontSize=18)),
        )

        chart = alt.layer(ele_soe_chart, ele_fAv_chart).resolve_scale(
            y='independent'  # Ensures each chart has its own y-axis
        ).properties(
            width=800,
            height=400
        ).interactive()

        # Save the chart to an HTML file
        save_chart(chart, _path, f'oM_Plot_05_rEleStateOfEnergy_7days_{CaseName}.html')

    # Creating dataframe with outputs like electricity buy, electricity sell, total production, total consumption, Inventory, energy outflows, VarStartUp, VarShutDown, FixedAvailability, EleDemand, ElectricityCost, ElectricityPrice
    # series of electricity production
    OutputResults1a = pd.Series(data=[ (sum((optmodel.vEleGenCommitment[p,sc,n,egt]() * model.Par['pEleMinPower'][egt][p,sc,n] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egt]()) * model.Par['pDuration'][p,sc,n] for egt  in model.egt  if (nd,egt) in model.n2eg and (gt,egt) in model.t2eg) + sum((optmodel.vEleStorDischarge[p,sc,n,egs]() * model.Par['pEleMinPower'][egs][p,sc,n] + optmodel.vEleTotalOutput2ndBlock[p,sc,n,egs]()) * model.Par['pDuration'][p,sc,n] for egs  in model.egs  if (nd,egs ) in model.n2eg and (gt,egs ) in model.t2eg)) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleGeneration' ).reset_index()
    OutputResults1a['Component'] = 'Production/Discharge [kWh]'
    OutputResults1a['EleGeneration'] *= (1/model.factor1)
    OutputResults1a = OutputResults1a.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults1a = OutputResults1a.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleGeneration', aggfunc='sum')
    # series of electricity consumption
    OutputResults2a = pd.Series(data=[-sum((optmodel.vEleStorCharge[p,sc,n,egs]() * model.Par['pEleMinCharge'][egs][p,sc,n] + optmodel.vEleTotalCharge2ndBlock[p,sc,n,egs]()) * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleConsumption').reset_index()
    OutputResults2a['Component'] = 'Consumption/Charge [kWh]'
    OutputResults2a['EleConsumption'] *= (1/model.factor1)
    OutputResults2a = OutputResults2a.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults2a = OutputResults2a.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleConsumption', aggfunc='sum')
    # series of FCR-D upwards
    OutputResults1b = pd.Series(data=[ sum(optmodel.vEleFreqContReserveDisUpwardBid[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDUp').reset_index()
    OutputResults1b['Component'] = 'FCR-D Upward [kWh]'
    OutputResults1b['EleFCRDUp'] *= (1/model.factor1)
    OutputResults1b = OutputResults1b.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults1b = OutputResults1b.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDUp', aggfunc='sum')
    # series of FCR-D downwards
    OutputResults2b = pd.Series(data=[-sum(optmodel.vEleFreqContReserveDisDownwardBid[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDDown').reset_index()
    OutputResults2b['Component'] = 'FCR-D Downward [kWh]'
    OutputResults2b['EleFCRDDown'] *= (1/model.factor1)
    OutputResults2b = OutputResults2b.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults2b = OutputResults2b.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDDown', aggfunc='sum')
    # series of FCR-D upwards when the battery is discharging
    OutputResults1c = pd.Series(data=[ sum(optmodel.vEleFreqContReserveDisUpDis[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDUpDis').reset_index()
    OutputResults1c['Component'] = 'FCR-D Upward Discharge [kWh]'
    OutputResults1c['EleFCRDUpDis'] *= (1/model.factor1)
    OutputResults1c = OutputResults1c.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults1c = OutputResults1c.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDUpDis', aggfunc='sum')
    # series of FCR-D downwards when the battery is discharging
    OutputResults1d = pd.Series(data=[-sum(optmodel.vEleFreqContReserveDisDownDis[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDDwDis').reset_index()
    OutputResults1d['Component'] = 'FCR-D Downward Discharge [kWh]'
    OutputResults1d['EleFCRDDwDis'] *= (1/model.factor1)
    OutputResults1d = OutputResults1d.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults1d = OutputResults1d.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDDwDis', aggfunc='sum')
    # series of FCR-D upwards when the battery is charging
    OutputResults2c = pd.Series(data=[ sum(optmodel.vEleFreqContReserveDisUpCha[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDUpChg').reset_index()
    OutputResults2c['Component'] = 'FCR-D Upward Charge [kWh]'
    OutputResults2c['EleFCRDUpChg'] *= (1/model.factor1)
    OutputResults2c = OutputResults2c.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults2c = OutputResults2c.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDUpChg', aggfunc='sum')
    # series of FCR-D downwards when the battery is charging
    OutputResults2d = pd.Series(data=[-sum(optmodel.vEleFreqContReserveDisDownCha[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleFCRDDwChg').reset_index()
    OutputResults2d['Component'] = 'FCR-D Downward Charge [kWh]'
    OutputResults2d['EleFCRDDwChg'] *= (1/model.factor1)
    OutputResults2d = OutputResults2d.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults2d = OutputResults2d.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleFCRDDwChg', aggfunc='sum')
    # series of electricity inventory
    OutputResults3 = pd.Series(data=[ sum(optmodel.vEleInventory[p,sc,n,egs]() for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleInventory').reset_index()
    OutputResults3['Component'] = 'Inventory [kWh]'
    OutputResults3['EleInventory'] *= (1/model.factor1)
    OutputResults3 = OutputResults3.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults3 = OutputResults3.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleInventory', aggfunc='sum')
    # series of ENS
    OutputResults4 = pd.Series(data=[ sum(optmodel.vENS[p,sc,n,ed]() * model.Par['pDuration'][p,sc,n] for ed in model.ed if (nd,ed) in model.n2ed) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='ENS').reset_index()
    OutputResults4['Component'] = 'ENS [kWh]'
    OutputResults4['ENS'] *= (1/model.factor1)
    OutputResults4 = OutputResults4.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults4 = OutputResults4.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='ENS', aggfunc='sum')
    # series of energy outflows
    OutputResults5 = pd.Series(data=[-sum(optmodel.vEleEnergyOutflows[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleEnergyOutflows').reset_index()
    OutputResults5['Component'] = 'Outflows/Driving [kWh]'
    OutputResults5['EleEnergyOutflows'] *= (1/model.factor1)
    OutputResults5 = OutputResults5.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults5 = OutputResults5.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleEnergyOutflows', aggfunc='sum')
    # series of load home
    OutputResults6 = pd.Series(data=[-sum(optmodel.vEleDemand[p,sc,n,ed]() * model.Par['pDuration'][p,sc,n] for ed in model.ed if (nd,ed) in model.n2ed) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleDemand').reset_index()
    OutputResults6['Component'] = 'Load/Home [kWh]'
    OutputResults6['EleDemand'] *= (1/model.factor1)
    OutputResults6 = OutputResults6.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults6 = OutputResults6.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleDemand', aggfunc='sum')
    # series of the electricity buy
    OutputResults7 = pd.Series(data=[ sum(optmodel.vEleBuy[p,sc,n,er]() * model.Par['pDuration'][p,sc,n] for er in model.er if (nd,er) in model.n2er) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleBuy').reset_index()
    OutputResults7['Component'] = 'Electricity Buy [kWh]'
    OutputResults7['EleBuy'] *= (1/model.factor1)
    OutputResults7 = OutputResults7.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults7 = OutputResults7.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleBuy', aggfunc='sum')
    # series of the electricity sell
    OutputResults8 = pd.Series(data=[-sum(optmodel.vEleSell[p,sc,n,er]() * model.Par['pDuration'][p,sc,n] for er in model.er if (nd,er) in model.n2er) for p,sc,n,nd in sPNND], index=pd.Index(sPNND)).to_frame(name='EleSell').reset_index()
    OutputResults8['Component'] = 'Electricity Sell [kWh]'
    OutputResults8['EleSell'] *= (1/model.factor1)
    OutputResults8 = OutputResults8.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 0: 'Value'}, inplace=False)
    OutputResults8 = OutputResults8.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Node'], values='EleSell', aggfunc='sum')
    # series of the spot price
    OutputResults9 = pd.Series(data=[  model.Par['pVarEnergyCost' ] [er][p,sc,n] for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults9['Component'] = 'Spot Price [EUR/kWh]'
    OutputResults9 = OutputResults9.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults9 = OutputResults9.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of the electricity cost
    OutputResults10 = pd.Series(data=[(model.Par['pVarEnergyCost'] [er][p,sc,n] * model.Par['pEleRetBuyingRatio'][er] + model.Par['pEleRetOverforingsavgift'][er] + model.Par['pEleRetPaslag'][er] + model.Par['pEleRetEnergyTax'][er]) for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults10['Component'] = 'EleCost [EUR/kWh]'
    OutputResults10['EUR/KWh'] *= (1/model.factor1)
    OutputResults10 = OutputResults10.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults10 = OutputResults10.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of the electricity price
    OutputResults11 = pd.Series(data=[  model.Par['pVarEnergyPrice'] [er][p,sc,n] * model.Par['pEleRetSellingRatio'][er] for p,sc,n,er in model.psner], index=pd.Index(model.psner)).to_frame(name='EUR/KWh').reset_index()
    OutputResults11['Component'] = 'ElePrice [EUR/kWh]'
    OutputResults11['EUR/KWh'] *= (1/model.factor1)
    OutputResults11 = OutputResults11.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Retailer', 0: 'Value'}, inplace=False)
    OutputResults11 = OutputResults11.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Retailer'], values='EUR/KWh', aggfunc='sum')
    # series of FixedAvailability
    OutputResults12 = pd.Series(data=[ sum(model.Par['pVarFixedAvailability'][egs][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='FixedAvailability').reset_index()
    OutputResults12['Component'] = 'Availability [0,1]'
    OutputResults12 = OutputResults12.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults12 = OutputResults12.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='FixedAvailability', aggfunc='sum')
    # series of spillage
    OutputResults13 = pd.Series(data=[ sum(optmodel.vEleSpillage[p,sc,n,egs]() * model.Par['pDuration'][p,sc,n] for egs in model.egs if (nd,egs) in model.n2eg and (gt,egs) in model.t2eg) for p,sc,n,nd,gt in sPNNDGT], index=pd.Index(sPNNDGT)).to_frame(name='EleSpillage').reset_index()
    OutputResults13['Component'] = 'Spillage [kWh]'
    OutputResults13['EleSpillage'] *= (1/model.factor1)
    OutputResults13 = OutputResults13.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 'level_3': 'Node', 'level_4': 'Technology', 0: 'Value'}, inplace=False)
    OutputResults13 = OutputResults13.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EleSpillage', aggfunc='sum')
    # series of FCR-D upwards prices
    OutputResults14 = pd.Series(data=[ model.Par['pOperatingReservePrice_FCRD_Up'][p,sc,n] for p,sc,n in model.psn], index=pd.Index(model.psn)).to_frame(name='EUR/kWh').reset_index()
    OutputResults14['Component'] = 'FCR-D Upward Price [EUR/kWh]'
    OutputResults14['Technology'] = ''
    OutputResults14['EUR/kWh'] *= (1/model.factor1)
    OutputResults14 = OutputResults14.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 0: 'Value'}, inplace=False)
    OutputResults14 = OutputResults14.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EUR/kWh', aggfunc='sum')
    # series of FCR-D downwards prices
    OutputResults15 = pd.Series(data=[ model.Par['pOperatingReservePrice_FCRD_Down'][p,sc,n] for p,sc,n in model.psn], index=pd.Index(model.psn)).to_frame(name='EUR/kWh').reset_index()
    OutputResults15['Component'] = 'FCR-D Downward Price [EUR/kWh]'
    OutputResults15['Technology'] = ''
    OutputResults15['EUR/kWh'] *= (1/model.factor1)
    OutputResults15 = OutputResults15.rename(columns={'level_0': 'Period', 'level_1': 'Scenario', 'level_2': 'LoadLevel', 0: 'Value'}, inplace=False)
    OutputResults15 = OutputResults15.pivot_table(index=['Period', 'Scenario', 'LoadLevel'], columns=['Component','Technology'], values='EUR/kWh', aggfunc='sum')

    if len(model.egs):
        if len(model.egv):
            OutputResults = pd.concat([OutputResults1a, OutputResults1c, OutputResults1d, OutputResults2a, OutputResults2c, OutputResults2d, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults12, OutputResults3, OutputResults5, OutputResults13, OutputResults14, OutputResults15, OutputResults9, OutputResults10, OutputResults11], axis=1)
        else:
            OutputResults = pd.concat([OutputResults1a, OutputResults2a, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults3, OutputResults15, OutputResults9, OutputResults10, OutputResults11], axis=1)
    else:
        OutputResults = pd.concat([OutputResults1a, OutputResults4, OutputResults6, OutputResults7, OutputResults8, OutputResults9, OutputResults10, OutputResults11], axis=1)
    OutputResults['Date'] = OutputResults.index.get_level_values(2).map(lambda x: Date + pd.Timedelta(hours=(int(x[1:]) - int(hour_of_year[1:])))).strftime('%Y-%m-%d %H:%M:%S')
    OutputResults = OutputResults.set_index('Date', append=True)
    OutputResults.index.names = [None, None, None, None]
    OutputResults.columns.names = [None, None]
    save_to_csv(OutputResults, _path, f'oM_Result_07_rEleOutputSummary_{CaseName}.csv', index=True)

    # -----------------------------------------------------------
    # 1) COLUMN SELECTION AND RENAMING
    # -----------------------------------------------------------

    rename_cols = {
        'Spot Price [EUR/kWh]': 'Price Spot',
        'EleCost [EUR/kWh]': 'Price Import',
        'FCR-D Upward Price [EUR/kWh]': 'Price FCR-D Upward',
        'FCR-D Downward Price [EUR/kWh]': 'Price FCR-D Downward',
        'Production/Discharge [kWh]': 'Discharge Day-Ahead',
        'FCR-D Upward Discharge [kWh]': 'Discharge FCR-D Upward',
        'FCR-D Downward Discharge [kWh]': 'Discharge FCR-D Downward',
        'Consumption/Charge [kWh]': 'Charge Day-Ahead',
        'FCR-D Upward Charge [kWh]': 'Charge FCR-D Upward',
        'FCR-D Downward Charge [kWh]': 'Charge FCR-D Downward'
    }

    keep_cols = list(rename_cols.keys())

    # Extract + flatten columns
    data = OutputResults[keep_cols]
    data.columns = data.columns.get_level_values(0)

    # Flatten index
    data = data.reset_index().rename(columns={'level_0': 'Period','level_1': 'Scenario','level_2': 'LoadLevel','level_3': 'Date'}).rename(columns=rename_cols)

    # Ensure datetime
    data['Date'] = pd.to_datetime(data['Date'])

    # -----------------------------------------------------------
    # 2) RESHAPE INTO LONG FORMAT
    # -----------------------------------------------------------

    bar_components = ['Discharge Day-Ahead', 'Charge Day-Ahead','Discharge FCR-D Upward', 'Discharge FCR-D Downward','Charge FCR-D Upward', 'Charge FCR-D Downward']

    line_components = ['Price Spot', 'Price Import','Price FCR-D Upward', 'Price FCR-D Downward']

    bar_data = data[['Date'] + bar_components].melt(id_vars='Date', var_name='Component', value_name='Value')
    line_data = data[['Date'] + line_components].melt(id_vars='Date', var_name='Component', value_name='Value')

    line_data_FCR = line_data[line_data['Component'].str.contains('FCR-D')]

    # -----------------------------------------------------------
    # 3) DATE WINDOW (FIRST 7 DAYS)
    # -----------------------------------------------------------
    start_date = data['Date'].min()
    end_date = start_date + pd.Timedelta(days=7)

    LabelSize = 16
    TitleSize = 18

    def filter_7d(df):
        return df[(df['Date'] >= start_date) & (df['Date'] < end_date)]

    bar_7d      = filter_7d(bar_data)
    line_7d     = filter_7d(line_data)
    line_FCR_7d = filter_7d(line_data_FCR)

    # -----------------------------------------------------------
    # 4) HELPER FUNCTIONS FOR PLOT BUILDING
    # -----------------------------------------------------------

    def make_bar_chart(df):
        return (alt.Chart(df)
                .mark_bar()
                .encode(
            x=alt.X('Date:T',axis=alt.Axis(title='',labelAngle=-90,format="%a, %b %d, %H:%M",tickCount=30,labelLimit=1000,labelFontSize=16,titleFontSize=18)),
            y=alt.Y('sum(Value):Q',axis=alt.Axis(title='[kWh]',labelFontSize=LabelSize,titleFontSize=TitleSize)),
            color=alt.Color('Component:N',scale=alt.Scale(scheme='category10'),legend=alt.Legend(title='', labelFontSize=LabelSize, titleFontSize=TitleSize)
            )
        ).properties(width=1200, height=400)
                )

    def make_line_chart(df):
        return (alt.Chart(df)
                .mark_line(strokeDash=[5, 5], point=alt.OverlayMarkDef(filled=False))
                .encode(
            x=alt.X('Date:T',axis=alt.Axis(title='',labelAngle=-90,format="%a, %b %d, %H:%M",tickCount=30,labelLimit=1000,labelFontSize=LabelSize,titleFontSize=TitleSize)),
            y=alt.Y('Value:Q',axis=alt.Axis(title='[SEK/kWh]',labelFontSize=LabelSize,titleFontSize=TitleSize)),
            color=alt.Color('Component:N',scale=alt.Scale(scheme='category10'),legend=alt.Legend(title='', labelFontSize=LabelSize, titleFontSize=TitleSize)
            )
        ).properties(width=1200, height=400)
                )

    def save_plot(chart, name):
        chart.save(f"{_path}/oM_Plot_06_{name}_{CaseName}.html",embed_options={"renderer": "svg"})

    # -----------------------------------------------------------
    # 5) BUILD & SAVE ALL CHARTS (NO DUPLICATION)
    # -----------------------------------------------------------

    # Full period
    save_plot(alt.layer(make_bar_chart(bar_data), make_line_chart(line_data)).resolve_scale(y='independent').interactive(),"rEleOutputSummary")

    save_plot(make_line_chart(line_data), "rEleOutputPrices")
    save_plot(make_line_chart(line_data_FCR), "rEleOutputFCRDPrices")

    # 7 days
    save_plot(alt.layer(make_bar_chart(bar_7d), make_line_chart(line_7d)).resolve_scale(y='independent').interactive(),"rEleOutputSummary_7days")

    save_plot(make_line_chart(line_7d), "rEleOutputPrices_7days")
    save_plot(make_line_chart(line_FCR_7d), "rEleOutputFCRDPrices_7days")

    # -----------------------------------------------------------
    # 1) COMPUTE NET POWER & FILTER OUT ZERO ROWS
    # -----------------------------------------------------------

    # Compute Net Power directly on the processed dataset
    data['NetPower'] = data['Discharge Day-Ahead'] - data['Charge Day-Ahead']

    # Filter out rows where NetPower = 0
    data_filtered = data[data['NetPower'] != 0].copy()
    # -----------------------------------------------------------
    # 2) HELPER FUNCTION FOR SCATTER PLOTS
    # -----------------------------------------------------------

    def make_scatter(df, x_field, y_field, x_title, y_title, color_field, tooltip_fields):
        return (
            alt.Chart(df)
            .mark_circle(size=70, opacity=0.6)
            .encode(
                x=alt.X(f'{x_field}:Q', axis=alt.Axis(title=x_title, labelFontSize=14, titleFontSize=16)),
                y=alt.Y(f'{y_field}:Q', axis=alt.Axis(title=y_title, labelFontSize=14, titleFontSize=16)),
                color=alt.Color(f'{color_field}:Q', scale=alt.Scale(scheme='redyellowgreen')),
                tooltip=tooltip_fields)
            .properties(width=700, height=500)
            .configure_title(fontSize=18)
        )

    scatter_discharge = make_scatter(data_filtered, x_field='Price Spot', y_field='Discharge Day-Ahead', x_title='Spot Price [SEK/kWh]', y_title='Discharge [kWh]', color_field='Discharge Day-Ahead', tooltip_fields=['Date:T', 'Price Spot:Q', 'Discharge Day-Ahead:Q'])
    scatter_discharge.save(f"{_path}/oM_Plot_07_rEleOutputScatter_{CaseName}.html", embed_options={'renderer': 'svg'})

    scatter_charge    = make_scatter(data_filtered, x_field='Price Import', y_field='Charge Day-Ahead', x_title='Import Price [SEK/kWh]', y_title='Charge [kWh]', color_field='Charge Day-Ahead', tooltip_fields=['Date:T', 'Price Import:Q', 'Charge Day-Ahead:Q'])

    scatter_charge.save(f"{_path}/oM_Plot_07_rEleChargeScatter_{CaseName}.html", embed_options={'renderer': 'svg'})

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

    log_time('-- Sankey diagrams output time:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # Duration curve of the EV total output and the total charge
    EV_TotalOutput = pd.Series(data=[sum(optmodel.vEleTotalOutput[p,sc,n,egv]() for egv in model.egv) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EV_TotalCharge = pd.Series(data=[sum(optmodel.vEleTotalCharge[p,sc,n,egs]() for egs in model.egs) for p,sc,n in model.psn], index=pd.MultiIndex.from_tuples(model.psn))
    EV_NetCharge = EV_TotalCharge - EV_TotalOutput
    
    create_and_save_duration_curve(
        series_data=EV_NetCharge.values,
        index_tuples=model.psn,
        value_col_name='NetCharge',
        Date=Date,
        hour_of_year=hour_of_year,
        path=_path,
        csv_filename=f'oM_Result_10_rDurationCurve_NetCharge_{CaseName}.csv',
        html_filename=f'oM_Plot_rDurationCurve_NetCharge_{CaseName}.html',
        title='Duration Curve of the Charge and Discharge of the EV',
        y_label='Charge and discharge [KWh]'
    )

    log_time('-- Duration curves of the net charge output time:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # Duration curve of the Solar PV total output
    SolarPV_data = [sum(optmodel.vEleTotalOutput[p,sc,n,egr]() for egr in model.egr) for p,sc,n in model.psn]
    create_and_save_duration_curve(
        series_data=SolarPV_data,
        index_tuples=model.psn,
        value_col_name='TotalOutput',
        Date=Date,
        hour_of_year=hour_of_year,
        path=_path,
        csv_filename=f'oM_Result_11_rDurationCurve_TotalOutput_{CaseName}.csv',
        html_filename=f'oM_Plot_rDurationCurve_TotalOutput_{CaseName}.html',
        title='Duration Curve of the Total Output of the Solar PV',
        y_label='Total Output [KWh]'
    )

    log_time('-- Duration curves of electricity production output time:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # Duration curve of the electricity demand
    EleDemand_data = [sum(optmodel.vEleDemand[p,sc,n,ed]() for ed in model.ed) for p,sc,n in model.psn]
    create_and_save_duration_curve(
        series_data=EleDemand_data,
        index_tuples=model.psn,
        value_col_name='Demand',
        Date=Date,
        hour_of_year=hour_of_year,
        path=_path,
        csv_filename=f'oM_Result_12_rDurationCurve_Demand_{CaseName}.csv',
        html_filename=f'oM_Plot_rDurationCurve_Demand_{CaseName}.html',
        title='Duration Curve of the Demand',
        y_label='Demand [KWh]'
    )

    log_time('-- Duration curves of the electricity demand output time:', StartTime, ind_log=indlog)
    StartTime = time.time()

    # Duration curve of the electricity bought from the market
    EleBuy_data = [sum(optmodel.vEleBuy[p,sc,n,er]() for er in model.er) for p,sc,n in model.psn]
    create_and_save_duration_curve(
        series_data=EleBuy_data,
        index_tuples=model.psn,
        value_col_name='Buy',
        Date=Date,
        hour_of_year=hour_of_year,
        path=_path,
        csv_filename=f'oM_Result_13_rDurationCurve_EleBuy_{CaseName}.csv',
        html_filename=f'oM_Plot_rDurationCurve_EleBuy_{CaseName}.html',
        title='Duration Curve of the Buy',
        y_label='Buy [KWh]'
    )

    log_time('-- Duration curves of the electricity bought output time:',StartTime)
    StartTime = time.time()

    # Duration curve of the electricity sold to the market
    EleSell_data = [sum(optmodel.vEleSell[p,sc,n,er]() for er in model.er) for p,sc,n in model.psn]
    create_and_save_duration_curve(
        series_data=EleSell_data,
        index_tuples=model.psn,
        value_col_name='Sell',
        Date=Date,
        hour_of_year=hour_of_year,
        path=_path,
        csv_filename=f'oM_Result_14_rDurationCurve_EleSell_{CaseName}.csv',
        html_filename=f'oM_Plot_rDurationCurve_EleSell_{CaseName}.html',
        title='Duration Curve of the Sell',
        y_label='Sell [KWh]'
    )

    log_time('-- Duration curves of the electricity sold output time:', StartTime, ind_log=indlog)

    return model