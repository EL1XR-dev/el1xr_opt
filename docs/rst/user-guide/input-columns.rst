Input column reference
======================

This page lists the columns of the unit tables and the single-row tables, with their meaning
and unit. The file layouts are described in :doc:`data-and-io`, the time series there too, and
the option indicators of ``oM_Data_Option`` in :doc:`../concepts/features-and-modes`.

Conventions
-----------

- **Units.** el1xr_opt has no fixed units: a case chooses one unit of power (for example kW),
  one of energy (kWh), one of money (EUR or SEK) and kg for hydrogen, and uses them in every
  table. The *Unit or values* column names the quantity.
- **Yes / No columns** take ``Yes`` or ``No`` (also ``Y``, ``N`` and lower case).
- **Blank cells** are read as 0, unless the table says otherwise.
- **Scaling.** ``Factor1`` and ``MoneyBase`` (Parameter table) rescale the numbers the solver
  sees; :doc:`data-and-io` shows the steps.
- **Unused columns.** Some tables carry columns that the current formulation does not read.
  They are listed under each table, may be left blank, and are kept so that older cases still
  load.

A test (``tests/test_docs_columns.py``) checks that every column of the shipped cases is on
this page.

Generation units
----------------

``oM_Data_ElectricityGeneration`` and ``oM_Data_HydrogenGeneration``: one row per unit. The
*Table* column tells which of the two tables a column belongs to.

.. csv-table::
   :file: columns/generation.csv
   :header-rows: 1
   :widths: 18 10 52 20

Columns read but not used:

.. csv-table::
   :file: columns/generation_unused.csv
   :header-rows: 1
   :widths: 30 70

Demands
-------

``oM_Data_ElectricityDemand`` and ``oM_Data_HydrogenDemand``: one row per demand. The demand
itself is the time series ``oM_Data_VarMaxDemand``.

.. csv-table::
   :file: columns/demand.csv
   :header-rows: 1
   :widths: 18 10 52 20

Columns read but not used:

.. csv-table::
   :file: columns/demand_unused.csv
   :header-rows: 1
   :widths: 30 70

Retailers
---------

``oM_Data_ElectricityRetail`` and ``oM_Data_HydrogenRetail``: one row per retailer. The
buying and selling prices are the time series ``oM_Data_VarEnergyCost`` and
``oM_Data_VarEnergyPrice``. The column names of the Swedish tariff terms are kept as they are:
*Overföringsavgift* is the transfer fee, *fast avgift* the fixed fee, *påslag* the markup and
*moms* the value-added tax.

.. csv-table::
   :file: columns/retail.csv
   :header-rows: 1
   :widths: 18 10 52 20

Columns read but not used:

.. csv-table::
   :file: columns/retail_unused.csv
   :header-rows: 1
   :widths: 30 70

Networks
--------

``oM_Data_ElectricityNetwork`` and ``oM_Data_HydrogenNetwork``: one row per line or pipe,
indexed by its from-node, to-node and circuit.

.. csv-table::
   :file: columns/network.csv
   :header-rows: 1
   :widths: 18 10 52 20

Columns read but not used:

.. csv-table::
   :file: columns/network_unused.csv
   :header-rows: 1
   :widths: 30 70

Global settings
---------------

``oM_Data_Parameter``: one row of settings for the whole case.

.. csv-table::
   :file: columns/parameter.csv
   :header-rows: 1
   :widths: 18 10 52 20

Columns read but not used:

.. csv-table::
   :file: columns/parameter_unused.csv
   :header-rows: 1
   :widths: 30 70

Periods, scenarios, nodes and durations
---------------------------------------

.. csv-table::
   :file: columns/other.csv
   :header-rows: 1
   :widths: 18 20 42 20
