Sets
====

.. note::

   This page covers the core electricity/hydrogen sets. The heat sector, the
   investment / capacity-sizing layer and the energy-community layer add their own sets
   (heat ``htd``/``htg``/``htp``/``htw``/``hts``; candidates ``egc``/``hgc``/``egsc``/``hgsc``;
   the zone/retailer maps for sharing). See :doc:`heat-sector`, :doc:`features-and-modes`
   and :doc:`community`.

Acronyms
--------

.. list-table::
   :widths: 30 50
   :header-rows: 1

   * - **Acronym**
     - **Description**
   * - aFRR
     - Automatic Frequency Restoration Reserve
   * - BESS
     - Battery Energy Storage System
   * - DA
     - Day-Ahead
   * - ESS
     - Energy Storage System (includes BESS and HESS)
   * - EV
     - Electric Vehicle
   * - FCR-D
     - Frequency Containment Reserve – Disturbance
   * - FCR-N
     - Frequency Containment Reserve – Normal
   * - H-VPP
     - Hydrogen-based Virtual Power Plant
   * - HESS
     - Hydrogen Energy Storage System
   * - IB
     - Imbalance
   * - ID
     - Intraday
   * - mFRR
     - Manual Frequency Restoration Reserve
   * - SoC
     - State of Charge
   * - VRE
     - Variable Renewable Energy

The optimization model is built upon a series of indexed sets that define its dimensions, including time, space, and technology. These sets are used by Pyomo to create variables and constraints efficiently. Understanding these sets is crucial for interpreting the model's structure and preparing input data.

The core sets are defined in the ``model`` object and are accessible throughout the formulation scripts (e.g., in ``oM_ModelFormulation.py``).

Temporal Hierarchy
------------------

The model uses a nested temporal structure to represent time, from long-term planning periods down to hourly operational timesteps.

Sets
~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\nP`
     - All periods (e.g., years in a planning horizon)
     - :code:`model.pp`
   * - :math:`\nS`
     - All scenarios, representing different operational conditions within a period
     - :code:`model.scc`
   * - :math:`\nT`
     - All time steps (e.g., hours or sub-hourly intervals)
     - :code:`model.nn`

Indices
~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\periodindex`
     - Period (e.g., year.)
     - :code:`model.p`
   * - :math:`\scenarioindex`
     - All scenarios, representing different operational conditions within a period
     - :code:`model.sc`
   * - :math:`\timeindex`
     - Time step (e.g., hours or sub-hourly intervals)
     - :code:`model.n`
   * - :math:`ps`
     - Combination of period and scenario
     - :code:`model.ps`
   * - :math:`psn`
     - Combination of period, scenario, and time step
     - :code:`model.psn`

Spatial Representation
----------------------

The spatial dimension defines the physical layout and regional aggregation of the energy system.

Sets
~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\nB`
     - Node or bus bar in the network
     - :code:`model.nd`
   * - :math:`\nLE`
     - Electricity arcs -- all input lines (from node, to node, circuit)
     - :code:`model.eln`
   * - :math:`\nLE'`
     - Electricity lines actually modelled (the subset of ``eln`` that passes the
       reactance / transfer-capacity / period filters; used by the flow constraints)
     - :code:`model.ela`
   * - :math:`\nLH`
     - Hydrogen arc (pipeline)
     - :code:`model.hpn`
   * - :math:`\nZ`
     - Zone or region in the network
     - :code:`model.zn`

The electricity and hydrogen line sets split further into switchable, candidate and
existing arcs.

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Definition**
     - **Pyomo Component**
   * - Switchable electricity lines
     - lines in ``ela`` flagged as switchable
     - :code:`model.els`
   * - Candidate electricity lines (positive investment cost)
     - lines in ``ela`` with a fixed investment cost
     - :code:`model.elc`
   * - Existing electricity lines
     - ``ela`` minus ``elc``
     - :code:`model.ele`
   * - Hydrogen pipelines actually modelled
     - the subset of ``hpn`` that passes the transfer-capacity / period filters
     - :code:`model.hpa`
   * - Candidate hydrogen pipelines (positive investment cost)
     - pipelines in ``hpa`` with a fixed investment cost
     - :code:`model.hpc`
   * - Existing hydrogen pipelines
     - ``hpa`` minus ``hpc``
     - :code:`model.hpe`

The reference (slack) nodes for the two networks are their own one-element sets.

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Notes**
     - **Pyomo Component**
   * - Electricity reference node
     - voltage-angle / slack reference for the electricity network
     - :code:`model.endrf`
   * - Hydrogen reference node
     - pressure reference for the hydrogen network
     - :code:`model.hndrf`

