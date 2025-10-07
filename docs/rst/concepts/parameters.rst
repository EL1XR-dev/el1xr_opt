Parameters
==========

They are written in **uppercase** letters.

==========================================================================================  ===================================================================  ========  ===========================================================================
**Symbol**                                                                                  **Description**                                                      **Unit**  **oM_Modelformulation.py**
------------------------------------------------------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\ptimestepduration_{\periodindex,\scenarioindex,\timeindex}`                         Duration of each time step                                           h         «``pDuration``»
:math:`\pfactorone`                                                                         Unit conversion factor (1,000)                                                 «``factor1``»
:math:`\pdiscountrate_{\periodindex}`                                                       Annual discount factor                                               %         «``pParDiscountRate``»
:math:`\pelebuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`              Cost of electricity bought                                           €/MWh     «``pVarEnergyCost``»
:math:`\pelesellprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`             Price of electricity sold                                            €/MWh     «``pVarEnergyPrice``»
:math:`\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`              Cost of hydrogen bought                                              €/kgH2    «``pHydrogenCost``»
:math:`\phydbuyprice_{\periodindex,\scenarioindex,\timeindex,\eletraderindex}`              Price of hydrogen sold                                               €/kgH2    «``pHydrogenPrice``»
:math:`\pelemarketbuyingratio_{\eletraderindex}`                                            Electricity buying ratio for electricity market region                         «``pEleRetBuyingRatio``»
:math:`\pelemarketsellingratio_{\eletraderindex}`                                           Electricity selling ratio for electricity market region                        «``pEleRetSellingRatio``»
:math:`\pelemarketcertrevenue_{\eletraderindex}`                                            Electricity certificate fee for electricity market region            €/kWh     «``pEleRetelcertifikat``»
:math:`\pelemarketpassthrough_{\eletraderindex}`                                            Electricity pass-through fee for electricity market region           €/kWh     «``pEleRetpaslag``»
:math:`\pelemarketmoms_{\eletraderindex}`                                                   Electricity tax (moms) for electricity market region                           «``pEleRetmoms``»
:math:`\pelemarketnetfee_{\eletraderindex}`                                                 Electricity network fee for electricity market region                €/kWh     «``pEleRetnetavgift``»
:math:`\pelemarkettariff_{\eletraderindex}`                                                 Tariff for electricity market region                                 €/kW      «``pEleRetTariff``»
==========================================================================================  ===================================================================  ========  ===========================================================================