Parameters
==========

They are written in **uppercase** letters.

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_Modelformulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`DUR_{p,sc,n}`                           Duration of each load level                                          h         «``pDuration``»
:math:`F1`                                     Unit conversion factor (1,000)                                       -         «``factor1``»
:math:`Γ`                                      Annual discount factor                                               %         «``pParDiscountRate``»
:math:`CEB_{p,sc,n,er}, PES_{p,sc,n,er}`       Cost/price of electricity bought/sold                                €/MWh     «``pVarEnergyCost``, ``pElectricityPrice``»
:math:`CHB_{p,sc,n,er}, PHS_{p,sc,n,er}`       Cost/price of hydrogen bought/sold                                   €/kgH2    «``pHydrogenCost``, ``pHydrogenPrice``»
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