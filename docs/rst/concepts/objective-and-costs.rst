Objective Function & Costs
==========================

The core purpose of the optimization model is to minimize the total system cost over a specified time horizon. This is achieved through an objective function that aggregates all relevant operational expenditures, as well as penalties for undesirable outcomes like unmet demand.

Parameters
----------

They are written in **uppercase** letters.

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_Modelformulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`DUR_n`                                  Duration of each load level                                          h         «``pDuration``»
:math:`factor1`                                Unit conversion factor (1,000)                                       -         «``factor1``»
:math:`Γ`                                      Annual discount factor                                               %         «``pParDiscountRate``»
:math:`CEB_{nnd},    PES^{DA}_{nnd}`           Cost/price of electricity bought/sold                                €/MWh     «``pElectricityCost``, ``pElectricityPrice``»
:math:`CHB_{nnd},    PHS^{DA}_{nnd}`           Cost/price of hydrogen bought/sold                                   €/kgH2    «``pHydrogenCost``, ``pHydrogenPrice``»
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
**Symbol**                                     **Description**                                                      **Unit**  **oHySEM.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\alpha`                                 Total cost                                                           €         «``vTotalSCost``»
:math:`c^{EM}_{p,sc}`                          Total cost of electricity market transactions                        €         «``vTotalEleMCost``»
:math:`c^{HM}_{p,sc}`                          Total cost of hydrogen market transactions                           €         «``vTotalHydMCost``»
:math:`c^{EG}_{p,sc}`                          Total generation cost of electricity                                 €         «``vTotalEleGCost``»
:math:`c^{HG}_{p,sc}`                          Total generation cost of hydrogen                                    €         «``vTotalHydGCost``»
:math:`c^{E}_{p,sc}`                           Total emission cost                                                  €         «``vTotalECost``»
:math:`c^{EC}_{p,sc}`                          Total consumption cost of electricity                               €         «``vTotalEleCCost``»
:math:`c^{HC}_{p,sc}`                          Total consumption cost of hydrogen                                  €         «``vTotalHydCCost``»
:math:`c^{ER}_{p,sc}`                          Total reliability cost of electricity                                €         «``vTotalEleRCost``»
:math:`c^{HR}_{p,sc}`                          Total reliability cost of hydrogen                                   €         «``vTotalHydRCost``»
:math:`c^{EP}_{p,sc}`                          Total power peak cost of electricity                                 €         «``vTotalElePeakCost``»
=============================================  ===================================================================  ========  ===========================================================================


The main objective function is defined by the Pyomo constraint ``eTotalSCost``, which minimizes the variable ``vTotalSCost``.

Total System Cost :math:`\alpha`
---------------------------------

The total system cost is the sum of all discounted costs across every period (:math:`p`) and scenario (:math:`sc`) in the model horizon. The objective function can be expressed conceptually as:

Total system cost in [Cost-unit] («``eTotalSCost``»)

.. math::
   \min \alpha

And the total cost is the sum of all operational costs, discounted to present value («``eTotalTCost``»):

.. math::
   \alpha = \sum_{p \in P, sc \in SC} Γ_{p} \times (
   & c^{EM}_{p,sc} + c^{HM}_{p,sc} + \\
   & c^{EG}_{p,sc} + c^{HG}_{p,sc} + \\
   & c^{E}_{p,sc} + \\
   & c^{EC}_{p,sc} + c^{HC}_{p,sc} + \\
   & c^{ER}_{p,sc} + c^{HR}_{p,sc} + \\
   & c^{EP}_{p,sc})

Where:

- **pDiscountFactor** is defined as :math:`\frac{1}{(1 + r)^{(t_p / 8760)}}`, where :math:`r` is the annual discount rate (``pParDiscountRate``) and :math:`t_p` is the time in hours from the start of the horizon to the start of period :math:`p`. It is used to convert future costs into present value, accounting for the time value of money.
- **vTotalEleMCost**, **vTotalHydMCost** are the total market costs for electricity and hydrogen, respectively.
- **vTotalEleGCost**, **vTotalHydGCost** are the total generation costs for electricity and hydrogen, respectively.
- **vTotalECost** is the total emission cost.
- **vTotalEleCCost**, **vTotalHydCCost** are the total consumption costs for electricity and hydrogen, respectively.
- **vTotalEleRCost**, **vTotalHydRCost** are the total reliability costs for electricity and hydrogen, respectively.
- **vTotalElePeakCost** is the total power peak cost for electricity.

Key Cost Components
-------------------

The total cost is broken down into several components, each represented by a specific variable. The model seeks to find the optimal trade-off between these costs.

#.  **Market Costs** (``vTotalEleMCost``, ``vTotalHydMCost``)
    This represents the net cost of trading with external markets. It is calculated as the cost of buying energy minus the revenue from selling energy.

    *   Cost components: ``vTotalEleTradeCost``, ``vTotalHydTradeCost``
    *   Revenue components: ``vTotalEleTradeProfit``, ``vTotalHydTradeProfit``

    #.  **Electricity Purchase** (``vTotalEleTradeCost``): The cost incurred from purchasing electricity from the market. This cost is defined by the constraint ``eTotalEleTradeCost`` and includes variable energy costs, taxes, and other fees.

        .. math::
           \text{vTotalEleTradeCost}_{p,sc,n} =
           & \sum_{er \in ER} \text{pDuration}_{p,sc,n} \times (\\
           & (\text{pVarEnergyCost}_{er,p,sc,n} \times \text{pEleRetBuyingRatio}_{er} + \\
           & \text{pEleRetelcertifikat}_{er} \times \text{factor1} + \\
           & \text{pEleRetpaslag}_{er} \times \text{factor1}) \times \\
           & (1 + \text{pEleRetmoms}_{er} \times \text{factor1}) + \\
           & \text{pEleRetnetavgift}_{er} \times \text{factor1}) \times \text{vEleBuy}_{p,sc,n,er}

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