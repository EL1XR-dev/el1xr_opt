Model Sets
==========

The optimization model is built upon a series of indexed sets that define its dimensions, including time, space, and technology. These sets are used by Pyomo to create variables and constraints efficiently. Understanding these sets is crucial for interpreting the model's structure and preparing input data.

The core sets are defined in the ``model`` object and are accessible throughout the formulation scripts (e.g., in ``oM_ModelFormulation.py``).

Temporal Hierarchy
------------------

The model uses a nested temporal structure to represent time, from long-term planning periods down to hourly operational timesteps.

*   ``model.p``: **Periods**. The highest level, typically representing years in an investment planning horizon.
*   ``model.sc``: **Scenarios**. Represents different operational conditions within a period, such as typical weather weeks or stress-case scenarios.
*   ``model.n``: **Timesteps / Load Levels**. The finest temporal resolution, usually representing hours or sub-hourly intervals within a scenario.

These are often used in combination:

*   ``model.ps``: A combined set of ``(period, scenario)``.
*   ``model.psn``: A combined set of ``(period, scenario, timestep)``, representing every unique time point in the model.

Spatial Representation
----------------------

The spatial dimension defines the physical layout of the energy system.

*   ``model.nd``: **Nodes**. Represents distinct locations or buses in the energy network. All assets (generators, demands, storage) are assigned to a node.
*   ``model.ela``: **Electricity Arcs**. Defines the connections (transmission lines) in the electricity grid, represented as ``(node_from, node_to, circuit_id)``.
*   ``model.hpa``: **Hydrogen Arcs**. Defines the connections (pipelines) in the hydrogen network.

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