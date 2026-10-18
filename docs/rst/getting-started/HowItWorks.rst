Overview of el1xr_opt
=====================

This page describes the energy system that el1xr_opt represents and the sequence from a
case to its results, ahead of the formulation. The inputs are described in
:doc:`../user-guide/data-and-io`, and the equations in the Concepts pages.

Model decisions
---------------

el1xr_opt determines the least-cost operation of an energy system, and optionally its
investment, over a set of time steps called load levels. At each load level the model
decides:

- the electricity and hydrogen bought from and sold to the market, through a retailer;
- the output or consumption of each generating unit, electrolyser, fuel cell and heat pump;
- the charge and discharge of each store: batteries, electric vehicles (EVs), hydrogen
  tanks and heat stores;
- the reserve capacity (FCR-N and FCR-D) offered by each unit;
- optionally, the share of each candidate unit that is built.

The objective is the total cost: market purchases, network tariffs, taxes, fuel and
operating costs, degradation, the cost of unserved demand and, when the case has
candidates, investment. Sales and reserve remuneration enter as revenues.

System representation
---------------------

A case consists of **nodes** joined by electricity lines and hydrogen pipelines. Each node
holds **units**, **demands** and **retailers**. A retailer connects the node to a market and
carries the network tariffs. Electricity, hydrogen and heat are coupled by the units that
convert one carrier into another: an electrolyser converts electricity into hydrogen, a fuel
cell converts hydrogen into electricity, and a heat pump converts electricity into heat.

.. figure:: /../img/System.png
   :width: 90%
   :align: center
   :alt: Electricity generation, transmission, power-to-hydrogen, hydrogen storage, hydrogen demand and exports, grid storage, domestic supply with homes and an EV, and commercial and industrial users, joined by electricity and hydrogen flows.

   Energy system represented by el1xr_opt: electricity and hydrogen production, storage,
   networks and demand, at scales from a single home to a hydrogen valley.

At every node and load level, the energy supplied equals the energy consumed. These
balances, one per carrier, couple all the units of the model; the map at the top of
:doc:`../concepts/constraints` shows which units enter each balance.

Solution sequence
-----------------

el1xr_opt reads a case, builds the optimisation model in Pyomo, solves it and writes the
results.

.. graphviz::
   :align: center
   :alt: The sequence from the case files to the results: options, input data, variables, optional layers, objective, constraints, solver and results.

   digraph run {
     graph [rankdir=TB, nodesep=0.3, ranksep=0.25, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#4a6fa5",
            fontname="Helvetica", fontsize=11, width=5.0];
     edge  [color="#4a6fa5", arrowsize=0.7];
     case   [label="Case: a folder of CSV files or one .duckdb file", fillcolor="#e8f5e9", color="#2e7d32"];
     load   [label="Case and solver options (el1xr-run or load_case)"];
     data   [label="Input tables read; sets and parameters built (data_processing)"];
     vars   [label="Decision variables and their bounds (create_variables)"];
     layers [label="Optional layers: energy community, investment, heat sector"];
     obj    [label="Objective: costs minus revenues"];
     cons   [label="Constraints: balances, unit limits, markets, reserves, storage"];
     extra  [label="Community sharing and renewable-hydrogen matching"];
     solve  [label="Solution by HiGHS, Gurobi, CBC or CPLEX (solving_model)", fillcolor="#f3e5f5", color="#6a1b9a"];
     out    [label="Results: results.duckdb, and CSV files and plots on request", fillcolor="#fdecea", color="#c62828"];
     case -> load -> data -> vars -> layers -> obj -> cons -> extra -> solve -> out;
   }

The sequence follows ``build_model`` and ``routine`` in ``oM_Sequence``:

1. ``data_processing`` reads every table of the case and builds the sets (nodes, units, load
   levels) and the parameters. :doc:`../user-guide/data-and-io` shows how an input value
   becomes a parameter.
2. ``create_variables`` declares the decision variables and their bounds.
3. The optional layers add their own variables: the energy community, the investment
   decisions for candidate units, and the heat sector. A layer that the case does not use is
   left out.
4. The objective sums the costs and revenues, and the constraints keep every decision within
   the physical limits, the unit limits and the market rules.
5. ``solving_model`` passes the model to the solver.
6. The results are written to ``results.duckdb`` in the case folder, as described in
   :doc:`../concepts/results-and-postprocessing`.

Module structure
----------------

The modules that carry out this sequence, from the input files through the model
formulation and the solver to the results:

.. figure:: /../img/el1xr_opt_architecture.svg
   :width: 90%
   :align: center
   :alt: The el1xr_opt modules in layers: input, source, data, model, solve and output, with the decoupled network analysis.

   Module structure of el1xr_opt, from a CSV case folder or a ``.duckdb`` file to the
   results.

Further reading
---------------

- A first case: :doc:`Quickstart`, then :doc:`../user-guide/examples`.
- A new case: :doc:`../user-guide/data-and-io`.
- The formulation: :doc:`../concepts/constraints` and :doc:`../concepts/objective-function`.
- Contributions: :doc:`../developer/contributing`.
