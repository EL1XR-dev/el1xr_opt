Data & I/O
==========

Data formats
------------
The model is data-driven. A case is supplied either as a **folder of CSV files** or as a
**single ``.duckdb`` file** holding the same tables. Both are read through one common
interface (``open_source`` / ``resolve_source``), so a DuckDB run reproduces a CSV run
exactly. If both the CSV folder and the ``.duckdb`` file are present, the folder is used.
Convert a CSV case to DuckDB with::

    el1xr-csv2duckdb --dir data/EEM26 --case Home1   # writes data/EEM26/Home1.duckdb

The tables define the model's sets (periods, technologies, nodes, ...) and parameters
(costs, capacities, efficiencies, ...).

Outputs
~~~~~~~

Results are written to ``<dir>/<case>/results.duckdb`` by default -- one table per set,
parameter, variable and constraint dual, plus an ``oM_Result_RunMetadata`` table. Pass
``--rawresults True`` to also write the CSV result tables, and ``--plots True`` for the
figures. Turn the DuckDB output off with ``--duckdbresults False``.

Heat tables
~~~~~~~~~~~

A heat-bearing case adds ``oM_Dict_HeatGeneration`` / ``oM_Data_HeatGeneration`` (with a
``Type`` column -- HeatPump / Boiler / Heat2Ele / Storage), ``oM_Data_HeatDemand`` and
``oM_Data_VarMaxHeatDemand``. They are read only when present, so electricity/hydrogen
cases are unaffected. See :doc:`../concepts/heat-sector`.

CSV File Naming Conventions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The input CSV files follow a specific naming convention to distinguish between
different types of data:

- **``oM_Dict...``**: Files starting with this prefix are used to define the model's
  sets and dictionaries. These typically contain lists of technologies, nodes,
  or other categorical data.

- **``oM_Data...``**: Files starting with this prefix contain the numerical data
  for the model's parameters, such as costs, efficiencies, or time series data.

This convention helps in organizing the input data and is used by the data loading
functions to correctly process the files.

CSV File Descriptions
~~~~~~~~~~~~~~~~~~~~~

The following sections provide a more detailed description of the ``oM_Dict...``
and ``oM_Data...`` CSV files.

oM_Dict Files
"""""""""""""

These files define the sets and dictionaries used in the optimization model.
Each file corresponds to a specific set, and the rows of the CSV file define
the elements of that set.

.. list-table:: oM_Dict Files
   :widths: 25 75
   :header-rows: 1

   * - File
     - Description
   * - ``oM_Dict_Node_Home1.csv``
     - Defines the nodes in the network. Each row represents a node. The
       relevant column is ``Node``.
   * - ``oM_Dict_Technology_Home1.csv``
     - Defines the technologies available in the model. Each row represents a
       technology. The relevant column is ``Technology``.
   * - ``oM_Dict_Area_Home1.csv``
     - Defines the geographical areas. The relevant column is ``Area``.
   * - ``oM_Dict_Region_Home1.csv``
     - Defines the geographical regions. The relevant column is ``Region``.
   * - ``oM_Dict_Zone_Home1.csv``
     - Defines the geographical zones. The relevant column is ``Zone``.
   * - ``oM_Dict_Period_Home1.csv``
     - Defines the time periods. The relevant column is ``Period``.
   * - ``oM_Dict_Scenario_Home1.csv``
     - Defines the scenarios. The relevant column is ``Scenario``.
   * - ``oM_Dict_LoadLevel_Home1.csv``
     - Defines the load levels. The relevant column is ``LoadLevel``.
   * - ``oM_Dict_Storage_Home1.csv``
     - Defines the storage technologies. The relevant column is ``Storage``.
   * - ``oM_Dict_Circuit_Home1.csv``
     - Defines the electrical circuits. The relevant column is ``Circuit``.
   * - ``oM_Dict_ElectricityDemand_Home1.csv``
     - Defines the electricity demand categories. The relevant column is
       ``ElectricityDemand``.
   * - ``oM_Dict_ElectricityGeneration_Home1.csv``
     - Defines the electricity generation categories. The relevant column is
       ``ElectricityGeneration``.
   * - ``oM_Dict_ElectricityRetail_Home1.csv``
     - Defines the electricity retail categories. The relevant column is
       ``ElectricityRetail``.
   * - ``oM_Dict_HydrogenDemand_Home1.csv``
     - Defines the hydrogen demand categories. The relevant column is
       ``HydrogenDemand``.
   * - ``oM_Dict_HydrogenGeneration_Home1.csv``
     - Defines the hydrogen generation categories. The relevant column is
       ``HydrogenGeneration``.
   * - ``oM_Dict_HydrogenRetail_Home1.csv``
     - Defines the hydrogen retail categories. The relevant column is
       ``HydrogenRetail``.
   * - ``oM_Dict_AreaToRegion_Home1.csv``
     - Maps areas to regions. The relevant columns are ``Area`` and ``Region``.
   * - ``oM_Dict_ZoneToArea_Home1.csv``
     - Maps zones to areas. The relevant columns are ``Zone`` and ``Area``.
   * - ``oM_Dict_NodeToZone_Home1.csv``
     - Maps nodes to zones. The relevant columns are ``Node`` and ``Zone``.

oM_Data Files
"""""""""""""

These files contain the numerical data for the model's parameters. This includes
time series data, costs, efficiencies, and other parameters that define the
behavior of the model.