Indices
~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\busindex`
     - Node or bus bar in the network
     - :code:`nd`
   * - :math:`\busindexa`
     - From node of a connection or arc
     - :code:`i`
   * - :math:`\busindexb`
     - To node of a connection or arc
     - :code:`j`
   * - :math:`\lineindexa`
     - From node of a transmission line
     - :code:`ijc`
   * - :math:`\lineindexb`
     - To node of a transmission line
     - :code:`jic`
   * - :math:`\zoneindex`
     - Zone or region in the network
     - :code:`zn`

Technology and Asset Sets
-------------------------

The model uses a rich set of indices to differentiate between various types of technologies and assets. There is a clear separation between the electricity and hydrogen systems.

General Technology Subsets
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\nGE`
     - All electricity generation units
     - :code:`model.eg`
   * - :math:`\nGENR`
     - Non-renewable electricity generators (subset of :math:`\nGE`)
     - :code:`model.egnr`
   * - :math:`\nGR`
     - Renewable (RES) electricity generators (subset of :math:`\nGE`)
     - :code:`model.egr`
   * - :math:`\nGT`
     - Thermal (committable) electricity generators (subset of :math:`\nGE`)
     - :code:`model.egt`
   * - :math:`\nGV`
     - Electric-vehicle units (subset of :math:`\nGE`)
     - :code:`model.egv`
   * - :math:`\nEE`
     - Electricity energy storage systems (subset of :math:`\nGE`)
     - :code:`model.egs`
   * - :math:`\nGH`
     - All hydrogen production units
     - :code:`model.hg`
   * - :math:`\nHGT`
     - Scheduled / thermal hydrogen units (positive variable cost, subset of :math:`\nGH`)
     - :code:`model.hgt`
   * - :math:`\nGHE`
     - Units converting electricity to hydrogen, i.e. electrolysers (``e2h``)
     - :code:`model.e2h`
   * - :math:`\nGEH`
     - Units converting hydrogen to electricity, i.e. fuel cells (``h2e``)
     - :code:`model.h2e`
   * - :math:`\nEH`
     - Hydrogen energy storage systems (subset of :math:`\nGH`)
     - :code:`model.hgs`

.. note::

   ``model.hgr`` (the hydrogen analogue of ``egr``, "hydrogen RES units") is a
   deliberately empty placeholder. There is no hydrogen RES input column, so the set is
   always empty; it exists only so the initial-output loop can reference it the same way
   the electricity loop references ``egr``.

Cross-sector and storage/conversion unions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These derived sets are built by set algebra (union ``|`` / difference ``-``) from the base
technology sets and are used to write balance and capacity constraints compactly.

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Definition**
     - **Pyomo Component**
   * - Non-RES electricity generators (committable, can carry reserves)
     - ``eg`` minus ``egr``
     - :code:`model.egnr`
   * - Electricity consumption units (storage charging plus electrolysers)
     - ``egs`` union ``e2h``
     - :code:`model.eh`
   * - Hydrogen consumption units (hydrogen storage charging plus fuel cells)
     - ``hgs`` union ``h2e``
     - :code:`model.he`
   * - Electricity and hydrogen storage combined
     - ``egs`` union ``hgs``
     - :code:`model.ehs`
   * - Candidate electricity and hydrogen units combined
     - ``egc`` union ``hgc``
     - :code:`model.esc`

Technology subsets
~~~~~~~~~~~~~~~~~~

Technology labels (the ``gt`` set) grouped by what the units mapped to them are.

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Notes**
     - **Pyomo Component**
   * - Electricity storage technologies
     - technologies that have at least one ``egs`` unit
     - :code:`model.et`
   * - Hydrogen storage technologies
     - technologies that have at least one ``hgs`` unit
     - :code:`model.ht`
   * - RES technologies
     - technologies that have at least one ``egr`` unit
     - :code:`model.rt`

Heat sector
~~~~~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Pyomo Component**
     - **Notes**
   * - Heat demands
     - :code:`model.htd`
     - per node via ``n2htd``
   * - Heat generators (heat pumps and boilers)
     - :code:`model.htg`
     - per node via ``n2htg``
   * - Heat pumps (electricity to heat, subset of ``htg``)
     - :code:`model.htp`
     - the cross-sector load on the electricity balance
   * - Heat-to-power units (ORC / CHP)
     - :code:`model.htw`
     - per node via ``n2htw``
   * - Thermal stores
     - :code:`model.hts`
     - per node via ``n2hts``

See :doc:`heat-sector`.

Investment / candidates
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Pyomo Component**
     - **Notes**
   * - Electricity investment candidates (positive investment cost)
     - :code:`model.egc`
     - candidate generators / storage / fuel cells
   * - Electricity storage candidates (subset of ``egc``)
     - :code:`model.egsc`
     -
   * - Hydrogen investment candidates
     - :code:`model.hgc`
     - candidate electrolysers / storage
   * - Hydrogen storage candidates (subset of ``hgc``)
     - :code:`model.hgsc`
     -

The community layer additionally uses the zone/retailer mapping sets ``n2er`` / ``n2hr``
and ``z2er`` (see :doc:`community`).

