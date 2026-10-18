Glossary
========

Terms used across the documentation, in alphabetical order.

.. glossary::
   :sorted:

   Activation share
      The share of a reserve bid that is expected to be activated in a load level, given in
      ``oM_Data_OperatingReserveActivation``.

   Benders decomposition
      A solution method that splits the model into a master problem (the investment, and the
      stored energy at time-window boundaries) and operating subproblems, and links them by
      cuts until the gap between the bounds is small. See :doc:`../user-guide/decomposition`.

   Build fraction
      The share of a candidate unit that is built, between ``InvestmentLo`` and
      ``InvestmentUp``. It scales every rating of the unit. See :doc:`../concepts/investment`.

   Candidate
      A unit with a positive ``FixedInvestmentCost``, whose build the model decides.

   Endurance
      The time, in minutes, for which a store must be able to deliver its reserve bid. The
      stored energy backs an upward bid and the free room a downward bid.

   Energy not served
      Demand left unmet, priced at the cost of energy not served (``ENSCost`` or ``HNSCost`` in
      ``oM_Data_Parameter``).

   Factor1
      A unit scale in ``oM_Data_Parameter``, 1 by default. Quantities are multiplied by it and
      prices divided by it; the optimal decisions do not change.

   FCR-D
      Frequency containment reserve for disturbances, procured separately for upward and
      downward regulation.

   FCR-N
      Frequency containment reserve for normal operation, a symmetric product.

   Headroom
      The margin between a unit's scheduled output or charge and its limit, within which its
      reserve bids must fit.

   Load level
      One time step of the model. Its length is set by ``LoadLevelMinutes`` (60 by default),
      and its duration in hours is given in ``oM_Data_Duration``.

   MoneyBase
      A money scale in ``oM_Data_Parameter``, 1 by default. Money values are divided by it; the
      optimal decisions do not change.

   Node
      A point of the network at which units, demands and retailers are connected and the
      energy balances are written.

   Option indicator
      A column of ``oM_Data_Option`` that turns a feature on (1) or off (0), such as unit
      commitment or ramp limits. See :doc:`../concepts/features-and-modes`.

   Period
      The longest time frame of a case, such as a year, with a weight in ``oM_Data_Period``.

   PPA
      Power purchase agreement: renewable electricity bought from a unit at a fixed price.

   Retailer
      The link from a node to a market. It carries the buying and selling prices and the
      network tariffs.

   RFNBO
      Renewable fuel of non-biological origin: hydrogen whose production the EU rules allow
      to be counted as renewable. The renewable-hydrogen matching of the model is based on them.

   Scenario
      A possible future within a period, such as a weather or price year, with a probability
      in ``oM_Data_Scenario``.

   Storage reset
      The setting of a store of ``StorageType`` Hourly back to its initial level every
      ``StorageResetHours`` (744 h by default; 0 turns it off).

   Unit
      A generating unit, store, electrolyser, fuel cell, compressor or heat unit, described by
      one row of its unit table.
