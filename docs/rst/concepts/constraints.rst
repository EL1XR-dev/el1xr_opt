Constraints
===========
The optimization model is governed by a series of constraints that ensure the solution is physically and economically feasible. These constraints, defined in the ``create_constraints`` function, enforce everything from the laws of physics to the operational limits of individual assets.

.. note::

   This page covers the core electricity/hydrogen constraints. The heat balance and
   conversions (``eHeatBalance``, ``eHeatPumpCOP``, ``eHeatToEle``, ``eHeatInventory``),
   the investment caps (``e*InvestMax*``, ``eTotalICost``) and the community pool
   (``eEleCommunityPool``) are documented on the :doc:`heat-sector`,
   :doc:`features-and-modes` and :doc:`community` pages. Note that the electricity
   balance ``eEleBalance`` also carries the heat-pump load and heat-to-power injection
   when a heat case is active, and the retail balance carries the community share terms.

1. Market and Commercial Constraints
------------------------------------
These constraints model the rules for interacting with external markets. And the economic trading is shown in the next figure.

.. image:: /../img/Market_interaction.png
   :scale: 30%
   :align: center

Day-ahead Electricity Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Participation in the day-ahead electricity market is modeled through constraints ensuring that energy bought or sold doesn't exceed predefined limits for each time step and retailer.

Electricity bought from the market is enabled if :math:`\pelemaxmarketbuy_{\eltraderindex} >= 0.0`. The upper bound is defined by («``eEleRetMaxBuy``»):

.. math::
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} \le \peleretmaxbuy_{\eltraderindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\eltraderindex

The composition of electricity bought from the market is defined by («``eEleBuyComposition``»):

.. math::
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} =
   \sum_{\demandindex \in \nDE, (\eltraderindex,\demandindex) \in \nREDE} \veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} +
   \sum_{\storageindex \in \nEES, (\eltraderindex,\storageindex) \in \nREGE} \veletotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\eltraderindex

.. note::
   ``eEleBuyComposition`` is currently disabled in the model (commented out in
   ``oM_ModelFormulation.py``). The relation above documents its intended form.

Electricity sold to the market is enabled if :math:`\pelemaxmarketsell_{\eltraderindex} >= 0.0`. The upper bound is defined by («``eEleRetMaxSell``»):

.. math::
   \velesell_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} \le \peleretmaxsell_{\eltraderindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\eltraderindex

The composition of electricity sold to the market is defined by («``eEleSellComposition``»):

.. math::
   \velesell_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} =
   \sum_{\genindex \in \nGENR, (\eltraderindex,\genindex) \in \nREGE} \veletotaloutput_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\eltraderindex

.. note::
   ``eEleSellComposition`` is currently disabled in the model (commented out in
   ``oM_ModelFormulation.py``). The relation above documents its intended form.

Day-ahead Hydrogen Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Participation in the day-ahead hydrogen market ensures that the amount of energy bought or sold does not exceed predefined limits for each time step and retailer.

Hydrogen bought from the market («``eHydRetMaxBuy``») is enabled if :math:`\phydmaxmarketbuy_{\hydtraderindex} >= 0.0`:

.. math::
   \vhydbuy_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} \le \phydretmaxbuy_{\hydtraderindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\hydtraderindex

The composition of hydrogen bought from the market is defined by («``eHydBuyComposition``»):

.. math::
   \vhydbuy_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} =
   \sum_{\busindex \in \nB, (\busindex,\hydtraderindex) \in \nBH} \vhydimport_{\periodindex,\scenarioindex,\timeindex,\busindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\hydtraderindex

Hydrogen sold to the market («``eHydRetMaxSell``») is enabled if :math:`\phydmaxmarketsell_{\hydtraderindex} >= 0.0`:

.. math::
   \vhydsell_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} \le \phydretmaxsell_{\hydtraderindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\hydtraderindex

The composition of hydrogen sold to the market is defined by («``eHydSellComposition``»):

.. math::
   \vhydsell_{\periodindex,\scenarioindex,\timeindex,\hydtraderindex} =
   \sum_{\busindex \in \nB, (\busindex,\hydtraderindex) \in \nBH} \vhydexport_{\periodindex,\scenarioindex,\timeindex,\busindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\hydtraderindex

Reserve Electricity Market Participation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Frequency containment reserves in normal operation (FCR-N)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-N is a symmetric product. The total FCR-N bid from eligible generators and storage units is limited by the FCR-N requirement, taken as the average of the upward and downward requirements («``eEleFreqContReserveNor``»):

.. math::
   \sum_{\genindex \in \nGET, \pgennofcrn_{\genindex}=0} \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \sum_{\storageindex \in \nEES, \pgennofcrn_{\storageindex}=0} \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \le \frac{1}{2}\left(\pfcrnrequirement^{up}_{\periodindex,\scenarioindex,\timeindex} + \pfcrnrequirement^{dn}_{\periodindex,\scenarioindex,\timeindex}\right)
   \quad \forall \periodindex,\scenarioindex,\timeindex

For a generator, the FCR-N bid is bounded by both its upward and downward provision («``eEleRelationFreqNorUpBid2Gen``», «``eEleRelationFreqNorDownBid2Gen``»):

.. math::
   \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\genindex} \le \velefcrnupgen_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET, \pgennofcrn_{\genindex}=0

.. math::
   \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\genindex} \le \velefcrndowngen_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET, \pgennofcrn_{\genindex}=0

For a storage unit, the FCR-N bid equals the sum of its discharging and charging provision in each direction («``eEleRelationFreqNorUpBid2Stor``», «``eEleRelationFreqNorDownBid2Stor``»):

.. math::
   \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\storageindex} =
   \velefcrnupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrnupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES, \pgennofcrn_{\storageindex}=0

.. math::
   \velefcrnbid_{\periodindex,\scenarioindex,\timeindex,\storageindex} =
   \velefcrndowndis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrndowncha_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES, \pgennofcrn_{\storageindex}=0

Because FCR-N is symmetric, a storage unit provides equal upward and downward reserve in each operating mode («``eEleSymmFreqNorStor2Ch``», «``eEleSymmFreqNorStor2Dis``»):

