Sets
====

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
   * - :math:`\nC`
     - Electricity connection (from node, to node, circuit)
     - :code:`model.cc`
   * - :math:`\nLE`
     - Electricity arc (transmission line)
     - :code:`model.eln`
   * - :math:`\nLH`
     - Hydrogen arc (pipeline)
     - :code:`model.hpn`
   * - :math:`\nZ`
     - Zone or region in the network
     - :code:`model.zn`

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

*   **Electricity Generation** (:math:`\elegenindex`):

    *   ``model.egt``: Dispatchable generators that can be committed (turned on/off), like gas turbines.
    *   ``model.egs``: Electricity storage units, like batteries.
    *   ``model.egnr``: Non-renewable generators.

*   **Hydrogen Production** (:math:`\hydgenindex`):

    *   ``model.hgt``: Dispatchable hydrogen producers.
    *   ``model.hgs``: Hydrogen storage units, like salt caverns or tanks.

*   **Energy Conversion**:
    *   ``model.e2h``: Technologies that convert **electricity to hydrogen** (e.g., electrolyzers). This is a subset of ``hg``.
    *   ``model.h2e``: Technologies that convert **hydrogen to electricity** (e.g., fuel cells). This is a subset of ``eg``.

.. list-table:: Technology and Asset Set Symbols
   :widths: 15 60 25
   :header-rows: 1

   * - Symbol
     - Description
     - :code:`oM_InputData.py`
   * - :math:`\nGE`
     - All electricity generation units
     - :code:`model.eg`
   * - :math:`\nGENR`
     - Non-renewable electricity generators (subset of :math:`\nGE`)
     - :code:`model.egnr`
   * - :math:`\nGVRE`
     - Variable Renewable Energy (VRE) generators (subset of :math:`\nGE`)
     - :code:`model.egvre`
   * - :math:`\nEE`
     - Electricity energy storage systems (subset of :math:`\nGE`)
     - :code:`model.egs`
   * - :math:`\nGH`
     - All hydrogen production units
     - :code:`model.hg`
   * - :math:`\nGHE`
     - Units converting electricity to hydrogen (e.g., electrolyzers)
     - :code:`model.e2h`
   * - :math:`\nGEH`
     - Units converting hydrogen to electricity (e.g., fuel cells)
     - :code:`model.h2e`
   * - :math:`\nEH`
     - Hydrogen energy storage systems (subset of :math:`\nGH`)
     - :code:`model.hgs`

============  =======================================================================================================================
**Index**     **Description**
------------  -----------------------------------------------------------------------------------------------------------------------
:math:`eg`    Electricity unit (thermal or hydro unit or ESS)
:math:`et`    Electricity thermal unit
:math:`es`    Electricity energy storage system (eESS)
:math:`hg`    Hydrogen unit (e.g., electrolyzer, hydrogen tank)
:math:`hz`    Hydrogen electrolyzer
:math:`hs`    Hydrogen energy storage system (e.g., hydrogen tank)
============  =======================================================================================================================

Demand and Retail
~~~~~~~~~~~~~~~~~

*   ``model.ed``: Electricity demands.
*   ``model.hd``: Hydrogen demands.
*   ``model.er``: Electricity retail markets (points of common coupling for buying/selling from a wholesale market).
*   ``model.hr``: Hydrogen retail markets.

.. list-table:: Demand, Retail, and Miscellaneous Set Symbols
   :widths: 20 80
   :header-rows: 1

   * - Symbol
     - Description
   * - :math:`\nDE`
     - All electricity demands
   * - :math:`\nDH`
     - All hydrogen demands
   * - :math:`\nRE`
     - All electricity retailers
   * - :math:`\nKE`
     - Set of peak indices for demand charge calculation

Node-to-Technology Mappings
---------------------------

The model uses mapping sets to link specific assets to their locations in the network. For example:

*   ``model.n2eg``: Maps which electricity generators exist at which nodes.
*   ``model.n2hg``: Maps which hydrogen producers exist at which nodes.
*   ``model.n2ed``: Maps electricity demands to nodes.

These sets are fundamental for building the energy balance constraints at each node. By combining temporal, spatial, and technological sets, the model can create highly specific variables, such as ``vEleTotalOutput[p,sc,n,eg]``, which represents the electricity output of generator ``eg`` at a specific time ``(p,sc,n)``.