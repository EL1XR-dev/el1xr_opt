Sets
====

Acronyms
--------

===========  ====================================================================
**Acronym**  **Description**
===========  ====================================================================
BESS         Battery Energy Storage System
DA           Day-Ahead Market
ESS          Energy Storage System (includes BESS and HESS)
H-VPP        Hydrogen-based Virtual Power Plant
HESS         Hydrogen Energy Storage System
ID           Intraday Markets
RT           Real Time Market
SoC          State of Charge
VRE          Variable Renewable Energy
===========  ====================================================================

The optimization model is built upon a series of indexed sets that define its dimensions, including time, space, and technology. These sets are used by Pyomo to create variables and constraints efficiently. Understanding these sets is crucial for interpreting the model's structure and preparing input data.

The core sets are defined in the ``model`` object and are accessible throughout the formulation scripts (e.g., in ``oM_ModelFormulation.py``).

Temporal Hierarchy
------------------

The model uses a nested temporal structure to represent time, from long-term planning periods down to hourly operational timesteps.

Sets
~~~~

==========================  ===============================================================================  ========================================
**Symbol**                  **Description**                                                                  **oM_InputData.py**
--------------------------  -------------------------------------------------------------------------------  ----------------------------------------
:math:`\nP`                  All periods (e.g., years in a planning horizon)                                 :code:`model.p`
:math:`\nS`                  All scenarios, representing different operational conditions within a period    :code:`model.sc`
:math:`\nT`                  All time steps (e.g., hours or sub-hourly intervals)                            :code:`model.n`
==========================  ===============================================================================  ========================================

Indices
~~~~~~~

==========================  ===============================================================================  ========================================
**Symbol**                  **Description**                                                                  **oM_InputData.py**
--------------------------  -------------------------------------------------------------------------------  ----------------------------------------
:math:`\periodindex`        Period (e.g., year.)                                                             :code:`model.p`
:math:`\scenarioindex`      Scenario (e.g., solar generation, spot prices, etc.)                             :code:`model.sc`
:math:`\timeindex`          Time step (e.g., hours or sub-hourly intervals)                                  :code:`model.n`
:math:`ps`                  Combination of period and scenario                                               :code:`model.ps`
:math:`psn`                 Combination of period, scenario, and time step                                   :code:`model.psn`
==========================  ===============================================================================  ========================================

Spatial Representation
----------------------

The spatial dimension defines the physical layout and regional aggregation of the energy system.

Sets
~~~~

============  ==============================================================================  =========================================
**Symbol**    **Description**                                                                 **oM_InputData.py**
------------  ------------------------------------------------------------------------------  -----------------------------------------
:math:`\nB`   Node or bus bar in the network                                                  :code:`model.nd`
:math:`\nC`   Electricity connection (from node, to node, circuit ID)                         :code:`model.cc`
:math:`\nL`   Electricity arc (transmission line)                                             :code:`model.eln`
:math:`\nH`   Hydrogen arc (pipeline)                                                         :code:`model.hpn`
:math:`\nZ`   Zone or region in the network                                                   :code:`model.zn`
============  ==============================================================================  =========================================

Indices
~~~~~~~

========================  ==============================================================================  =========================================
**Symbol**                **Description**                                                                 **oM_InputData.py**
------------------------  ------------------------------------------------------------------------------  -----------------------------------------
:math:`\busindex`         Node or bus bar in the network                                                  :code:`nd`
:math:`\busindexa`        From node of a connection or arc                                                :code:`i`
:math:`\busindexb`        To node of a connection or arc                                                  :code:`j`
:math:`\circuitindex`     Circuit ID of a connection                                                      :code:`cc`
:math:`\lineindexa`       From node of a transmission line                                                :code:`ijc`
:math:`\lineindexb`       To node of a transmission line                                                  :code:`jic`
:math:`\zoneindex`        Zone or region in the network                                                   :code:`z`
========================  ==============================================================================  =========================================

Technology and Asset Sets
-------------------------

The model uses a rich set of indices to differentiate between various types of technologies and assets. There is a clear separation between the electricity and hydrogen systems.

General Technology Subsets
~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Electricity Generation (`eg`)**:

    *   ``model.egt``: Dispatchable generators that can be committed (turned on/off), like gas turbines.
    *   ``model.egs``: Electricity storage units, like batteries.
    *   ``model.egnr``: Non-renewable generators.
    *   ``model.egv``: Variable renewable energy sources (VRES), like solar and wind.

*   **Hydrogen Production (`hg`)**:

    *   ``model.hgt``: Dispatchable hydrogen producers.
    *   ``model.hgs``: Hydrogen storage units, like salt caverns or tanks.

*   **Energy Conversion**:
    *   ``model.e2h``: Technologies that convert **electricity to hydrogen** (e.g., electrolyzers). This is a subset of ``hg``.
    *   ``model.h2e``: Technologies that convert **hydrogen to electricity** (e.g., fuel cells). This is a subset of ``eg``.

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

Node-to-Technology Mappings
---------------------------

The model uses mapping sets to link specific assets to their locations in the network. For example:

*   ``model.n2eg``: Maps which electricity generators exist at which nodes.
*   ``model.n2hg``: Maps which hydrogen producers exist at which nodes.
*   ``model.n2ed``: Maps electricity demands to nodes.

These sets are fundamental for building the energy balance constraints at each node. By combining temporal, spatial, and technological sets, the model can create highly specific variables, such as ``vEleTotalOutput[p,sc,n,eg]``, which represents the electricity output of generator ``eg`` at a specific time ``(p,sc,n)``.