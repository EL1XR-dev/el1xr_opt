.. _future_developments:

Future Developments
===================

This section outlines potential future enhancements to the optimisation model, based on a number of identified challenges and opportunities for more detailed modelling. These items represent a roadmap for increasing the model's accuracy and applicability to real-world scenarios.

.. note::

   Several items once on this roadmap are **now implemented** and documented elsewhere:
   the :doc:`heat-sector`, the :doc:`community` sharing layer, the modular
   feature/cost-registry architecture (:doc:`features-and-modes`), the physical
   electricity PPA and RFNBO matching (green hydrogen), and the depth-of-discharge
   degradation scaffolding. What remains genuinely future is, for example, district
   heating with a heat network, virtual/CfD PPAs, and the ``arc`` (block-angular)
   balance that would underpin a Dantzig-Wolfe decomposition. Treat the list below as
   indicative and cross-check against the changelog.

To-Do List
----------

The following is a list of key areas for future development, divided into modelling enhancements and computational/structural improvements.

Modelling Enhancements
----------------------

This category includes improvements that add new features, constraints, or more detailed representations of physical or financial systems to the model.

1.  **Sequential Market Participation**:

    *   **Challenge**: The current model does not fully capture the sequential nature of day-ahead (DA), intraday (ID), and imbalance (IMB) markets. It assumes perfect foresight for intraday markets.

    *   **To-Do**: Implement a deterministic MILP model that can handle the sequential decision-making process across these markets. This could involve a rolling horizon approach or the use of penalty factors to represent the uncertainty of intraday prices.
    *   **Prototype Equations**: The objective function would be expanded to include revenues and costs from each market stage:

        .. math::
           \max \pi = \sum_{t \in T} (R_{DA,t} + R_{ID,t} - C_{DA,t} - C_{ID,t})

        where bids in later markets adjust the position from earlier ones:

        .. math::
           P_{dispatch,t} = B_{DA,t} + B_{ID,t}

    *   **Potential Integration**:

        *   Introduce new decision variables in `oM_ModelFormulation.py` for bids in each market (e.g., :math:`vBidDA_t`, :math:`vBidID_t`).
        *   Add new parameters for the prices in each market.
        *   Implement new constraints to link the market positions sequentially.

2.  **LER (Limited Energy Reservoir) Constraints Implementation**:

    *   **Challenge**: The model needs to incorporate the hysteresis logic for Normal/Alert Energy Management (NEM/AEM) for BESS participating in Frequency Containment Reserve (FCR) markets, as per Swedish TSO requirements.
    *   **To-Do**: Implement the state-dependent enable/disable logic for NEM/AEM activation states using binary variables and state transition constraints.
    *   **Prototype Equations**: The hysteresis logic can be modelled using Big-M constraints. For example, for the NEM-low mode activation:

        .. math::
           SOC_t - SOC_{lower,enable} \leq M \cdot (1 - b_{NEM-low,t})
        .. math::
           SOC_{lower,disable} - SOC_t \leq M \cdot b_{NEM-low,t}

    *   **Potential Integration**:

        *   Add new binary variables in `oM_ModelFormulation.py` for each NEM/AEM state (e.g., :math:`vNEM_{low,t}`).
        *   Define new parameters for the SOC thresholds (e.g., :math:`pSOC_{lower,enable}`).
        *   Add the Big-M constraints to `create_constraints` in `oM_ModelFormulation.py`.

3.  **PPA Inclusion in the Model**:

    *   **Challenge**: The model currently lacks the functionality to incorporate a virtual Power Purchase Agreement (PPA) or a Contract for Difference (CfD) into the financial model and technical constraints.
    *   **To-Do**: Develop the necessary mathematical formulations to represent the financial settlements of a virtual PPA and integrate them into the objective function.
    *   **Prototype Equation**: The trading revenue from a two-way CfD can be formulated as:

        .. math::
           R_{trad,t} = (p_{market,t} - p_{strike}) \cdot B_{PPA,t}

    *   **Potential Integration**:

        *   Modify the objective function in `oM_ModelFormulation.py` to include this revenue component.
        *   Add a new parameter for the PPA strike price (:math:`pPPA_{strike}`) and a variable for the PPA volume (:math:`vPPA_{volume,t}`).