.. math::
   \velefcrnupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} = \velefcrndowncha_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \velefcrnupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} = \velefcrndowndis_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Frequency containment reserves in disturbed operation (FCR-D)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FCR-D is modeled through the upward and downward reserve constraints, which ensure that the provision of reserves does not exceed the available capacity of generators and storage units.

The bids for upward and downward reserves are constrained by («``eEleFreqContReserveDisUpward``», «``eEleFreqContReserveDisDownward``»):

.. math::
   \sum_{\genindex \in \nGET, \pgennofcrd_{\genindex}=0} \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \sum_{\genindex \in \nEES, \pgennofcrd_{\genindex}=0} \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \le \pfcrduprequirement_{\periodindex,\scenarioindex,\timeindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex

.. math::
   \sum_{\genindex \in \nGET, \pgennofcrd_{\genindex}=0} \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \sum_{\genindex \in \nEES, \pgennofcrd_{\genindex}=0} \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \le \pfcrddwrequirement_{\periodindex,\scenarioindex,\timeindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex

The relation between bids and FCR-D reserves from an electric generator is defined by («``eEleRelationFreqDisUpBid2Gen``», «``eEleRelationFreqDisDownBid2Gen``»):

.. math::
   \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex,\genindex} =
   \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET, \pgennofcrd_{\genindex}=0

.. math::
   \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex,\genindex} =
   \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET, \pgennofcrd_{\genindex}=0

And for an electric ESS («``eEleRelationFreqDisUpBid2Stor``», «``eEleRelationFreqDisDownBid2Stor``»):

.. math::
   \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex,\storageindex} =
   \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \velefcrdupactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES, \pgennofcrd_{\storageindex}=0

.. math::
   \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex,\storageindex} =
   \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \velefcrddwactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES, \pgennofcrd_{\storageindex}=0

Combined headroom for FCR-D and FCR-N provision from an electric ESS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The headroom constraints limit the **sum** of the FCR-D and FCR-N provision in each
direction and operating mode to the remaining capacity. The upward headroom is
defined by («``eEleFreqUpDischargeHeadroom``», «``eEleFreqUpChargeHeadroom``»):

.. math::
   \velefcrdupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrnupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} \le
   \pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \velefcrdupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrnupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} \le
   \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

and the downward headroom by («``eEleFreqDownDischargeHeadroom``», «``eEleFreqDownChargeHeadroom``»):

.. math::
   \velefcrddwdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrndowndis_{\periodindex,\scenarioindex,\timeindex,\storageindex} \le
   \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \velefcrddwcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrndowncha_{\periodindex,\scenarioindex,\timeindex,\storageindex} \le
   \pelemaxcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. note::
   For a unit that does not participate in the day-ahead market (or whose maximum
   discharge power is numerically zero), the two discharge headroom constraints
   instead bound the provision by the maximum charge power
   :math:`\pelemaxcharge`. The constraints are active when the unit is eligible
   for FCR-D (:math:`\pgennofcrd=0`) or FCR-N (:math:`\pgennofcrn=0`).

Availability bounds for FCR-D and FCR-N provision from an electric ESS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The total provision in each mode, as a fraction of the unit capacity, is limited by
the time-varying availability. The upward bounds are («``eEleFreqUpDischargeBound``», «``eEleFreqUpChargeBound``»):

.. math::
   \frac{\velefcrdupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrnupdis_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\velefcrdupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrnupcha_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

and the downward bounds are («``eEleFreqDownDischargeBound``», «``eEleFreqDownChargeBound``»):

.. math::
   \frac{\velefcrddwdis_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrndowndis_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\velefcrddwcha_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrndowncha_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Storage endurance for FCR-D and FCR-N
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Endurance constraints make sure a storage unit holds enough energy (for upward
reserve) or enough free capacity (for downward reserve) to sustain its reserve bid
for the required duration. The reserve bid of the previous time step
(:math:`\timeindex-\ptimestep`) is used, with the endurance requirements
:math:`\pelegenendurancefcrd` and :math:`\pelegenendurancefcrn` given in minutes.
The upward and downward endurance are defined by («``eEleStorageEnduranceUp``», «``eEleStorageEnduranceDown``»):

.. math::
   \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} \ge
   \frac{1}{\pdischeff_{\storageindex}} \left(
   \frac{\pelegenendurancefcrd_{\storageindex}}{60} \velefcrdupbid_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} +
   \frac{\pelegenendurancefcrn_{\storageindex}}{60} \velefcrnbid_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} \right)
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \pelemaxstorage_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} \ge
   \pcheff_{\storageindex} \left(
   \frac{\pelegenendurancefcrd_{\storageindex}}{60} \velefcrddwbid_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} +
   \frac{\pelegenendurancefcrn_{\storageindex}}{60} \velefcrnbid_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} \right)
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. note::
   An earlier activation-based version of the headroom constraints (named
   ``eEleFreqDis...Headroom``) appeared here; those constraint names are not present
   in the current code. The constraints above match the implemented
   ``eEleFreq...Headroom`` family, which bound the combined FCR-D and FCR-N
   provision. Please review the formulation against ``oM_ModelFormulation.py``.

Peak Power Calculation
~~~~~~~~~~~~~~~~~~~~~~~
A set of constraints identify the highest power peaks within a billing period for tariff calculations, supporting both 'Hourly' and 'Daily' tariff types.

Hourly Tariff Constraints
^^^^^^^^^^^^^^^^^^^^^^^^^
For retailers with 'Hourly' tariffs, the following constraints identify the peak consumption hours within each month.

The peak demand value is determined by («``eElePeakHourValue``»):

.. math::
   \vglobalpeak_{\periodindex,\scenarioindex,\monthindex,\eltraderindex,\peakindex} \ge
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} -
   \pmaxsell_{\eltraderindex} \sum_{\peakindex' \le \peakindex} \vpeakind_{\periodindex,\scenarioindex,\timeindex,\eltraderindex,\peakindex'}
   \quad \forall \periodindex,\scenarioindex,\monthindex,\timeindex,\eltraderindex,\peakindex

(Note: Although a night discount between 22:00 and 06:00 is described in the documentation, it is not currently applied in the peak calculation equations below.)

Indicator constraints («``eElePeakHourInd_C1``», «``eElePeakHourInd_C2``») link the peak demand variables to binary indicators:

.. math::
   \vglobalpeak_{\periodindex,\scenarioindex,\monthindex,\eltraderindex,\peakindex} \ge
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} -
   \pmaxsell_{\eltraderindex} (1 - \vpeakind_{\periodindex,\scenarioindex,\timeindex,\eltraderindex,\peakindex})
   \quad \forall \periodindex,\scenarioindex,\monthindex,\timeindex,\eltraderindex,\peakindex

.. math::
   \vglobalpeak_{\periodindex,\scenarioindex,\monthindex,\eltraderindex,\peakindex} \le
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} +
   \pmaxsell_{\eltraderindex} (1 - \vpeakind_{\periodindex,\scenarioindex,\timeindex,\eltraderindex,\peakindex})
   \quad \forall \periodindex,\scenarioindex,\monthindex,\timeindex,\eltraderindex,\peakindex

The number of peak hours selected per month is constrained by («``eElePeakNumberMonths``»):

.. math::
   \sum_{\periodindex,\scenarioindex,\timeindex} \vpeakind_{\periodindex,\scenarioindex,\timeindex,\eltraderindex,\peakindex} = 1
   \quad \forall \monthindex,\eltraderindex,\peakindex

Daily Tariff Constraints
^^^^^^^^^^^^^^^^^^^^^^^^
For retailers with 'Daily' tariffs, the constraints first identify the daily peak and then select the highest peaks from those daily values.

The daily peak demand is determined by («``eEleDailyPeakValue``»):

.. math::
   \vdailypeak_{\periodindex,\scenarioindex,\text{doy},\eltraderindex} \ge
   \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\timeindex,\eltraderindex

Indicator constraints («``eEleDailyPeakInd_C1``», «``eEleDailyPeakInd_C2``») and the daily peak selection constraint («``eEleDailyPeakNumber``») work together to identify the single peak hour for each day.

The global peak is then selected from the daily peaks («``eEleGlobalPeakValue``»):

.. math::
   \vglobalpeak_{\periodindex,\scenarioindex,\monthindex,\eltraderindex,\peakindex} \ge
   \vdailypeak_{\periodindex,\scenarioindex,\text{doy},\eltraderindex} -
   \pmaxsell_{\eltraderindex} \sum_{\peakindex' \le \peakindex} \vmonthpeakind_{\periodindex,\scenarioindex,\text{doy},\eltraderindex,\peakindex'}
   \quad \forall \periodindex,\scenarioindex,\monthindex,\text{doy},\eltraderindex,\peakindex

Finally, the number of daily peaks selected per month is constrained by («``eElePeakNumberDays``»), and the peaks are ordered from highest to lowest by («``eEleMonthPeakOrder``»).

3. Energy Balance and Conversion
--------------------------------
These are the most fundamental constraints, ensuring that at every node (:math:`\busindexa`) and at every timestep (:math:`\timeindex`), energy supply equals energy demand.

Electricity Balance
~~~~~~~~~~~~~~~~~~~
The electricity balance at each node is enforced by («``eEleBalance``»):

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGE_{\busindex}} \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nEES_{\busindex}} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\genindex \in \nGHE_{\busindex}} \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &- \sum_{(\busindexb,\circuitindex) \in lout(\busindex)} \vflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   + \sum_{(\busindexa,\circuitindex) \in lin(\busindex)} \vflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex} \\
   &+ \veleimport_{\periodindex,\scenarioindex,\timeindex,\busindex} - \veleexport_{\periodindex,\scenarioindex,\timeindex,\busindex}
   = \sum_{\demandindex \in \nDE_{\busindex}}(\veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}
   - \vloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex})
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex
   \end{aligned}

Electricity Retailer Balance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At each retailer connection point, the balance links the retailer's own generators
and storage, its market purchases and sales, and the demand it serves
(«``eEleRetNodeBalance``»):

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGER} \veletotaloutput_{\periodindex,\scenarioindex,\timeindex,\genindex}
   + \sum_{\genindex \in \nGET} \left( \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} + \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \right)
   + \sum_{\storageindex \in \nEES} \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \\
   &- \sum_{\storageindex \in \nEES} \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\genindex \in \nGHE} \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}
   + \velebuy_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} - \velesell_{\periodindex,\scenarioindex,\timeindex,\eltraderindex} \\
   &= \sum_{\demandindex \in \nDE} \left( \veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} - \veleloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex} \right)
   \quad \forall \periodindex,\scenarioindex,\timeindex,\eltraderindex \in \nRE
   \end{aligned}

where every sum is restricted to the generators, storage units, electrolysers and
demands assigned to retailer :math:`\eltraderindex` (the retailer-to-asset mappings
:math:`\nREGE`, :math:`\nREDE`, and the retailer-to-hydrogen-generator mapping).

Hydrogen Balance
~~~~~~~~~~~~~~~~
The hydrogen balance at each node is enforced by («``eHydBalance``»):

.. math::
   \begin{aligned}
   &\sum_{\genindex \in \nGH_{\busindex}} \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   - \sum_{\storageindex \in \nEHS_{\busindex}} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   - \sum_{\genindex \in \nHGE_{\busindex}} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \\
   &- \sum_{(\busindexb,\circuitindex) \in hout(\busindex)} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindex,\busindexb,\circuitindex}
   + \sum_{(\busindexa,\circuitindex) \in hin(\busindex)} \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindex,\circuitindex} \\
   &+ \vhydimport_{\periodindex,\scenarioindex,\timeindex,\busindex} - \vhydexport_{\periodindex,\scenarioindex,\timeindex,\busindex}
   = \sum_{\demandindex \in \nDH_{\busindex}}(\vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}
   - \vhydloadshed_{\periodindex,\scenarioindex,\timeindex,\demandindex})
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindex
   \end{aligned}

Energy Conversion
~~~~~~~~~~~~~~~~~
Energy conversion between electricity and hydrogen is modeled by the following constraints.

From hydrogen to electricity («``eAllEnergy2Ele``»):
:math:`\veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} = \phydtoelefunction_{\genindex} \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGEH`

From electricity to hydrogen («``eAllEnergy2Hyd``»):
:math:`\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} = \frac{\veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydprodfunction_{\genindex}} \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE`

2. Asset Operational Constraints
--------------------------------
These constraints model the physical limitations of generation and storage assets.

Output and Charge Limits
~~~~~~~~~~~~~~~~~~~~~~~~
The total output of a committed electricity unit is defined by («``eEleTotalOutput``»):

.. math::
   \begin{aligned}
   \frac{\veletotaloutput_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} =
   \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \pfcrdact_{\periodindex,\scenarioindex,\timeindex} \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\genindex} -
   \pfcrdact_{\periodindex,\scenarioindex,\timeindex} \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}}
   {\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGENR
   \end{aligned}

For electricity storage systems, the formulation is:

.. math::
   \begin{aligned}
   \frac{\veletotaloutput_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}} =
   \velestordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \pfcrdupreqactivation_{\periodindex,\scenarioindex,\timeindex} \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex} -
   \pfcrddwreqactivation_{\periodindex,\scenarioindex,\timeindex} \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   {\peleminproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES
   \end{aligned}

The total output of a hydrogen unit is defined by («``eHydTotalOutput``»):

.. math::
   \frac{\vhydtotaloutput_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} =
   \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} +
   \frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

The total charge of an electricity storage system is defined by («``eEleTotalCharge``»):

.. math::
   \begin{aligned}
   \frac{\veletotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} =
   \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} -
   \pfcrdupreqactivation_{\periodindex,\scenarioindex,\timeindex} \velefcrdupactch_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \pfcrddwreqactivation_{\periodindex,\scenarioindex,\timeindex} \velefcrddwactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   {\peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES
   \end{aligned}

The total charge of a hydrogen unit is defined by («``eHydTotalCharge``»):

.. math::
   \frac{\vhydtotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}} =
   \vhydstorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nHGS

The maximum and minimum charge of the second block for an electrolyzer is constrained by («``eE2HMaxCharge2ndBlock``», «``eE2HMinCharge2ndBlock``»):

.. math::
   \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \cdot \phydmaxchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \geq \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \geq \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} \cdot \phydminchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGHE

Ramping Limits
~~~~~~~~~~~~~~
A series of constraints limit how quickly the output or charging rate of an asset can change. For example, ``eEleMaxRampUpOutput`` restricts the increase in a generator's output between consecutive timesteps.

Maximum ramp-up and ramp-down for a non-renewable electricity unit («``eEleMaxRampUpOutput``», «``eEleMaxRampDwOutput``»):
* P. Damcı-Kurt, S. Küçükyavuz, D. Rajan, and A. Atamtürk, “A polyhedral study of production ramping,” Math. Program., vol. 158, no. 1–2, pp. 175–205, Jul. 2016. `10.1007/s10107-015-0919-9 <https://doi.org/10.1007/s10107-015-0919-9>`_

.. math::
   \frac{-\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} - \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} + \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\genindex}}
   \le \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

.. math::
   \frac{-\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} - \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\genindex}}
   \ge -\velecommitbin_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \vshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

Maximum ramp-up and ramp-down for discharging an electricity ESS («``eEleMaxRampUpDischarge``», «``eEleMaxRampDwDischarge``»):

.. math::
   \frac{-\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} - \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\storageindex}}
   \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{-\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} - \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\storageindex}}
   \ge -1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Maximum ramp-up and ramp-down for a hydrogen unit («``eHydMaxRampUpOutput``», «``eHydMaxRampDwOutput``»):

.. math::
   \frac{-\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\genindex}}
   \le \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vhydstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

.. math::
   \frac{-\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\genindex}}
   \ge -\vhydcommitbin_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex} + \vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

Unit Commitment Logic
~~~~~~~~~~~~~~~~~~~~~
For dispatchable assets, these constraints model the on/off decisions.

Logical relation between commitment, startup, and shutdown status of an electricity unit («``eEleCommitmentStartupShutdown``»):

.. math::
   \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \velecommitbin_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex}
   = \velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \veleshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

Logical relation for a hydrogen unit («``eHydCommitmentStartupShutdown``»):

.. math::
   \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\genindex}
   = \vhydstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

Minimum up-time and down-time of a thermal unit («``eEleMinUpTime``», «``eEleMinDownTime``»):
- D. Rajan and S. Takriti, “Minimum up/down polytopes of the unit commitment problem with start-up costs,” IBM, New York, Technical Report RC23628, 2005. https://pdfs.semanticscholar.org/b886/42e36b414d5929fed48593d0ac46ae3e2070.pdf

.. math::
   \sum_{\timeindex'=\timeindex-\puptime_{\genindex}+1}^{\timeindex} \velestartupbin_{\periodindex,\scenarioindex,\timeindex',\genindex}
   \le \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

.. math::
   \sum_{\timeindex'=\timeindex-\pdwtime_{\genindex}+1}^{\timeindex} \veleshutdownbin_{\periodindex,\scenarioindex,\timeindex',\genindex}
   \le 1 - \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

Minimum up-time and down-time for a hydrogen unit («``eHydMinUpTime``», «``eHydMinDownTime``»):

.. math::
   \sum_{\timeindex'=\timeindex-\puptime_{\genindex}+1}^{\timeindex} \vhydstartupbin_{\periodindex,\scenarioindex,\timeindex',\genindex}
   \le \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

.. math::
   \sum_{\timeindex'=\timeindex-\pdwtime_{\genindex}+1}^{\timeindex} \vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex',\genindex}
   \le 1 - \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

