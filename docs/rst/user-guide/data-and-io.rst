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

.. graphviz::
   :align: center
   :alt: A case holds oM_Dict lists, oM_Data unit tables, time series and single-row tables; the lists and unit tables give the sets, and the data tables give the parameters.

   digraph files {
     graph [rankdir=LR, nodesep=0.2, ranksep=0.5, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#ffffff", color="#888888"];
     edge  [color="#555555", arrowsize=0.7];
     case  [label="Case\nCSV folder or one .duckdb file", fillcolor="#e8f5e9", color="#2e7d32"];
     dict  [label="oM_Dict_*\nlists: nodes, units, periods,\nscenarios, load levels, mappings"];
     unit  [label="oM_Data_* unit tables\none row per unit, demand,\nretailer or line"];
     ts    [label="oM_Data_* time series\none row per period, scenario\nand load level"];
     one   [label="oM_Data_Option, oM_Data_Parameter\none row of settings"];
     sets  [label="Sets\n(model.eg, model.n, ...)", fillcolor="#e1bee7", color="#6a1b9a"];
     par   [label="Parameters\n(model.Par)", fillcolor="#e1bee7", color="#6a1b9a"];
     case -> {dict unit ts one};
     dict -> sets; unit -> sets [style=dashed, label=" columns decide\n the unit sets", fontsize=8, fontname="Helvetica"];
     {unit ts one} -> par;
   }

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

These files hold the numbers. There are three layouts:

- **Unit tables**, one row per unit, demand, retailer or line, and one column per attribute
  (for example ``Node``, ``MaximumPower``, ``StorageType``).
- **Time series**, one row per period, scenario and load level, and one column per unit,
  demand or retailer.
- **Single-row tables** (``Option`` and ``Parameter``), one column per setting.

Unit tables
"""""""""""

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Content
   * - ``oM_Data_ElectricityGeneration``
     - One row per electricity unit (generator, battery, EV, fuel cell): node, retailer,
       technology, capacities, efficiencies, storage type, costs, investment and FCR settings.
   * - ``oM_Data_HydrogenGeneration``
     - One row per hydrogen unit (electrolyser, hydrogen store, compressor). A compressor row
       names its outlet node in ``DischargeNode``.
   * - ``oM_Data_ElectricityDemand`` / ``oM_Data_HydrogenDemand``
     - One row per demand: node, retailer, whether it is flexible, and its period window.
   * - ``oM_Data_ElectricityRetail`` / ``oM_Data_HydrogenRetail``
     - One row per retailer: node, whether it buys or sells, energy limits, and the tariff
       terms.
   * - ``oM_Data_ElectricityNetwork`` / ``oM_Data_HydrogenNetwork``
     - One row per line or pipe, indexed by from-node, to-node and circuit: capacity, length,
       losses, reactance and investment data.
   * - ``oM_Data_NodeLocation``
     - Latitude and longitude of each node, used to compute line lengths.
   * - ``oM_Data_Period``
     - The weight of each period.
   * - ``oM_Data_Scenario``
     - The probability of each scenario in each period.

Time series
"""""""""""

Every time series has one row per period, scenario and load level. In the per-unit series
(``VarMin*`` and ``VarMax*``), a zero or blank cell falls back to the unit's constant value in
its unit table.

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Content
   * - ``oM_Data_Duration``
     - The duration of each load level in hours. A load level with a zero or blank duration
       is left out of the model.
   * - ``oM_Data_VarMaxDemand`` / ``oM_Data_VarMinDemand``
     - The demand of each electricity and hydrogen demand, per load level.
   * - ``oM_Data_VarMaxGeneration`` / ``oM_Data_VarMinGeneration``
     - The maximum and minimum output of each unit (for example a solar profile).
   * - ``oM_Data_VarMaxConsumption`` / ``oM_Data_VarMinConsumption``
     - The maximum and minimum charge or consumption of each unit.
   * - ``oM_Data_VarMaxStorage`` / ``oM_Data_VarMinStorage``
     - The maximum and minimum stored energy of each store.
   * - ``oM_Data_VarMaxInflows`` / ``oM_Data_VarMinInflows``
     - Energy flowing into a store from outside the model, such as natural inflows.
   * - ``oM_Data_VarMaxOutflows`` / ``oM_Data_VarMinOutflows``
     - Energy leaving a store outside the model, such as the driving use of an EV.
   * - ``oM_Data_VarMaxFuelCost`` / ``oM_Data_VarMinFuelCost``
     - The variable cost of each unit, per load level.
   * - ``oM_Data_VarMaxEmissionCost`` / ``oM_Data_VarMinEmissionCost``
     - The emission cost of each unit, per load level.
   * - ``oM_Data_VarFixedAvailability``
     - The availability of a store (1 available, 0 not), used only for units with
       ``FixedAvailability`` set. At 0 the store can neither charge nor discharge, as for an
       EV that is not plugged in.
   * - ``oM_Data_VarEnergyCost`` / ``oM_Data_VarEnergyPrice``
     - The buying and selling price of each retailer, per load level.
   * - ``oM_Data_OperatingReservePrice``
     - The FCR-D and FCR-N capacity prices, per product (``FCRD_Up``, ``FCRD_Down``,
       ``FCRN_Up``, ``FCRN_Down``).
   * - ``oM_Data_OperatingReserveRequire``
     - The FCR volume the market buys, per product. The bids of all units together stay
       below it.
   * - ``oM_Data_OperatingReserveActivation``
     - The expected share of each FCR product that is activated, per load level.
   * - ``oM_Data_VarMaxEnergy`` / ``oM_Data_VarMinEnergy``,
       ``oM_Data_VarPositionGeneration`` / ``oM_Data_VarPositionConsumption`` /
       ``oM_Data_VarPositionOutflows``, ``oM_Data_Tariff``
     - Read but not used by the current formulation. The ``VarMaxEnergy``, ``VarMinEnergy``
       and two ``VarPosition*`` series must still be present, and may be empty.

Single-row tables
"""""""""""""""""

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Content
   * - ``oM_Data_Option``
     - The option flags, for example unit commitment, ramps or investment. The flags and
       their defaults are listed in :doc:`../concepts/features-and-modes`.
   * - ``oM_Data_Parameter``
     - The global settings: costs of energy not served, discount rate, reference nodes, time
       step, load-level length (``LoadLevelMinutes``), unit scale (``Factor1``), money scale
       (``MoneyBase``) and others.

Optional tables
"""""""""""""""

These are read only when present, so a case without them is unchanged.

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Content
   * - ``oM_Data_SeriesResolution``
     - The resolution of a time-series file that is given at its own resolution, for example
       ``OperatingReservePrice,uniform 1h``. See :doc:`../concepts/time-structure`.
   * - ``oM_Data_Resolution``
     - A declared resolution per unit, flow or inventory (time blocks). See
       :doc:`../concepts/time-structure`.
   * - ``oM_Data_HeatGeneration``, ``oM_Data_HeatDemand``, ``oM_Data_VarMaxHeatDemand``
     - The heat sector. See :doc:`../concepts/heat-sector`.

From an input file to a model parameter
---------------------------------------

``data_processing`` turns the tables into the parameters of the model (``model.Par``) in a
fixed order. Knowing it explains two things that surprise new users: a blank cell in a time
series is not zero, and the numbers in ``model.Par`` are not always the numbers in the files.

.. graphviz::
   :align: center
   :alt: The steps from the input tables to the model parameters.

   digraph inputs {
     graph [rankdir=TB, nodesep=0.3, ranksep=0.25, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#4a6fa5",
            fontname="Helvetica", fontsize=11, width=4.6];
     edge  [color="#4a6fa5", arrowsize=0.7];
     read  [label="Read every oM_Dict and oM_Data table\n(blank numbers become 0)", fillcolor="#e8f5e9", color="#2e7d32"];
     res   [label="Resample time series given at their own resolution\nonto the load levels (oM_Data_SeriesResolution)"];
     money [label="Divide money values by MoneyBase"];
     f1    [label="Scale by Factor1: quantities times Factor1,\nprices divided by Factor1"];
     keep  [label="Keep the load levels with a positive duration"];
     fill  [label="A zero time-series cell takes the unit's constant\nfrom its unit table"];
     par   [label="model.Par: the parameters the constraints use", fillcolor="#f3e5f5", color="#6a1b9a"];
     read -> res -> money -> f1 -> keep -> fill -> par;
   }

- **Zero and blank cells.** A blank number is read as 0, and a zero in a per-unit time series
  (``VarMax*`` and ``VarMin*``) is replaced by the unit's constant value. So a zero cell does not
  switch a unit off; give a small positive value, or set the unit's constant, to do that.
- **Scaling.** ``Factor1`` and ``MoneyBase`` are set in ``oM_Data_Parameter`` and are 1 by
  default. They change the size of the numbers the solver sees, for better numerical
  conditioning, and leave the optimal decisions unchanged. ``results.duckdb`` holds the values
  as the solver sees them: when the two are not 1, divide quantities by ``Factor1`` and multiply
  money by ``MoneyBase`` to get back to the units of the input files. The CSV result tables
  divide quantities by ``Factor1`` already.

Loaders
-------
.. autofunction:: el1xr_opt.Modules.oM_LoadCase.load_case
    :no-index:

Writers
-------
.. automodule:: el1xr_opt.Modules.oM_OutputData
    :members: saving_rawdata, saving_results
    :no-index:
