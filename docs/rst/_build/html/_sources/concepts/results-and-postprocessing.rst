Results & Post-Processing
=========================

After a successful optimization run, the model automatically post-processes the solution and saves a comprehensive set of results to the case directory (e.g., ``data/case_name/``). This is handled by the ``saving_results`` function in the ``oM_OutputData`` module.

The primary outputs are a series of CSV files, each prefixed with ``oM_Result_``, which provide detailed insights into the model's decisions. Several plots are also generated as HTML files.

Key Output Files
----------------

The results are organized into several key CSV files for detailed analysis:

*   **`oM_Result_01_rTotalCost_...`**: This file provides a breakdown of the total system costs. It comes in two forms:
    *   `_Hourly_`: Shows the costs (market, generation, emissions, etc.) for each timestep.
    *   `_General_`: Shows the total costs aggregated for each period and scenario.

*   **`oM_Result_02_rElectricityBalance_...`**: This is a crucial output for understanding the physical operation of the system. It details the energy balance (in MWh) at every node for every timestep, showing the contribution of each component (generation, consumption, flows).

*   **`oM_Result_05_rEleStateOfEnergy_...`**: This file tracks the state of energy (or state of charge) for all electricity storage assets over time, making it easy to analyze how batteries and other storage devices are being used.

*   **`oM_Result_07_rEleOutputSummary_...`**: A wide-format summary file that aggregates many key results into a single table. It includes production/discharge, consumption/charge, inventory levels, prices, and the availability status of assets for each timestep.

*   **`oM_Result_08_rEnergyBalance_...`**: This file contains the aggregated energy flow data used to generate the Sankey diagrams. It shows the total energy transferred between major system components (e.g., from Solar PV to the demand, or from the grid to an EV).

Visualizations
--------------

In addition to the raw data, the model generates several interactive plots saved as HTML files, which can be opened in any web browser:

*   **`oM_Plot_rElectricityBalance_...`**: A stacked bar chart visualizing the electricity balance over time.
*   **`oM_Plot_rEleDemand_...`**: A line chart showing the original and net electricity demand, overlaid with the electricity price.
*   **`oM_Plot_rEleStateOfEnergy_...`**: A line chart showing the state of energy for storage assets, often overlaid with their availability status.
*   **`oM_Plot_rSankey_...`**: Sankey diagrams illustrating the energy flows between different parts of the system for each period.
*   **`oM_Plot_rDurationCurve_...`**: A series of duration curves for key metrics like demand, generation, and market interaction, showing the number of hours a certain value is met or exceeded.

These files provide a solid foundation for understanding the optimization results, from high-level economic summaries down to the detailed operational behavior of individual assets.