.. list-table:: oM_Data Files
   :widths: 35 65
   :header-rows: 1

   * - File
     - Description
   * - ``oM_Data_Duration_Home1.csv``
     - Specifies the duration of each time step.
   * - ``oM_Data_ElectricityDemand_Home1.csv``
     - Time series data for electricity demand. Columns: ``Period``, ``Scenario``, ``LoadLevel``, value.
   * - ``oM_Data_ElectricityGeneration_Home1.csv``
     - Parameters for electricity generation technologies (e.g., capacity). Columns: ``Technology``, parameter values.
   * - ``oM_Data_ElectricityNetwork_Home1.csv``
     - Data for the electricity network, like line capacities.
   * - ``oM_Data_ElectricityRetail_Home1.csv``
     - Data related to electricity retail.
   * - ``oM_Data_HydrogenDemand_Home1.csv``
     - Time series data for hydrogen demand.
   * - ``oM_Data_HydrogenGeneration_Home1.csv``
     - Parameters for hydrogen generation technologies.
   * - ``oM_Data_HydrogenNetwork_Home1.csv``
     - Data for the hydrogen network.
   * - ``oM_Data_HydrogenRetail_Home1.csv``
     - Data related to hydrogen retail.
   * - ``oM_Data_NodeLocation_Home1.csv``
     - Defines the geographical location (e.g., latitude, longitude) of nodes.
   * - ``oM_Data_OperatingReserveActivation_Home1.csv``
     - Cost or activation data for operating reserves.
   * - ``oM_Data_OperatingReservePrice_Home1.csv``
     - Prices for operating reserves.
   * - ``oM_Data_OperatingReserveRequire_Home1.csv``
     - Requirements for operating reserves.
   * - ``oM_Data_Option_Home1.csv``
     - Contains various modeling options and flags.
   * - ``oM_Data_Parameter_Home1.csv``
     - Defines global parameters like costs, discount rates, and time steps.
   * - ``oM_Data_Period_Home1.csv``
     - Defines the characteristics of each period, like duration.
   * - ``oM_Data_Scenario_Home1.csv``
     - Provides scenario-specific data, such as probabilities.
   * - ``oM_Data_Tariff_Home1.csv``
     - Contains electricity tariff data.
   * - ``oM_Data_VarEnergyCost_Home1.csv``
     - Variable costs associated with energy.
   * - ``oM_Data_VarEnergyPrice_Home1.csv``
     - Variable prices for energy.
   * - ``oM_Data_VarMaxConsumption_Home1.csv``
     - Upper bounds for consumption variables.
   * - ``oM_Data_VarMaxDemand_Home1.csv``
     - Upper bounds for demand variables.
   * - ``oM_Data_VarMaxEmissionCost_Home1.csv``
     - Upper bounds for emission cost variables.
   * - ``oM_Data_VarMaxEnergy_Home1.csv``
     - Upper bounds for energy variables.
   * - ``oM_Data_VarMaxFuelCost_Home1.csv``
     - Upper bounds for fuel cost variables.
   * - ``oM_Data_VarMaxGeneration_Home1.csv``
     - Upper bounds for generation variables.
   * - ``oM_Data_VarMaxInflows_Home1.csv``
     - Upper bounds for inflow variables.
   * - ``oM_Data_VarMaxOutflows_Home1.csv``
     - Upper bounds for outflow variables.
   * - ``oM_Data_VarMaxStorage_Home1.csv``
     - Upper bounds for storage variables (e.g., max capacity). Columns: ``Storage``, ``Node``, value.
   * - ``oM_Data_VarMinConsumption_Home1.csv``
     - Lower bounds for consumption variables.
   * - ``oM_Data_VarMinDemand_Home1.csv``
     - Lower bounds for demand variables.
   * - ``oM_Data_VarMinEmissionCost_Home1.csv``
     - Lower bounds for emission cost variables.
   * - ``oM_Data_VarMinEnergy_Home1.csv``
     - Lower bounds for energy variables.
   * - ``oM_Data_VarMinFuelCost_Home1.csv``
     - Lower bounds for fuel cost variables.
   * - ``oM_Data_VarMinGeneration_Home1.csv``
     - Lower bounds for generation variables.
   * - ``oM_Data_VarMinInflows_Home1.csv``
     - Lower bounds for inflow variables.
   * - ``oM_Data_VarMinOutflows_Home1.csv``
     - Lower bounds for outflow variables.
   * - ``oM_Data_VarMinStorage_Home1.csv``
     - Lower bounds for storage variables.
   * - ``oM_Data_VarPositionConsumption_Home1.csv``
     - Position data for consumption variables.
   * - ``oM_Data_VarPositionGeneration_Home1.csv``
     - Position data for generation variables.
   * - ``oM_Data_VarPositionOutflows_Home1.csv``
     - Position data for outflow variables.
   * - ``oM_Data_VarShutDown_Home1.csv``
     - Costs or parameters for shutting down units.
   * - ``oM_Data_VarStartUp_Home1.csv``
     - Costs or parameters for starting up units.

Loaders
-------
.. autofunction:: el1xr_opt.Modules.oM_LoadCase.load_case
    :no-index:

Writers
-------
.. automodule:: el1xr_opt.Modules.oM_OutputData
    :members: saving_rawdata, saving_results
    :no-index:
