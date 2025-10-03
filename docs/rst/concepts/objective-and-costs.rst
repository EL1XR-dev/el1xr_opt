Objective Function & Costs
==========================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

Parameters
----------

They are written in **uppercase** letters.

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_Modelformulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`DUR_{p,sc,n}`                           Duration of each load level                                          h         «``pDuration``»
:math:`F1`                                     Unit conversion factor (1,000)                                       -         «``factor1``»
:math:`Γ`                                      Annual discount factor                                               %         «``pParDiscountRate``»
:math:`CEB_{nnd},    PES^{DA}_{nnd}`           Cost/price of electricity bought/sold                                €/MWh     «``pVarEnergyCost``, ``pElectricityPrice``»
:math:`CHB_{nnd},    PHS^{DA}_{nnd}`           Cost/price of hydrogen bought/sold                                   €/kgH2    «``pHydrogenCost``, ``pHydrogenPrice``»
:math:`R^{EB}_{er}`                            Electricity buying ratio for electricity market region               -         «``pEleRetBuyingRatio``»
:math:`R^{ES}_{er}`                            Electricity selling ratio for electricity market region              -         «``pEleRetSellingRatio``»
:math:`M^{EF}_{er}`                            Electricity certificate fee for electricity market region            €/MWh     «``pEleRetelcertifikat``»
:math:`M^{ES}_{er}`                            Electricity pass-through fee for electricity market region           €/MWh     «``pEleRetpaslag``»
:math:`M^{ER}_{er}`                            Electricity tax (moms) for electricity market region                 -         «``pEleRetmoms```
:math:`M^{EN}_{er}`                            Electricity network fee for electricity market region                €/MWh     «``pEleRetnetavgift``»
:math:`M^{EP}_{er}`                            Tariff for electricity market region                                 €/MW      «``pEleRetTariff``»
:math:`UP^{SR}_{n},  DP^{SR}_{n}`              Price of :math:`SR` upward and downward secondary reserve            €/MW      «``pOperatingReservePrice_Up_SR``, ``pOperatingReservePrice_Down_SR``»
:math:`UR^{SR}_{n},  DR^{SR}_{n}`              Requirement for :math:`SR` upward and downward secondary reserve     €/MW      «``pOperatingReserveRequire_Up_SR``, ``pOperatingReserveRequire_Down_SR``»
:math:`UEI^{TR}_{n}, DEI^{TR}_{n}`             Expected income of :math:`TR` upward and downward tertiary reserve   €/MW      «``pOperatingReservePrice_Up_TR``, ``pOperatingReservePrice_Down_TR``»
:math:`CENS`                                   Cost of electricity not served. Value of Lost Load (VoLL)            €/MWh     «``pParENSCost``»
:math:`CHNS`                                   Cost of hydrogen not served.                                         €/tH2     «``pParHNSCost``»
=============================================  ===================================================================  ========  ===========================================================================

Variables
----------

They are written in **lowercase** letters.

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_ModelFormulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\alpha`                                 Total system cost                                                    €         «``vTotalSCost``»
:math:`c^{EM}_{p,sc}`                          Net cost of electricity market transactions                          €         «``vTotalEleMCost``»
:math:`c^{HM}_{p,sc}`                          Net cost of hydrogen market transactions                             €         «``vTotalHydMCost``»
:math:`c^{EG}_{p,sc}`                          Generation cost of electricity                                       €         «``vTotalEleGCost``»
:math:`c^{HG}_{p,sc}`                          Generation cost of hydrogen                                          €         «``vTotalHydGCost``»
:math:`c^{E}_{p,sc}`                           Emission cost                                                        €         «``vTotalECost``»
:math:`c^{EC}_{p,sc}`                          Consumption cost of electricity                                      €         «``vTotalEleCCost``»
:math:`c^{HC}_{p,sc}`                          Consumption cost of hydrogen                                         €         «``vTotalHydCCost``»
:math:`c^{ER}_{p,sc}`                          Reliability cost of electricity                                      €         «``vTotalEleRCost``»
:math:`c^{HR}_{p,sc}`                          Reliability cost of hydrogen                                         €         «``vTotalHydRCost``»
:math:`c^{EP}_{p,sc}`                          Power peak cost of electricity                                       €         «``vTotalElePeakCost``»
:math:`em^{C}_{p,sc,n}`                        Cost of electricity market transactions (purchasing)                 €         «``vTotalEleTradeCost``»
:math:`em^{P}_{p,sc,n}`                        Profit of electricity market transactions (sales)                    €         «``vTotalEleTradeProfit``»
:math:`hm^{C}_{p,sc,n}`                        Cost of hydrogen market transactions (purchasing)                    €         «``vTotalHydTradeCost``»
:math:`hm^{P}_{p,sc,n}`                        Profit of hydrogen market transactions (sales)                       €         «``vTotalHydTradeProfit``»
:math:`eb_{p,sc,n,er}`                         Electricity bought from the market                                   MWh       «``vEleBuy``»
:math:`es_{p,sc,n,er}`                         Electricity sold to the market                                       MWh       «``vEleSell``»
:math:`h^{B}_{p,sc,n,hr}`                      Hydrogen bought from the market                                      kgH2      «``vHydBuy``»
:math:`h^{S}_{p,sc,n,hr}`                      Hydrogen sold to the market                                          kgH2      «``vHydSell``»
:math:`eg_{p,sc,n,eg}`                         Electricity output from electricity generator                        MWh       «``vEleTotalOutput``»
:math:`hg_{p,sc,n,hg}`                         Hydrogen output from hydrogen generator                              MWh       «``vHydTotalOutput``»
:math:`ens_{p,sc,n,ed}`                        Electricity not served                                               MWh       «``vENS``»
:math:`hns_{p,sc,n,hd}`                        Hydrogen not served                                                  kgH2      «``vHNS``»
:math:`peak_{p,sc,m,er,peak}`                  Electricity peak demand for tariff calculation                       MW        «``vElePeak``»
=============================================  ===================================================================  ========  ===========================================================================


