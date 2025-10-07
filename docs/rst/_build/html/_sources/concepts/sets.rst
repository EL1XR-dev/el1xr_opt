.. _sets_section:

****
Sets
****

The optimization model is built upon a series of indexed sets that define its dimensions, including time, space, and technology. These sets are used by Pyomo to create variables and constraints efficiently. Understanding these sets is crucial for interpreting the model's structure and preparing input data.

The core sets are defined in the ``model`` object and are accessible throughout the formulation scripts (e.g., in ``oM_ModelFormulation.py``). This section provides a comprehensive reference for all sets and indices used in the model, aligned with the mathematical notation found in the :ref:`objective_function_section` and :ref:`constraints_section`.

.. contents::
   :local:
   :depth: 2

Temporal Sets and Indices
=========================

The model uses a nested temporal structure to represent time, from long-term planning periods down to hourly operational timesteps.

Sets
----

.. list-table:: Temporal Sets
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nP`
     - All periods (e.g., years in a planning horizon).
   * - :math:`\nS`
     - All scenarios, representing different operational conditions within a period.
   * - :math:`\nW`
     - All weeks in a year.
   * - :math:`\nM`
     - All months in a year.
   * - :math:`\nH`
     - All hours in a day.
   * - :math:`\nT`
     - All time steps (e.g., hours or sub-hourly intervals).
   * - :math:`\nV`
     - All time step intervals, defining the duration of each time step.

Indices
-------

.. list-table:: Temporal Indices
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\periodindex`
     - Index for a specific period.
   * - :math:`\scenarioindex`
     - Index for a specific scenario.
   * - :math:`\weekindex`
     - Index for a specific week.
   * - :math:`\monthindex`
     - Index for a specific month.
   * - :math:`\dayindex`
     - Index for a specific day.
   * - :math:`\hourindex`
     - Index for a specific hour.
   * - :math:`\timeindex`
     - Index for a specific time step.
   * - :math:`\timestepindex`
     - Index for a specific time step interval.
   * - :math:`\storageperiodindex`
     - Index for a storage-specific period.
   * - :math:`\storageweekindex`
     - Index for a storage-specific week.
   * - :math:`\storagemonthindex`
     - Index for a storage-specific month.
   * - :math:`\storagedayindex`
     - Index for a storage-specific day.
   * - :math:`\storagehourindex`
     - Index for a storage-specific hour.
   * - :math:`\storagetimeindex`
     - Index for a storage-specific time step.
   * - :math:`\storagetimestepindex`
     - Index for a storage-specific time step interval.


Spatial Sets and Indices
========================

The spatial dimension defines the physical layout and regional aggregation of the energy system.

Sets
----

.. list-table:: Spatial Sets
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nB`
     - All buses in the network.
   * - :math:`\nBE`
     - Subset of buses with electrical connections.
   * - :math:`\nBH`
     - Subset of buses with hydrogen connections.
   * - :math:`\nL`
     - All transmission/distribution lines.
   * - :math:`\nC`
     - All circuits associated with lines.
   * - :math:`\nX`
     - All regions for aggregation.
   * - :math:`\nZ`
     - All zones for aggregation.
   * - :math:`\nA`
     - All areas for aggregation.

Indices
-------

.. list-table:: Spatial Indices
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\busindex`
     - Index for a bus.
   * - :math:`\busindexa`
     - Index for the "from" bus of a branch.
   * - :math:`\busindexb`
     - Index for the "to" bus of a branch.
   * - :math:`\branchindex`
     - Index for a branch between bus :math:`i` and :math:`j`.
   * - :math:`\lineindexa`
     - Index for the "from" bus of a line :math:`c`.
   * - :math:`\lineindexb`
     - Index for the "to" bus of a line :math:`c`.
   * - :math:`\circuitindex`
     - Index for a circuit.
   * - :math:`\regionindex`
     - Index for a region.
   * - :math:`\zoneindex`
     - Index for a zone.
   * - :math:`\areaindex`
     - Index for an area.

Technological Sets and Indices
==============================

These sets and indices categorize the various technologies for generation, storage, demand, and retail.

Generation Sets
---------------

.. list-table:: Generation Sets
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nG`
     - All generators.
   * - :math:`\nGE`
     - All electrical generators.
   * - :math:`\nGER`
     - All renewable electrical generators (e.g., solar, wind).
   * - :math:`\nGENR`
     - All non-renewable electrical generators (e.g., gas turbines).
   * - :math:`\nGEH`
     - All electrical generators that consume hydrogen (e.g., fuel cells).
   * - :math:`\nGH`
     - All hydrogen generators.
   * - :math:`\nCNG`
     - All hydrogen generators that consume natural gas (e.g., reformers).
   * - :math:`\nGHE`
     - All hydrogen generators that consume electricity (e.g., electrolyzers).

Storage Sets
------------

.. list-table:: Storage Sets
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nE`
     - All storage units.
   * - :math:`\nEE`
     - All electrical storage units (e.g., batteries).
   * - :math:`\nEH`
     - All hydrogen storage units (e.g., tanks, caverns).

Demand and Retail Sets
----------------------

.. list-table:: Demand and Retail Sets
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nD`
     - All demands.
   * - :math:`\nDE`
     - All electrical demands.
   * - :math:`\nDH`
     - All hydrogen demands.
   * - :math:`\nK`
     - All peak demands.
   * - :math:`\nKE`
     - All electrical peak demands.
   * - :math:`\nKH`
     - All hydrogen peak demands.
   * - :math:`\nR`
     - All retailers (points of common coupling to a market).
   * - :math:`\nRE`
     - All electrical retailers.
   * - :math:`\nRH`
     - All hydrogen retailers.

Technology Indices
------------------

.. list-table:: Technology Indices
   :widths: 15 85
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\genindex`
     - Index for a generic generator.
   * - :math:`\elegenindex`
     - Index for an electrical generator.
   * - :math:`\elenonresgenindex`
     - Index for a non-renewable electrical generator.
   * - :math:`\elenresgenindex`
     - Index for a renewable electrical generator.
   * - :math:`\elenhydgenindex`
     - Index for an electrical generator consuming hydrogen.
   * - :math:`\hydgenindex`
     - Index for a hydrogen generator.
   * - :math:`\hydcnggenindex`
     - Index for a hydrogen generator consuming natural gas.
   * - :math:`\hydelecgenindex`
     - Index for a hydrogen generator consuming electricity.
   * - :math:`\storageindex`
     - Index for a generic storage unit.
   * - :math:`\elestorageindex`
     - Index for an electrical storage unit.
   * - :math:`\hydstorageindex`
     - Index for a hydrogen storage unit.
   * - :math:`\loadindex`
     - Index for a generic load/demand.
   * - :math:`\eleloadindex`
     - Index for an electrical load.
   * - :math:`\hydloadindex`
     - Index for a hydrogen load.
   * - :math:`\peakindex`
     - Index for a generic peak load.
   * - :math:`\elepeakindex`
     - Index for an electrical peak load.
   * - :math:`\hydpeakindex`
     - Index for a hydrogen peak load.
   * - :math:`\consindex`
     - Index for a generic consumer.
   * - :math:`\eleconsindex`
     - Index for an electrical consumer.
   * - :math:`\hydconsindex`
     - Index for a hydrogen consumer.
   * - :math:`\traderindex`
     - Index for a generic retailer/trader.
   * - :math:`\eletraderindex`
     - Index for an electrical retailer.
   * - :math:`\hydtraderindex`
     - Index for a hydrogen retailer.