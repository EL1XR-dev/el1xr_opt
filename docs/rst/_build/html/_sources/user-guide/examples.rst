Examples
========

The framework includes pre-configured example cases that demonstrate how to structure input data for different energy system scales and configurations. These cases can be found in the ``src/el1xr_opt/`` directory and can be run using the main script.

Grid-Scale System: ``Grid1``
-----------------------------

The ``Grid1`` case represents a simplified, grid-scale hybrid energy system. It is designed to model the interactions between electricity and hydrogen networks, including various generation, storage, and demand technologies.

**Key Features:**

*   **Integrated Networks**: Includes data for both electricity and hydrogen grids (``oM_Data_ElectricityNetwork_Grid1.csv``, ``oM_Data_HydrogenNetwork_Grid1.csv``).
*   **Multiple Technologies**: Models a mix of generation assets, such as conventional power plants, renewables, and electrolyzers.
*   **Demand Profiles**: Contains sample data for electricity and hydrogen demand (``oM_Data_ElectricityDemand_Grid1.csv``, ``oM_Data_HydrogenDemand_Grid1.csv``).
*   **Operational Constraints**: The model is configured to consider operational details like generator ramping limits and minimum uptime/downtime, as specified in ``oM_Data_Option_Grid1.csv``.

This case is useful for users interested in transmission-level analysis, sector coupling, and large-scale renewable integration.

Residential Microgrid: ``Home1``
--------------------------------

The ``Home1`` case models a small-scale residential microgrid or a single "energy-prosumer" home. It is suitable for analyzing behind-the-meter assets and local energy optimization.

**Key Features:**

*   **Local Assets**: Focuses on typical residential technologies like rooftop solar PV, battery storage, and a home charger for an electric vehicle.
*   **Retail Tariffs**: Incorporates data for electricity retail prices and tariffs (``oM_Data_ElectricityRetail_Home1.csv``, ``oM_Data_Tariff_Home1.csv``), which are key drivers for residential optimization.
*   **Simplified Network**: Assumes a single-node or a very simple local network structure.
*   **Operational Logic**: Like the grid-scale case, it uses an options file (``oM_Data_Option_Home1.csv``) to define the active model constraints.

This case serves as a good starting point for users focused on distributed energy resources (DERs), demand response, and home energy management systems.

Running the Examples
--------------------

To run an example, you typically need to point the main execution script (e.g., ``el1xr_Main.py``) to the desired case directory. This is usually done by modifying a configuration file or a command-line argument that specifies the ``CaseName`` (e.g., "Grid1" or "Home1").