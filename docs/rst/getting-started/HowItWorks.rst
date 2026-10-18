Overview of el1xr_opt
=====================

This page explains what the model represents and what happens when it runs, before the
equations. The rest of the documentation goes into detail: the :doc:`../user-guide/data-and-io`
page for the inputs, and the Concepts pages for the formulation.

Decisions of the model
----------------------

el1xr_opt finds the cheapest way to operate an energy system over a set of time steps, called
load levels. For each load level it decides:

- how much electricity or hydrogen to buy from or sell to the market, through a retailer;
- how much each unit produces or consumes: generators, electrolysers, fuel cells, heat pumps;
- how much each store charges or discharges: batteries, EVs, hydrogen tanks, heat stores;
- how much reserve capacity (FCR-N and FCR-D) each unit offers;
- optionally, how much of each candidate unit to build.

The cost it minimises adds up market purchases, network tariffs, taxes, fuel and operating
costs, degradation, the cost of any demand left unserved and, when there are candidates,
investment. Sales and reserve payments count as revenues.

The system
----------

A case describes a set of **nodes** joined by electricity lines and hydrogen pipes. At each
node sit **units**, **demands** and **retailers**. A retailer is the link to a market and to
the network tariffs. Electricity, hydrogen and heat are coupled through the units that convert
one into another: an electrolyser turns electricity into hydrogen, a fuel cell does the
reverse, and a heat pump turns electricity into heat.

.. figure:: /../img/System.png
   :width: 90%
   :align: center
   :alt: Electricity generation, transmission, power-to-hydrogen, hydrogen storage, hydrogen demand and exports, grid storage, domestic supply with homes and an EV, and commercial and industrial users, joined by electricity and hydrogen flows.

   The kind of system el1xr_opt models: electricity and hydrogen production, storage,
   networks and demand, from a single home to a hydrogen valley.

At every node and load level, the energy that arrives must equal the energy that leaves.
These balances, one per energy carrier, tie the whole model together; the
:doc:`../concepts/constraints` page starts with a map of them.

From case to results, step by step
----------------------------------

el1xr_opt reads a case, builds the optimisation model in Pyomo, solves it and writes the results.

.. graphviz::
   :align: center
   :alt: The steps from the case files to the results.

   digraph run {
     graph [rankdir=TB, nodesep=0.3, ranksep=0.25, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#4a6fa5",
            fontname="Helvetica", fontsize=11, width=5.0];
     edge  [color="#4a6fa5", arrowsize=0.7];
     case   [label="Case: a folder of CSV files or one .duckdb file", fillcolor="#e8f5e9", color="#2e7d32"];
     load   [label="el1xr-run or load_case(): gather the options"];
     data   [label="data_processing: read the tables, build the sets and parameters"];
     vars   [label="create_variables: one variable per decision and load level"];
     layers [label="optional layers: community, investment, heat sector"];
     obj    [label="objective: costs minus revenues"];
     cons   [label="constraints: balances, unit limits, markets, reserves, storage"];
     extra  [label="community sharing and green-hydrogen matching"];
     solve  [label="solving_model: HiGHS, Gurobi, CBC or CPLEX", fillcolor="#f3e5f5", color="#6a1b9a"];
     out    [label="results.duckdb (and CSV files and plots on request)", fillcolor="#fdecea", color="#c62828"];
     case -> load -> data -> vars -> layers -> obj -> cons -> extra -> solve -> out;
   }

The steps follow ``build_model`` and ``routine`` in ``oM_Sequence``:

1. ``data_processing`` reads every table of the case and builds the sets (nodes, units, load
   levels) and the parameters. :doc:`../user-guide/data-and-io` shows how an input value
   becomes a parameter.
2. ``create_variables`` declares the decisions and their bounds.
3. The optional layers add their own variables: the energy community, the investment
   decisions for candidate units, and the heat sector. Each one is skipped when the case does
   not use it.
4. The objective adds up the costs and revenues; the constraints keep every decision within
   physics, unit limits and market rules.
5. ``solving_model`` passes the model to the solver.
6. The results are written to ``results.duckdb`` in the case folder; see
   :doc:`../concepts/results-and-postprocessing`.

The modules
-----------

The same steps, seen by module: from the input files, through the model formulation and the
solver, to the results.

.. figure:: /../img/el1xr_opt_architecture.svg
   :width: 90%
   :align: center
   :alt: The el1xr_opt modules in layers: input, source, data, model, solve and output, with the decoupled network analysis.

   The modules of el1xr_opt, from a CSV case folder or a ``.duckdb`` file to the results.

Further reading
---------------

- To solve a first case: :doc:`Quickstart`, then :doc:`../user-guide/examples`.
- To build a new case: :doc:`../user-guide/data-and-io`.
- To read the formulation: :doc:`../concepts/constraints` and
  :doc:`../concepts/objective-function`.
- To contribute: :doc:`../developer/contributing`.
