Results and post-processing
===========================

After a successful optimization run, the model post-processes the solution and saves the
results. By default they go to ``<dir>/<case>/results.duckdb`` (one table per set,
parameter, variable and constraint dual, plus an ``oM_Result_RunMetadata`` table), via
``oM_OutputData_duckdb.save_to_duckdb``. Pass ``--rawresults True`` to also write the CSV
result tables (``saving_results`` in ``oM_OutputData``), each prefixed ``oM_Result_``, and
``--plots True`` for the HTML figures.

.. graphviz::
   :align: center
   :alt: A solved model is written to results.duckdb by default, and to CSV result files and HTML plots on request.

   digraph results {
     graph [rankdir=LR, nodesep=0.2, ranksep=0.5, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#ffffff", color="#888888"];
     edge  [color="#555555", arrowsize=0.7, fontname="Helvetica", fontsize=9];
     model [label="Solved model", fillcolor="#e1bee7", color="#6a1b9a"];
     db    [label="results.duckdb (default)\none table per set (eg, n, ...), parameter (p...),\nvariable (v...) and constraint dual (<name>_dual),\nplus oM_Result_RunMetadata", fillcolor="#fdecea", color="#c62828"];
     csv   [label="oM_Result_*.csv\ncost breakdown, balances, state of\nenergy, summaries (--rawresults True)"];
     plot  [label="oM_Plot_*.html\nbalance, demand, state of energy,\nSankey, duration curves (--plots True)"];
     model -> db [label="--duckdbresults True"];
     model -> csv; model -> plot;
   }

.. note::

   When a case uses the heat sector, the investment layer or the energy community, their
   decisions are saved too: the heat balance, the candidate build fractions and
   investment cost, and the community sharing. The DuckDB output carries every variable,
   so these appear there even when the curated CSV/plot set focuses on electricity.

With ``--rawresults True`` the model also writes CSV files, each prefixed with
``oM_Result_``. The main ones are listed below; the DuckDB file holds the same results and more.

Key output files
----------------

The main CSV files are:

*   ``oM_Result_01_rTotalCost_...``: This file provides a breakdown of the total system costs. It comes in two forms:
    *   ``Hourly``: Shows the costs (market, generation, emissions, etc.) for each timestep.
    *   ``General``: Shows the total costs aggregated for each period and scenario.

*   ``oM_Result_02_rElectricityBalance_...``: This is a crucial output for understanding the physical operation of the system. It details the energy balance, in the energy unit of the case, at every node for every timestep, showing the contribution of each component (generation, consumption, flows).

*   ``oM_Result_05_rEleStateOfEnergy_...``: This file tracks the state of energy (or state of charge) for all electricity storage assets over time, making it easy to analyze how batteries and other storage devices are being used.

*   ``oM_Result_07_rEleOutputSummary_...``: A wide-format summary file that aggregates many key results into a single table. It includes production/discharge, consumption/charge, inventory levels, prices, and the availability status of assets for each timestep.

*   ``oM_Result_08_rEnergyBalance_...``: This file contains the aggregated energy flow data used to generate the Sankey diagrams. It shows the total energy transferred between major system components (e.g., from Solar PV to the demand, or from the grid to an EV).

Visualizations
--------------

In addition to the raw data, the model generates several interactive plots saved as HTML files, which can be opened in any web browser:

*   ``oM_Plot_rElectricityBalance_...``: A stacked bar chart visualizing the electricity balance over time.
*   ``oM_Plot_rEleDemand_...``: A line chart showing the original and net electricity demand, overlaid with the electricity price.
*   ``oM_Plot_rEleStateOfEnergy_...``: A line chart showing the state of energy for storage assets, often overlaid with their availability status.
*   ``oM_Plot_rSankey_...``: Sankey diagrams illustrating the energy flows between different parts of the system for each period.
*   ``oM_Plot_rDurationCurve_...``: A series of duration curves for key metrics like demand, generation, and market interaction, showing the number of hours a certain value is met or exceeded.

These files provide a solid foundation for understanding the optimization results, from high-level economic summaries down to the detailed operational behavior of individual assets.