4.  **Multiple Timescales Modeling**:

    *   **Challenge**: The model needs to handle both high-resolution frequency regulation signals (second/minute-level) and energy market data (hour-level) simultaneously.
    *   **To-Do**: Investigate and implement the best time resolution to handle both frequency and energy markets, potentially using time-aggregation techniques.
    *   **Prototype Equation**: This is primarily a structural change. Equations would need to be defined over different time sets, for example energy balance over hourly steps :math:`t` and FCR provision over minute-steps :math:`\tau`:

        .. math::
           E_{balance,t} = ...
        .. math::
           P_{FCR, \tau} = ...

    *   **Potential Integration**:

        *   Requires a significant change to the temporal structure in `oM_InputData.py` to handle multiple time resolutions.
        *   All time-indexed variables and constraints in `oM_ModelFormulation.py` would need to be updated to use the appropriate time sets.

5.  **Market Participation Exclusion Rules**:

    *   **Challenge**: The model uses a Big-M formulation to allow flexible participation in multiple frequency services, but it does not yet incorporate specific exclusion rules that may be imposed by TSOs (e.g., for Swedish frequency markets).
    *   **To-Do**: Implement the necessary logical constraints to enforce any exclusion rules between different frequency services, such as FCR-N and aFRR.
    *   **Prototype Equation**: Mutual exclusivity can be enforced with a simple linear constraint on the binary participation variables:

        .. math::
           b_{FCR-N,t} + b_{aFRR,t} \leq 1

    *   **Potential Integration**:

        *   Add this new constraint to `create_constraints` in `oM_ModelFormulation.py`, linking the existing binary variables for market participation.

6.  **Grid Fees and COMA Costs**:

    *   **Challenge**: The model's cost structure for grid usage and operations is not yet fully defined.
    *   **To-Do**: Define and implement a realistic cost structure for grid usage fees (MWh imported/exported) and COMA (Operating, Maintenance, Administration) costs, whether as fixed annual costs or usage-based.
    *   **Prototype Equations**: These costs would be added to the objective function:

        .. math::
           C_{grid,t} = c_{grid,import} \cdot P_{import,t} + c_{grid,export} \cdot P_{export,t}
        .. math::
           C_{COMA} = C_{fixed\_O\&M}

    *   **Potential Integration**:

        *   Update the objective function in `oM_ModelFormulation.py`.
        *   Add new parameters for the grid fee rates (:math:`pGridFee_{import}`) and fixed O&M costs (:math:`pCOMA_{cost}`).
        *   The grid cost would use the existing variables for grid import/export (:math:`vElecImport_t`, :math:`vElecExport_t`).

7.  **Vehicle-to-Grid (V2G) Integration**:

    *   **Current Status**: The model currently includes a basic representation of an aggregated EV fleet, considering it as a flexible load and storage resource with AC charging capabilities.
    * **Challenge**: The existing model can be enhanced to provide a more detailed and realistic representation of V2G by incorporating different charging technologies (DC), considering battery degradation from cycling, and modelling more complex driver behaviours.
    *   **To-Do**: Extend the V2G model to include DC fast-charging capabilities, add a cost component for battery degradation, and refine the constraints related to driving energy requirements.
    *   **AC vs. DC Charging**:

        *   **AC Charging (Implemented)**: The current model represents lower power charging via the vehicle's onboard charger, using a single efficiency parameter (:math:`\eta_{AC}`).
        *   **DC Charging (Future)**: A future extension would add high-power DC charging, which bypasses the vehicle's onboard charger. This would require a separate, higher efficiency parameter (:math:`\eta_{DC}`) and could be linked to different grid connection points or constraints.
    *   **Prototype Equations**: The state of charge for the aggregated EV fleet will continue to use the existing formulation, but a degradation cost should be added to the objective function:

        .. math::
           C_{V2G\_deg,t} = c_{deg} \cdot (P_{chg,t} + P_{dis,t})

        And the energy requirement constraint remains crucial:

        .. math::
           SOC_{EV,t} \geq SOC_{min,driving,t}

    *   **Potential Integration**:

        *   Modify the existing EV-related sets and parameters in `oM_InputData.py` to include data for DC chargers (e.g., efficiency, capacity).
        *   Introduce a new cost term for degradation to the objective function in `oM_ModelFormulation.py`.
        *   Add new variables or constraints if necessary to distinguish between AC and DC charging power, potentially allowing simultaneous connection to both if the model scope requires it.