The main objective function is defined by the Pyomo constraint ``eTotalSCost``, which minimizes the variable ``vTotalSCost``.

Total System Cost
-----------------

The total system cost is the sum of all discounted costs across every period (:math:`p`) and scenario (:math:`sc`) in the model horizon. The objective function can be expressed conceptually as:

Total system cost in [Cost-unit] («``eTotalSCost``»)

.. math::
   \min \alpha

And the total cost is the sum of all operational costs, discounted to present value («``eTotalTCost``»):

.. math::
   \alpha = \sum_{p \in P, sc \in SC} Γ_{p} \times (c^{EM}_{p,sc} + c^{HM}_{p,sc} + c^{EG}_{p,sc} + c^{HG}_{p,sc} + c^{E}_{p,sc} + c^{EC}_{p,sc} + c^{HC}_{p,sc} + c^{ER}_{p,sc} + c^{HR}_{p,sc} + c^{EP}_{p,sc})

Key Cost Components
-------------------

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

#.  **Market Costs** (``eTotalEleMCost``, ``eTotalHydMCost``)
    This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

    *   Cost components: ``em^{C}_{p,sc,n}``, ``hm^{C}_{p,sc,n}``
    *   Revenue components: ``em^{P}_{p,sc,n}``, ``hm^{P}_{p,sc,n}``

    #.  **Electricity Purchase**: The cost incurred from purchasing electricity from the market. This cost is defined by the constraint ``eTotalEleTradeCost`` and includes variable energy costs, taxes, and other fees.

        .. math::
           em^{C}_{p,sc,n} = &\sum_{er \in ER} DUR_{p,sc,n} \times ((CEB_{p,sc,n,er} \times M^{EF}_{er} + \\
           & M^{EF}_{er} \times F1 + M^{ES}_{er} \times F1) \times (1 + M^{ER}_{er} \times F1) + M^{EN}_{er} \times F1) \times eb_{p,sc,n,er}

    #.  **Electricity Sales** (``vTotalEleTradeProfit``): The revenue generated from selling electricity to the market. This is defined by the constraint ``eTotalEleTradeProfit``.

        .. math::
           \text{vTotalEleTradeProfit}_{p,sc,n} = \sum_{er \in ER} \text{pDuration}_{p,sc,n} \times (\text{pVarEnergyPrice}_{er,p,sc,n} \times \text{pEleRetSellingRatio}_{er} \times \text{vEleSell}_{p,sc,n,er})

    #.  **Hydrogen Purchase** (``vTotalHydTradeCost``): The cost incurred from purchasing hydrogen from the market, as defined by ``eTotalHydTradeCost``.

        .. math::
           \text{vTotalHydTradeCost}_{p,sc,n} = \sum_{hr \in HR} \text{pDuration}_{p,sc,n} \times (\text{pVarEnergyCost}_{hr,p,sc,n} \times \text{vHydBuy}_{p,sc,n,hr})

    #.  **Hydrogen Sales** (``vTotalHydTradeProfit``): The revenue generated from selling hydrogen to the market, as defined by ``eTotalHydTradeProfit``.

        .. math::
           \text{vTotalHydTradeProfit}_{p,sc,n} = \sum_{hr \in HR} \text{pDuration}_{p,sc,n} \times (\text{pVarEnergyPrice}_{hr,p,sc,n} \times \text{vHydSell}_{p,sc,n,hr})