..
    Decision variable of the operation of the compressor conditioned by the on/off status variable of itself [GWh] («``eCompressorOperStatus``»)

    :math:`\veleconsumptioncompress_{\periodindex,\scenarioindex,\timeindex,\storageindex} \geq \frac{\vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}} \peleconscompress_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! 1e-3 (1 \!-\! \vhydcompressbin_{\periodindex,\scenarioindex,\timeindex,\storageindex}) \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH`

    Decision variable of the operation of the compressor conditioned by the status of energy of the hydrogen tank [kgH2] («``eCompressorOperInventory``»)

    :math:`hsi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!+\! (\overline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \underline{HI}_{\periodindex,\scenarioindex,\timeindex,\storageindex}) hcf_{\periodindex,\scenarioindex,\timeindex,\storageindex} \quad \forall nhs`

    StandBy status of the electrolyzer conditioning its electricity consumption («``eEleStandBy_consumption_UpperBound``, ``eEleStandBy_consumption_LowerBound``»)

    :math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \geq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

    :math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

    StandBy status of the electrolyzer conditioning its hydrogen production («``eHydStandBy_production_UpperBound``, ``eHydStandBy_production_LowerBound``»)

    :math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \geq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} (1 \!-\! hsf_{\periodindex,\scenarioindex,\timeindex,\genindex}) \quad \forall nhz`

    :math:`ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \underline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex} (1 \!-\! hsf_{\periodindex,\scenarioindex,\timeindex,\genindex}) \quad \forall nhz`

    Avoid transition status from off to StandBy of the electrolyzer («``eHydAvoidTransitionOff2StandBy``»)

    :math:`hsf_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq huc_{\periodindex,\scenarioindex,\timeindex,\genindex} \quad \forall nhz`

Second Block Constraints
~~~~~~~~~~~~~~~~~~~~~~~~
These constraints define the operational limits for the second block of generation and storage units, including reserve provision.

Maximum and minimum electricity generation of the second block for a committed unit («``eEleMaxOutput2ndBlock``», «``eEleMinOutput2ndBlock``»):
* D.A. Tejada-Arango, S. Lumbreras, P. Sánchez-Martín, and A. Ramos "Which Unit-Commitment Formulation is Best? A Systematic Comparison" IEEE Transactions on Power Systems 35 (4):2926-2936 Jul 2020 `10.1109/TPWRS.2019.2962024 <https://doi.org/10.1109/TPWRS.2019.2962024>`_
* C. Gentile, G. Morales-España, and A. Ramos "A tight MIP formulation of the unit commitment problem with start-up and shut-down constraints" EURO Journal on Computational Optimization 5 (1), 177-201 Mar 2017. `10.1007/s13675-016-0066-y <https://doi.org/10.1007/s13675-016-0066-y>`_
* G. Morales-España, A. Ramos, and J. Garcia-Gonzalez "An MIP Formulation for Joint Market-Clearing of Energy and Reserves Based on Ramp Scheduling" IEEE Transactions on Power Systems 29 (1): 476-488, Jan 2014. `10.1109/TPWRS.2013.2259601 <https://doi.org/10.1109/TPWRS.2013.2259601>`_
* G. Morales-España, J.M. Latorre, and A. Ramos "Tight and Compact MILP Formulation for the Thermal Unit Commitment Problem" IEEE Transactions on Power Systems 28 (4): 4897-4908, Nov 2013. `10.1109/TPWRS.2013.2251373 <https://doi.org/10.1109/TPWRS.2013.2251373>`_

.. math::
   \frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} + \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\pelemaxprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}}
   \le \velecommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \velestartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \veleshutdownbin_{\periodindex,\scenarioindex,\timeindex+1,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

.. math::
   \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} - \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\genindex} \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nGET

Maximum and minimum electricity generation of the second block for an electricity ESS («``eEleMaxESSOutput2ndBlock``», «``eEleMinESSOutput2ndBlock``»):

.. math::
   \frac{\velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \velefcrddwactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex} \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Maximum and minimum hydrogen generation of the second block for a committed unit («``eHydMaxOutput2ndBlock``», «``eHydMinOutput2ndBlock``»):