8.  **Degradation Modeling for Energy Storage**:

    *   **Challenge**: To capture the long-term economic impact of operational decisions, the model must account for the physical degradation of storage assets. This is complex because different technologies degrade in different ways.
    *   **To-Do**: Implement distinct degradation cost models for electrochemical batteries (BESS) and hydrogen systems (electrolyzers, fuel cells).
    *   **BESS Degradation (Electrical Storage)**: Battery degradation is primarily driven by two factors:

        *   **Cycle Aging**: Caused by the throughput of energy (charging and discharging).
        *   **Calendar Aging**: Occurs over time regardless of usage.
    *   **Simple Model**: A linear cost per MWh of throughput is a common simplification for cycle aging.

        .. math::
           C_{BESS\_deg,t} = c_{cycle} \cdot (P_{chg,t} + P_{dis,t}) + c_{calendar}

    *   **Advanced Model**: *Depth of Discharge (DoD) Penalization* - A more accurate approach recognizes that deeper discharge cycles cause more stress than shallow ones. This non-linear cost can be approximated in a linear model using a piecewise function.

        *   **Prototype Equation**: The total degradation cost is the sum of costs incurred in different SOC segments, each with a different penalty.

            .. math::
               C_{BESS\_cycle\_deg,t} = \sum_{s \in S} c_{segment,s} \cdot E_{discharged,s,t}

            where :math:`S` is the set of DoD segments (e.g., 100-80%, 80-60%), :math:`c_{segment,s}` is the increasing cost for each segment, and :math:`E_{discharged,s,t}` is the energy discharged within that segment.

        *   **Potential Integration**: This requires a more complex formulation, typically using Special Ordered Sets of Type 2 (SOS2) constraints or binary variables to model the piecewise cost function. New parameters would be needed in `oM_InputData.py` to define the segment breakpoints and costs.

    *   **Hydrogen System Degradation**: Degradation in hydrogen systems primarily affects the conversion components, not the hydrogen storage tank itself. Key drivers include:

        *   **Operational Stress**: Total operating hours for electrolyzers and fuel cells.
        *   **Start/Stop Cycles**: Thermal and mechanical stress from starting up and shutting down.
    *   **Prototype Equations for Hydrogen Systems**:

        .. math::
           C_{Hyd\_deg,t} = c_{op} \cdot b_{commit,t} + c_{su} \cdot b_{startup,t}

        where :math:`b_{commit,t}` is a binary variable for being online and :math:`b_{startup,t}` is a binary for starting up at time :math:`t`.
    *   **Potential Integration**:

        *   Add new parameters to `oM_InputData.py` for degradation cost factors (e.g., :math:`pBESS_{cycle\_cost}`, :math:`pHyd_{op\_cost}`).
        *   Add these new cost components to the objective function in `oM_ModelFormulation.py`, linking them to existing variables for power dispatch and commitment status.

Computational and Structural Enhancements
-----------------------------------------

This category focuses on improvements to the underlying code structure and mathematical formulation to enhance computational efficiency, scalability, and maintainability.

1.  **Code Restructuring with Python Classes**:

    *   **Challenge**: The current implementation relies on a procedural approach with functions spread across multiple modules. This can make the code harder to navigate, debug, and extend as the model complexity grows.
    *   **To-Do**: Refactor the codebase into a more object-oriented structure. A central `OptimizationModel` class could encapsulate the data, Pyomo model, and methods for building, solving, and post-processing.
    *   **Benefits**:

        *   **Encapsulation**: Grouping related data and functions into a single class improves organization.
        *   **Maintainability**: Changes to the model are localized within the class, reducing the risk of unintended side effects.
        *   **Scalability**: A class-based structure is easier to extend with new components (e.g., new assets, new market products).
    *   **Potential Integration**:

        *   Create a new class in a module like `oM_ModelClass.py`.
        *   Methods of this class would wrap the existing functions from `oM_ModelFormulation.py`, `oM_InputData.py`, etc.
        *   The main script `el1xr_Main.py` would then instantiate this class to run the optimisation.

2.  **Modular Component Implementation with Pyomo Blocks**:

    *   **Challenge**: As more assets (like V2G, electrolyzers, different PPA types) are added, the main model formulation in `create_constraints` can become monolithic and difficult to manage. Adding or removing a component requires manually editing a large function.
    *   **To-Do**: Use Pyomo's `Block` feature to encapsulate the variables and constraints for each physical or financial component. Each block would represent a self-contained model of an asset.
    *   **Example**: A `BESS` block could contain all variables (state of charge, charge/discharge power) and constraints (energy balance, power limits) related to the battery.
    *   **Benefits**:

        *   **Modularity**: Makes it easy to add, remove, or swap different implementations of a component (e.g., a simple BESS model vs. an advanced one with degradation).
        *   **Readability**: The main model becomes a cleaner composition of these blocks, rather than a long list of constraints.
        *   **Scalability**: Simplifies the management of models with many individual assets of the same type (e.g., multiple battery units).
    *   **Potential Integration**:

        *   In `oM_ModelFormulation.py`, define a separate function for each component that returns a `Block` (e.g., `def create_bess_block(...)`).
        *   The main `create_constraints` function would then call these functions to attach the blocks to the main model.
