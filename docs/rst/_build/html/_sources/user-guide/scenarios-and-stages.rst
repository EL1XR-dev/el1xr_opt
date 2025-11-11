Scenarios & stages
==================

The model's temporal structure is organized in a multi-level hierarchy, which allows for detailed and flexible simulations over various time horizons. This hierarchy is defined as follows:

``period → scenario → stage → loadlevel``

Each level plays a distinct role in defining the simulation's scope and resolution.

Hierarchy Levels
----------------

*   **Periods:** This is the highest level in the hierarchy and represents the longest time frame, such as a year or a multi-year planning horizon. The model iterates through each period to conduct long-term investment and operational simulations.

*   **Scenarios:** Within each period, there can be multiple scenarios. These typically represent different possible futures or operating conditions, such as variations in weather patterns, demand fluctuations, or fuel prices. Each scenario is assigned a probability, allowing the model to weigh its impact on the overall results.

*   **Stages:** Stages represent representative time slices within a scenario, such as a typical day, week, or month. This allows the model to analyze specific operational patterns for different types of periods (e.g., a "winter weekday" vs. a "summer weekend").

*   **Load Levels:** This is the most granular level of the hierarchy and represents the individual time steps within a stage, such as 15-minute intervals, hours, or bi-hourly steps. The model makes its finest operational decisions at this level, like dispatching power plants or charging storage units. In the codebase, this corresponds to the `nn` set.

The relationship is hierarchical: one stage can be linked to multiple load levels, but a load level belongs to only one stage.

Configuration
-------------

This hierarchical structure is not hard-coded but is configured through a series of CSV files located in the specific case directory you are running. The `data_processing` function within the `el1xr_opt.Modules.oM_InputData` module reads these files to construct the corresponding sets (`model.p`, `model.sc`, `model.n`, etc.) that the Pyomo optimization model uses.

Example
-------

Consider a simulation for a single year with two scenarios and two stages:

- **Period:** Year 1
- **Scenarios:**
    - High Demand (Probability: 50%)
    - Low Demand (Probability: 50%)
- **Stages:**
    - Representative Weekday
    - Representative Weekend
- **Load Levels:** 24 hourly intervals for each stage.

In this setup, the model would solve for the optimal hourly dispatch for both a typical weekday and a typical weekend under both high and low demand scenarios, weighted by their respective probabilities, to determine the best overall strategy for the year.