.. math::
   \frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}}{\phydmaxprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\genindex}}
   \le \vhydcommitbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vhydstartupbin_{\periodindex,\scenarioindex,\timeindex,\genindex} - \vhydshutdownbin_{\periodindex,\scenarioindex,\timeindex+1,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

.. math::
   \vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex \in \nHGT

Maximum and minimum hydrogen output of the second block for a hydrogen ESS («``eHydMaxESSOutput2ndBlock``», «``eHydMinESSOutput2ndBlock``»):

.. math::
   \frac{\vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxprodsecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \vhydstorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. math::
   \vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex} \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. note::
   In the code the hydrogen ESS output is bounded by the charging-mode binary
   (:math:`\vhydstorchargebin`), while the electricity equivalent
   (``eEleMaxESSOutput2ndBlock``) uses the discharging-mode binary. Likewise the
   hydrogen ESS charge (``eMaxHydESSCharge2ndBlock``) is bounded by the
   discharging-mode binary. The charge/discharge binaries appear swapped relative
   to the electricity formulation — verify this is intended.

3. Energy Storage Dynamics
--------------------------
These constraints specifically model the behavior of energy storage systems.

Inventory Balance (State-of-Charge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The core state-of-charge (SoC) balancing equation, ``eEleInventory`` for electricity and ``eHydInventory`` for hydrogen, tracks the stored energy level over time.

State-of-Charge balance for electricity storage systems:

.. math::
   \begin{aligned}
   &\veleinventory_{\periodindex,\scenarioindex,\timeindex-\pcycletimestep_{\storageindex},\storageindex} +
   \sum_{\timeindex'=\timeindex-\pcycletimestep_{\storageindex}+1}^{\timeindex}
   \ptimestepduration_{\periodindex,\scenarioindex,\timeindex'}
   (\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} -
   \veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \\
   &\frac{\veletotaloutput_{\periodindex,\scenarioindex,\timeindex',\storageindex}}{\pdischeff_{\storageindex}} +
   \pcheff_{\storageindex} \veletotalcharge_{\periodindex,\scenarioindex,\timeindex',\storageindex})
   = \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \velespillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES
   \end{aligned}

State-of-Charge balance for hydrogen storage systems:

.. math::
   \begin{aligned}
   &\vhydinventory_{\periodindex,\scenarioindex,\timeindex-\pcycletimestep_{\storageindex},\storageindex} +
   \sum_{\timeindex'=\timeindex-\pcycletimestep_{\storageindex}+1}^{\timeindex}
   \ptimestepduration_{\periodindex,\scenarioindex,\timeindex'}
   (\vhydenergyinflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} -
   \vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \\
   &\vhydtotaloutput_{\periodindex,\scenarioindex,\timeindex',\storageindex} +
   \peff_{\storageindex} \vhydtotalcharge_{\periodindex,\scenarioindex,\timeindex',\storageindex})
   = \vhydinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \vhydspillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nHGS
   \end{aligned}

Charge/Discharge Incompatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The constraints prevent a storage unit from charging and discharging in the same timestep, using binary variables.

Electricity Storage Incompatibility («``eEleChargingDecision``», «``eEleDischargingDecision``», «``eEleStorageMode``»):

.. math::
   \frac{\veletotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\veletotaloutput_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \velestordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \le \pfixavail_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Hydrogen Storage Incompatibility («``eHydChargingDecision``», «``eHydDischargingDecision``», «``eHydStorageMode``»):

.. math::
   \frac{\vhydtotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \vhydstorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nHGS

.. math::
   \frac{\vhydtotaloutput_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \vhydstordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nHGS

.. math::
   \vhydstorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex} +
   \vhydstordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \le \pfixavail_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nHGS

Depth of Discharge (DoD) Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints model the degradation of electricity storage systems based on their Depth of Discharge (DoD).

The minimum and maximum inventory levels for each day are tracked by («``eEleInventoryMinDay``», «``eEleInventoryMaxDay``»):

.. math::
   \veleinvminday_{\periodindex,\scenarioindex,\text{doy},\storageindex} \le
   \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\timeindex,\storageindex \in \nEES

.. math::
   \veleinvmaxday_{\periodindex,\scenarioindex,\text{doy},\storageindex} \ge
   \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\timeindex,\storageindex \in \nEES

The daily DoD is calculated as the difference between the maximum and minimum inventory levels («``eEleInventoryDoD``»):

.. math::
   \veleinvdoday_{\periodindex,\scenarioindex,\text{doy},\storageindex} =
   \veleinvmaxday_{\periodindex,\scenarioindex,\text{doy},\storageindex} -
   \veleinvminday_{\periodindex,\scenarioindex,\text{doy},\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\storageindex \in \nEES

The total DoD is divided into three segments to model non-linear degradation costs («``eEleInventoryDoDSegments``»):

.. math::
   \veleinvdoday_{\periodindex,\scenarioindex,\text{doy},\storageindex} =
   \veleinvdodsaday_{\periodindex,\scenarioindex,\text{doy},\storageindex} +
   \veleinvdodsbday_{\periodindex,\scenarioindex,\text{doy},\storageindex} +
   \veleinvdodscday_{\periodindex,\scenarioindex,\text{doy},\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\storageindex \in \nEES

Upper bounds for each DoD segment are defined by («``eEleInventoryDoDS1Upper``», «``eEleInventoryDoDS2Upper``», «``eEleInventoryDoDS3Upper``»):

.. math::
   \veleinvdodsaday_{\periodindex,\scenarioindex,\text{doy},\storageindex} \le
   \pdodsa_{\storageindex} \pmaxstorage_{\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\storageindex \in \nEES

.. math::
   \veleinvdodsbday_{\periodindex,\scenarioindex,\text{doy},\storageindex} \le
   \pdodsb_{\storageindex} \pmaxstorage_{\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\storageindex \in \nEES

.. math::
   \veleinvdodscday_{\periodindex,\scenarioindex,\text{doy},\storageindex} \le
   \pdodsc_{\storageindex} \pmaxstorage_{\storageindex}
   \quad \forall \periodindex,\scenarioindex,\text{doy},\storageindex \in \nEES

.. note::
   The per-segment DoD bounds (``eEleInventoryDoDS1Upper``/``S2Upper``/``S3Upper``
   and the matching lower bounds) are currently disabled in the model (commented
   out in ``oM_ModelFormulation.py``). The daily DoD (``eEleInventoryDoD``) and the
   segment split (``eEleInventoryDoDSegments``) are active. The bounds above
   document the intended segment limits.

Energy Inflows and Outflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Energy inflows and outflows are constrained by the ESS commitment decision and physical limits.

Maximum and minimum electricity inflows («``eEleMaxInflows2Commitment``», «``eEleMinInflows2Commitment``»):

.. math::
   \frac{\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemininflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \ge 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

For storage units that provide FCR-D and do not participate in the day-ahead market, the energy inflow is allowed only while the unit is in charging mode («``eEleInflowsCharge``»):

.. math::
   \frac{\veleenergyinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES, \pgennofcrd_{\storageindex}=0

Maximum and minimum electricity outflows («``eEleMaxOutflows2Commitment``», «``eEleMinOutflows2Commitment``»):

.. math::
   \frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\peleminoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \ge 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Similar constraints apply to hydrogen storage systems («``eHydMaxInflows2Commitment``», «``eHydMinInflows2Commitment``», «``eHydMaxOutflows2Commitment``», «``eHydMinOutflows2Commitment``»).

For an electricity-consuming unit (storage or electrolyser) with no minimum charge and a fixed-availability profile, the total charge is limited by the availability profile («``eEleTotalMaxChargeConditioned``»):

.. math::
   \frac{\veletotalcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le \pvarfixedavailability_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

ESS electricity outflows over a cycle are constrained by («``eEleMaxEnergyOutflows``», «``eEleMinEnergyOutflows``»):

.. math::
   \sum_{\timeindex'=\timeindex-\poutflowtimestep_{\storageindex}+1}^{\timeindex}
   (\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \pelemaxoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex}) \le 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \sum_{\timeindex'=\timeindex-\poutflowtimestep_{\storageindex}+1}^{\timeindex}
   (\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \peleminoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex}) \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

ESS hydrogen outflows over a cycle are constrained by («``eHydMaxEnergyOutflows``», «``eHydMinEnergyOutflows``»):

.. math::
   \sum_{\timeindex'=\timeindex-\poutflowtimestep_{\storageindex}+1}^{\timeindex}
   (\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \phydmaxoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex}) \le 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. math::
   \sum_{\timeindex'=\timeindex-\poutflowtimestep_{\storageindex}+1}^{\timeindex}
   (\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex} - \phydminoutflow_{\periodindex,\scenarioindex,\timeindex',\storageindex}) \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

Incompatibility between charge and outflows for an electricity ESS is defined by («``eIncompatibilityEleChargeOutflows``»):

.. math::
   \frac{\veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxcharge_{\periodindex,\scenarioindex,\timeindex,\storageindex}} \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. note::
   ``eIncompatibilityEleChargeOutflows`` (and its hydrogen counterpart
   ``eIncompatibilityHydChargeOutflows``) are currently disabled in the model
   (commented out in ``oM_ModelFormulation.py``). The relation above documents
   the intended behaviour.

Operation Ramping Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints limit the rate of change in charging and discharging power for ESS.

Maximum ramp-up and ramp-down for charging an electricity ESS («``eEleMaxRampUpCharge``», «``eEleMaxRampDwCharge``»):

.. math::
   \frac{-\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \velefcrddwactch_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \velefcrdupactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\storageindex}}
   \ge -1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{-\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} - \velefcrdupactch_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrddwactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\storageindex}}
   \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Hydrogen storage systems have the same ramping limits, without the frequency-reserve activation terms (hydrogen provides no reserves).

Maximum ramp-up and ramp-down for charging a hydrogen ESS («``eHydMaxRampUpCharge``», «``eHydMaxRampDwCharge``»):

.. math::
   \frac{-\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\storageindex}}
   \ge -1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. math::
   \frac{-\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\storageindex}}
   \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

Maximum ramp-up and ramp-down for the outflows of a hydrogen ESS («``eHydMaxRampUpOutflows``», «``eHydMaxRampDwOutflows``»):

.. math::
   \frac{-\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\storageindex}}
   \le 1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. math::
   \frac{-\vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} + \vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\storageindex}}
   \ge -1
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

Second Block and Reserve Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These constraints define the operational limits for the second block of ESS, including reserve provision.

Maximum and minimum charge of the second block for an electricity ESS («``eEleMaxESSCharge2ndBlock``», «``eEleMinESSCharge2ndBlock``»):

.. math::
   \frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} + \velefcrddwactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} - \velefcrdupactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

Maximum and minimum charge of the second block for a hydrogen ESS («``eMaxHydESSCharge2ndBlock``», «``eHydMinESSCharge2ndBlock``»). As noted above, the bounding mode binary is swapped relative to the electricity case:

.. math::
   \frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \vhydstordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

.. math::
   \frac{\vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\phydmaxchargesecondblock_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \ge 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEHS

Reserve provision from an ESS is constrained by charging and discharging status («``eEleFreqDisUpChargeBound``», «``eEleFreqDisUpDischargeBound``», etc.):

.. math::
   \frac{\velefcrdupactch_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestorchargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

.. math::
   \frac{\velefcrdupactdi_{\periodindex,\scenarioindex,\timeindex,\storageindex}}{\pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\storageindex}}
   \le \velestordischargebin_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

4. Network Constraints
----------------------
These constraints model the physics and limits of the energy transmission and distribution networks.

DC Power Flow
~~~~~~~~~~~~~
For the electricity grid, ``eKirchhoff2ndLaw`` implements a DC power flow model, relating the power flow on a line to the voltage angles at its connecting nodes.

.. math::
   \frac{\vflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}}{\pnettc_{\busindexa,\busindexb,\circuitindex}} -
   \frac{(\vtheta_{\periodindex,\scenarioindex,\timeindex,\busindexa} - \vtheta_{\periodindex,\scenarioindex,\timeindex,\busindexb})}{\pnetreactance_{\busindexa,\busindexb,\circuitindex} \cdot \pnettc_{\busindexa,\busindexb,\circuitindex}} \cdot 0.1 = 0
   \quad \forall \periodindex,\scenarioindex,\timeindex,(\busindexa,\busindexb,\circuitindex) \in \nELA

6. Demand-Side and Reliability Constraints
------------------------------------------
*   **Ramping Limits**: Constraints such as ``eHydMaxRampUpDemand`` and ``eHydMaxRampDwDemand`` limit the rate of change in hydrogen demand, preventing abrupt fluctuations that could destabilize the system.
*   ``eEleDemandShiftBalance``: Ensures that for flexible loads, the total energy consumed is conserved, even if the timing of consumption is shifted.
*   **Unserved Energy**: The model allows for unserved energy through slack variables (``vENS``, ``vHNS``). The high penalty cost in the objective function acts as a soft constraint to meet demand.

..
    Ramping Limits
    ~~~~~~~~~~~~~~
    Ramp up and ramp down for the provision of demand to the hydrogen customers («``eHydMaxRampUpDemand``, ``eHydMaxRampDwDemand``»)

    :math:`\frac{- \vhyddemand_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\demandindex} \!+\! \vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampuprate_{\demandindex}} \leq   1 \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex|\demandindex \in \nDH`

    :math:`\frac{- \vhyddemand_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\demandindex} \!+\! \vhyddemand_{\periodindex,\scenarioindex,\timeindex,\demandindex}}{\ptimestepduration_{\periodindex,\scenarioindex,\timeindex} \prampdwrate_{\demandindex}} \geq \!-\! 1 \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex|\demandindex \in \nDH`

Demand Shifting Balance
~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand shifting balance («``eEleDemandShiftBalance``»)

If :math:`\peledemflexible_{\demandindex} == 1.0` and :math:`\peledemshiftedsteps_{\demandindex} > 0.0`:

.. math::
   \sum_{\timeindex '=\timeindex-\peledemshiftedsteps_{\demandindex}+1}^{\timeindex}
   \veledemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex} =
   \sum_{\timeindex '=\timeindex-\peledemshiftedsteps_{\demandindex}+1}^{\timeindex}
   \pmaxdemand_{\periodindex,\scenarioindex,\timeindex ',\demandindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex

Share of Flexible Demand
~~~~~~~~~~~~~~~~~~~~~~~~~
Flexible electricity demand share of total demand («``eEleDemandShifted``»)

If :math:`\peledemflexible_{\demandindex} == 1.0` and :math:`\peledemshiftedsteps_{\demandindex} > 0.0`:

.. math::
   \veledemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} =
   \pmaxdemand_{\periodindex,\scenarioindex,\timeindex,\demandindex} +
   \veledemflex_{\periodindex,\scenarioindex,\timeindex,\demandindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\demandindex

7. Electric Vehicle (EV) Modeling
---------------------------------
Electric vehicles are modeled as a special class of mobile energy storage, identified by the ``model.egv`` set (a subset of ``model.egs``). They are subject to standard storage dynamics but with unique constraints that reflect their dual role as both a transportation tool and a potential grid asset.

**Key Modeling Concepts:**

*   **Fixed Nodal Connection**: Each EV is assumed to have a fixed charging point at a specific node (``nd``). All its interactions with the grid (charging and vehicle-to-grid discharging) occur at this single location. This means the EV's charging load (``vEleTotalCharge``) is directly added to the demand side of that node's ``eEleBalance`` constraint, while any discharging (``vEleTotalOutput``) is added to the supply side.

*   **Availability Windows**: The availability of the EV for charging or discharging is governed by user behavior patterns, represented through time-dependent constraints:

    *   **Availability for Grid Services**: The :math:`\pvarfixedavailability` parameter indicates when the EV is parked and thus available for grid services. When this parameter is zero, the EV cannot charge or discharge, effectively making it unavailable to the grid. This is enforced by the ``eEleStorageMode`` constraint.

    *   **Charging Flexibility**: The model allows for flexible charging schedules within the availability windows. The EV can choose when to charge based on economic signals, as long as it adheres to the overall energy balance and state-of-charge constraints.

*   **Minimum Starting Charge**: The ``eEleMinEnergyStartUp`` constraint enforces a realistic user behavior: an EV must have a minimum state of charge *before* it can be considered "available" to leave its charging station (i.e., before its availability for grid services can change). This ensures the model doesn't fully drain the battery for grid purposes if the user needs it for a trip.

    .. math::
       \veleinventory_{\periodindex,\scenarioindex,\timeindex-\ptimestep,\storageindex} \ge 0.8 \cdot \pelemaxstorage_{\storageindex}
       \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex \in \nEES

*   **Driving Consumption**: The energy used for driving is modeled as an outflow from the battery. This can be configured in two ways, offering modeling flexibility:

    *   **Fixed Consumption**: By setting the upper and lower bounds of the outflow to the same value in the input data (e.g., ``pEleMinOutflows`` and ``pEleMaxOutflows``), driving patterns can be treated as a fixed, pre-defined schedule. This is useful for modeling commuters with predictable travel needs.
    *   **Variable Consumption**: Setting different upper and lower bounds allows the model to optimize the driving schedule. This can represent flexible travel plans, uncertain trip lengths, or scenarios where the timing of a trip is part of the optimization problem but having a fixed total daily consumption.

    Both approaches are ensure by the constraints ``eEleMaxEnergyOutflows`` and ``eEleMinEnergyOutflows``.

*   **Economic-Driven Charging (Tariff Response)**: The model does not use direct constraints to force EV charging at specific times. Instead, charging behavior is an *emergent property* driven by the objective to minimize total costs. This optimization is influenced by two main types of tariffs:

    *   **Volumetric Tariffs**: The total cost of purchasing energy from the grid (``vTotalEleTradeCost``) includes not just the wholesale energy price but also volumetric network fees (e.g., ``pEleRetnetavgift``). This means the model is incentivized to charge when the *all-in price per MWh* is lowest.
    *   **Capacity Tariffs**: The ``vTotalElePeakCost`` component of the objective function penalizes high monthly power peaks from the grid.

    Since EV charging (``vEleTotalCharge``) increases the total load at a node, the model will naturally schedule it during hours when the combination of volumetric and potential capacity costs is lowest. This interaction between the nodal balance, the cost components, and the objective function creates an economically rational "smart charging" behavior.


8. Bounds on Variables
-----------------------
To ensure numerical stability and solver efficiency, bounds are placed on key decision variables. For example, the state-of-charge variables for storage units are bounded between zero and their maximum capacity.

.. math::
   0 \leq \veleproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGE

.. math::
   0 \leq \vhydproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGH

.. math::
   0 \leq \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   0 \leq \veleconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE

.. math::
   0 \leq \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH

.. math::
   0 \leq \vhydconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE

.. math::
   0 \leq \velesecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGENR

.. math::
   0 \leq \vhydsecondblockproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \phydmaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \phydminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGHE

.. math::
   0 \leq \veleenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \pelemaxoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   0 \leq \vhydenergyoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \phydmaxoutflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH

.. math::
   0 \leq \vPupward_{\periodindex,\scenarioindex,\timeindex,\genindex}, \vPdownward_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \pelemaxproduction_{\periodindex,\scenarioindex,\timeindex,\genindex} \!-\! \peleminproduction_{\periodindex,\scenarioindex,\timeindex,\genindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\genindex|\genindex \in \nGENR

.. math::
   0 \leq \vCupward_{\periodindex,\scenarioindex,\timeindex,\storageindex}, \vCdownward_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \!-\! \peleminconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   0 \leq \velesecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \pelemaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   0 \leq \vhydsecondblockconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \phydmaxconsumption_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH

.. math::
   \pelemininflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq  \veleinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \pelemaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   \phydmininflow_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq  \vhydinventory_{\periodindex,\scenarioindex,\timeindex,\storageindex}  \leq \phydmaxinflow_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH

.. math::
   0 \leq  \velespillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEE

.. math::
   0 \leq  \vhydspillage_{\periodindex,\scenarioindex,\timeindex,\storageindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\storageindex|\storageindex \in \nEH

..
    :math:`0 \leq ec^{R\!+\!}_{\periodindex,\scenarioindex,\timeindex,\storageindex}, ec^{R-}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                        \quad \forall nes`

    :math:`0 \leq ec^{R\!+\!}_{\periodindex,\scenarioindex,\timeindex,\genindex}, ec^{R-}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                        \quad \forall nhz`

    :math:`0 \leq ec^{Comp}_{\periodindex,\scenarioindex,\timeindex,\storageindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\storageindex}                                                     \quad \forall nhs`

    :math:`0 \leq ec^{StandBy}_{\periodindex,\scenarioindex,\timeindex,\genindex} \leq \overline{EC}_{\periodindex,\scenarioindex,\timeindex,\genindex}                                                  \quad \forall nhz`

.. math::
   -\pelemaxrealpower_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex} \leq  \veleflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}  \leq \pelemaxrealpower_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex|(\busindexa,\busindexb,\circuitindex) \in \nLE

.. math::
   -\phydmaxflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex} \leq  \vhydflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}  \leq \phydmaxflow_{\periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex}
   \quad \forall \periodindex,\scenarioindex,\timeindex,\busindexa,\busindexb,\circuitindex|(\busindexa,\busindexb,\circuitindex) \in \nLH