#.  **Generation Costs (`vTotalEleGCost`, `vTotalHydGCost`)**
    This is the operational cost of running the generation and production assets. It typically includes:
    *   **Variable Costs**: Proportional to the energy produced (e.g., fuel costs).
    *   **No-Load Costs**: The cost of keeping a unit online, even at minimum output.
    *   **Start-up and Shut-down Costs**: Costs incurred when changing a unit's commitment state.

    The cost is defined by ``eTotalEleGCost`` for electricity and ``eTotalHydGCost`` for hydrogen.

    .. math::
       \text{vTotalEleGCost}_{p,sc,n} = \sum_{eg \in EG} \text{pDuration}_{p,sc,n} \times (
       & \text{pEleGenLinearVarCost}_{eg} \times \text{vEleTotalOutput}_{p,sc,n,eg} + \\
       & \text{pEleGenOMVariableCost}_{eg} \times \text{vEleTotalOutput}_{p,sc,n,eg}) + \\
       & \sum_{egt \in EGT} \text{pDuration}_{p,sc,n} \times (
       \text{pEleGenConstantVarCost}_{egt} \times \text{vEleGenCommitment}_{p,sc,n,egt} + \\
       & \text{pEleGenStartUpCost}_{egt} \times \text{vEleGenStartUp}_{p,sc,n,egt} + \\
       & \text{pEleGenShutDownCost}_{egt} \times \text{vEleGenShutDown}_{p,sc,n,egt})

    .. math::
       \text{vTotalHydGCost}_{p,sc,n} = \sum_{hg \in HG} \text{pDuration}_{p,sc,n} \times (
       & \text{pHydGenLinearVarCost}_{hg} \times \text{vHydTotalOutput}_{p,sc,n,hg} - \\
       & \text{pHydGenOMVariableCost}_{hg} \times \text{vHydTotalOutput}_{p,sc,n,hg}) + \\
       & \sum_{hgt \in HGT} \text{pDuration}_{p,sc,n} \times (
       \text{pHydGenConstantVarCost}_{hgt} \times \text{vHydGenCommitment}_{p,sc,n,hgt} + \\
       & \text{pHydGenStartUpCost}_{hgt} \times \text{vHydGenStartUp}_{p,sc,n,hgt} + \\
       & \text{pHydGenShutDownCost}_{hgt} \times \text{vHydGenShutDown}_{p,sc,n,hgt})

#.  **Emission Costs (`vTotalECost`)**
    This component captures the cost of carbon emissions from fossil-fueled generators. It is calculated by multiplying the CO2 emission rate of each generator by its output and the carbon price (``pGenCO2EmissionCost``). The formulation is defined by ``eTotalECost``.

    .. math::
       \text{vTotalECost}_{p,sc,n} = \sum_{egt \in EGT} \text{pDuration}_{p,sc,n} \times \text{pGenCO2EmissionCost}_{egt} \times \text{vEleTotalOutput}_{p,sc,n,egt}

#.  **Consumption Costs (`vTotalEleCCost`, `vTotalHydCCost`)**
    This represents the costs associated with operating energy consumers within the system, most notably the cost of power used to charge energy storage devices. These are defined by ``eTotalEleCCost`` and ``eTotalHydCCost``.

    .. math::
       \text{vTotalEleCCost}_{p,sc,n} = \sum_{egs \in EGS} \text{pDuration}_{p,sc,n} \times \text{pEleGenLinearTerm}_{egs} \times \text{vEleTotalCharge}_{p,sc,n,egs}

    .. math::
       \text{vTotalHydCCost}_{p,sc,n} = \sum_{hgs \in HGS} \text{pDuration}_{p,sc,n} \times \text{pHydGenLinearTerm}_{hgs} \times \text{vHydTotalCharge}_{p,sc,n,hgs}

#.  **Reliability Costs (`vTotalEleRCost`, `vTotalHydRCost`)**
    This is a penalty cost applied to any energy demand that cannot be met. It is calculated by multiplying the amount of unserved energy by a very high "value of lost load" (``pParENSCost`` or ``pParHNSCost``), ensuring the model prioritizes meeting demand. The associated constraints are ``eTotalEleRCost`` and ``eTotalHydRCost``.
    *   Associated variables: ``vENS`` (Energy Not Supplied), ``vHNS`` (Hydrogen Not Supplied).

    .. math::
       \text{vTotalEleRCost}_{p,sc,n} = \sum_{ed \in ED} \text{pDuration}_{p,sc,n} \times \text{pParENSCost} \times \text{vENS}_{p,sc,n,ed}

    .. math::
       \text{vTotalHydRCost}_{p,sc,n} = \sum_{hd \in HD} \text{pDuration}_{p,sc,n} \times \text{pParHNSCost} \times \text{vHNS}_{p,sc,n,hd}

#.  **Peak Demand Costs (`vTotalElePeakCost`)**
    This component models capacity-based tariffs, where costs are determined by the highest power peak registered during a specific billing period (e.g., a month). This incents the model to "shave" demand peaks to reduce costs. The formulation is defined by ``eTotalElePeakCost``.

    .. math::
       \text{vTotalElePeakCost}_{p,sc} = \frac{1}{|\text{Peaks}|} \sum_{er \in ER} \text{pEleRetTariff}_{er} \times \text{factor1} \times \sum_{m \in \text{moy}} \sum_{\text{peak} \in \text{Peaks}} \text{vElePeak}_{p,sc,m,er,\text{peak}}

By minimizing the sum of these components, the model finds the most economically efficient way to operate the system's assets to meet energy demand reliably.