Indices
~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\genindex`
     - Generation units
     - :code:`g`
   * - :math:`\storageindex`
     - Index letter for a storage unit. The storage **sets** are ``egs`` (electricity),
       ``hgs`` (hydrogen) and their union ``ehs``; there is no bare ``e`` set in the code.
     - :code:`egs` / :code:`hgs` / :code:`ehs`
   * - :math:`\traderindex`
     - Index letter for a retailer. The retailer **sets** are ``er`` (electricity)
       and ``hr`` (hydrogen); there is no bare ``r`` set in the code.
     - :code:`er` / :code:`hr`

Demand and Retail
~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\nDE`
     - All electricity demands
     - :code:`model.ed`
   * - :math:`\nDH`
     - All hydrogen demands
     - :code:`model.hd`
   * - :math:`\nRE`
     - All electricity retailers
     - :code:`model.er`
   * - :math:`\nRH`
     - All hydrogen retailers
     - :code:`model.hr`
   * - :math:`\nKE`
     - Set of peak indices for demand charge calculation
     - :code:`model.Peaks`

Indices
~~~~~~~

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Symbol**
     - **Description**
     - **Pyomo Component**
   * - :math:`\demandindex`
     - Consumer (demand index letter; sets are ``ed`` / ``hd``)
     - :code:`d`
   * - :math:`\traderindex`
     - Retailer (retailer index letter; sets are ``er`` / ``hr``)
     - :code:`r`

Inverse-Index Mapping Sets
--------------------------

The model uses mapping sets to link specific assets to their location, zone, technology
and retailer. These are "inverse index" sets: each entry pairs a key (node, zone,
technology or retailer) with an asset, so a constraint can loop over all assets sitting at
a given node or zone.

There are four families, each with an electricity (``e``) and a hydrogen (``h``) variant,
applied to generators (``g``), demands (``d``) and retailers (``r``):

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Family**
     - **Meaning (key to asset)**
     - **Pyomo Components**
   * - ``n2*``
     - node to asset
     - :code:`n2eg` / :code:`n2hg`, :code:`n2ed` / :code:`n2hd`, :code:`n2er` / :code:`n2hr`
   * - ``z2*``
     - zone to asset (built from ``n2*`` via the node-zone map ``ndzn``)
     - :code:`z2eg` / :code:`z2hg`, :code:`z2ed` / :code:`z2hd`, :code:`z2er` / :code:`z2hr`
   * - ``t2*``
     - technology to generator
     - :code:`t2eg` / :code:`t2hg`
   * - ``r2*``
     - retailer to asset
     - :code:`r2eg` / :code:`r2hg`, :code:`r2ed` / :code:`r2hd`

These sets are fundamental for building the energy balance constraints at each node. By
combining temporal, spatial, and technological sets, the model can create highly specific
variables, such as ``vEleTotalOutput[p,sc,n,eg]``, which represents the electricity output
of generator ``eg`` at a specific time ``(p,sc,n)``.

Calendar Time Sets
------------------

On top of the operational time step ``n``, the model derives a calendar from the model
start date. These sets let monthly and daily quantities (peak charges, daily storage
cycles) be written cleanly.

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Description**
     - **Notes**
     - **Pyomo Component**
   * - Months of the year present in the horizon
     - unique month numbers
     - :code:`model.moy`
   * - Days of the year present in the horizon
     - unique day-of-year numbers
     - :code:`model.doy`
   * - Hours of the year present in the horizon
     - unique hour-of-year numbers
     - :code:`model.hoy`
   * - Time step to month
     - pairs ``(n, month)``
     - :code:`model.n2m`
   * - Time step to day
     - pairs ``(n, day)``
     - :code:`model.n2d`
   * - Day to month
     - pairs ``(day, month)``
     - :code:`model.d2m`

These calendar sets are combined with period and scenario into composite index sets that
the monthly / daily constraints loop over. The naming follows the same prefix convention
as the operational index sets (``p`` period, ``s`` scenario, ``m`` month, ``d`` day,
``n`` time step). The main families are:

.. list-table::
   :widths: 30 50 30
   :header-rows: 1

   * - **Pattern**
     - **Tuple**
     - **Representative Pyomo Component**
   * - ``psm``
     - ``(p, sc, month)``
     - :code:`model.psm`
   * - ``psd``
     - ``(p, sc, day)``
     - :code:`model.psd`
   * - ``psdn``
     - ``(p, sc, day, n)``
     - :code:`model.psdn`
   * - ``psmd``
     - ``(p, sc, month, day)``
     - :code:`model.psmd`
   * - ``psmdn``
     - ``(p, sc, month, day, n)``
     - :code:`model.psmdn`

.. note::

   Each base pattern is further crossed with an asset set to give the index lists the
   constraints actually use, for example ``psmer`` / ``psmhr`` / ``psmhd`` (month, by
   retailer / hydrogen demand), ``psder`` / ``psded`` / ``psdegs`` / ``psdhgs`` (day, by
   retailer / demand / storage) and the per-time-step variants ``psdner`` / ``psdned`` /
   ``psdnegs`` / ``psdnhgs``. They all follow the same prefix-plus-asset convention.