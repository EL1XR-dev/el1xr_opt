Parameters
==========

They are written in **uppercase** letters.

=============================================  ===================================================================  ========  ===========================================================================
**Symbol**                                     **Description**                                                      **Unit**  **oM_Modelformulation.py**
---------------------------------------------  -------------------------------------------------------------------  --------  ---------------------------------------------------------------------------
:math:`\ptimestepduration_{p,sc,n}`            Duration of each time step                                           h         «``pDuration``»
:math:`\pfactorone`                            Unit conversion factor (1,000)                                                 «``factor1``»
:math:`\pdiscountrate_{p}`                     Annual discount factor                                               %         «``pParDiscountRate``»
:math:`\pelebuyprice_{p,sc,n,er}`              Cost of electricity bought                                           €/MWh     «``pVarEnergyCost``»
:math:`\pelesellprice_{p,sc,n,er}`             Price of electricity sold                                            €/MWh     «``pVarEnergyPrice``»
:math:`\phydbuyprice_{p,sc,n,er}`              Cost of hydrogen bought                                              €/kgH2    «``pHydrogenCost``»
:math:`\phydbuyprice_{p,sc,n,er}`              Price of hydrogen sold                                               €/kgH2    «``pHydrogenPrice``»
:math:`\pelemarketbuyingratio_{er}`            Electricity buying ratio for electricity market region                         «``pEleRetBuyingRatio``»
:math:`\pelemarketsellingratio_{er}`           Electricity selling ratio for electricity market region                        «``pEleRetSellingRatio``»
:math:`\pelemarketcertrevenue_{er}`            Electricity certificate fee for electricity market region            €/MWh     «``pEleRetelcertifikat``»
:math:`\pelemarketpassthrough_{er}`            Electricity pass-through fee for electricity market region           €/MWh     «``pEleRetpaslag``»
:math:`\pelemarketmoms_{er}`                   Electricity tax (moms) for electricity market region                           «``pEleRetmoms```
:math:`\pelemarketnetfee_{er}`                 Electricity network fee for electricity market region                €/MWh     «``pEleRetnetavgift``»
:math:`\pelemarkettariff_{er}`                 Tariff for electricity market region                                 €/MW      «``pEleRetTariff``»
=============================================  ===================================================================  ========  ===========================================================================