# Data sources for the FCR VPP case

Citable real-world data for the `H2VPPFCR` case study. Every figure here has a
source; nothing is invented. Where a number still needs the model author's or
Erik's confirmation (units, project-specific values), it is flagged.

The case is framed on a real initiative: the **High Coast to West Coast Hydrogen
Valley (HiWhyV)**, coordinated by RISE — a €19.8 M Clean Hydrogen Partnership
project linking renewable hydrogen production to industrial and transport demand
on Sweden's west coast, with e-methanol for shipping and aviation among the end
uses. This makes wind + electrolyser + hydrogen for heavy transport / shipping a
real, locally grounded setting.

- HiWhyV overview (RISE): https://www.ri.se/en/news/major-project-for-hydrogen-production-in-vasternorrland-and-western-sweden
- HiWhyV (EU STEP platform): https://strategic-technologies.europa.eu/step-results/step-stories/hiwhyv_en
- Port of Gothenburg heavy-truck green-hydrogen station: https://www.hydrogenfuelnews.com/swedens-green-hydrogen-station/8567508/

## Techno-economic parameters

| Quantity | Value | Source |
|---|---|---|
| Electrolyser specific energy (PEM) | ~48 kWh/kgH2 | electrolysis review (Enagás OTH 2025) |
| Electrolyser specific energy (alkaline) | ~50 kWh/kgH2 | electrolysis review (Enagás OTH 2025) |
| Electrolyser efficiency (LHV) | 60-70 % | electrolysis review (Enagás OTH 2025) |
| Electrolyser CAPEX (2030) | AEL 550 / PEM 650 EUR/kW (per kW electricity input) | DEA Technology Data 2024, sheets "1.1 AEC 100 MW" / "1.1 PEMEC 100 MW" |
| Battery round-trip efficiency | 85 % | NREL ATB 2024 (utility-scale) |
| Battery CAPEX (4 h utility-scale, 2024) | ~334 USD/kWh | NREL ATB 2024 |
| Onshore wind capacity factor (global, 2023) | 36 % | IRENA / Statista (Swedish onshore is typically lower, ~30-35 %) |
| Heavy-duty H2 refuelling station size | small 50-300, medium 300-1,200, large 1,000-4,000 kgH2/day | DOE / industry (FleetOwner, ScienceDirect) |
| Class-8 truck refuel | ~60 kgH2 | FleetOwner |

Sources:
- Danish Energy Agency, Technology Data (electrolysis, batteries, hydrogen storage): https://ens.dk/en/our-services/technology-catalogues
- Electrolysis state-of-the-art (Enagás Hydrogen Technology Observatory, 2025): https://www.enagas.es/content/dam/enagas/en/files/transicion-energetica/red-hidrogeno/observatorio-tecnologico-hidrogeno/oth-report-electrolysis-dic2025-eng.pdf
- NREL Annual Technology Baseline 2024, utility-scale battery storage: https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage
- IRENA / Statista onshore wind capacity factor 2023: https://www.statista.com/statistics/1498940/global-onshore-wind-energy-capacity-factor/
- Heavy-duty hydrogen refuelling demand: https://www.fleetowner.com/emissions-efficiency/article/55020801/

## Hydrogen demand temporal profiles

The daily volumes are set per sector (HRS ~1,500, industrial ~1,000, bunkering
~500 kgH2/day); the **hourly shapes** (`_sector_profile` in `build_case.py`) are
literature-grounded. Honesty note for the methods: only the industrial flat
baseload rests on a directly applicable source; the truck shape is a diesel-HDV
traffic **analogue** (no measured heavy-duty H2 station hourly data exists), and
the bunkering shape is a **designed scenario** (no operational H2 bunkering at
Gothenburg yet). State this explicitly in the paper.

| Sector | Hour-of-day | Weekday/weekend | Seasonal | Basis |
|---|---|---|---|---|
| HRS (truck) | morning ramp, midday plateau, overnight trough (peak ~7% of daily) | Sat 0.60, Sun 0.35 | Swedish July/Aug industrisemester dip | diesel-HDV traffic analogue |
| Industrial | flat 24/7 | none | none (6-yearly turnaround not applied in a representative year) | continuous process feedstock |
| Bunkering | daytime working-hours block (07-19) | Sat 0.7, Sun 0.5 | flat (ice-free port) | port-call / methanol-bunkering analogue |

Sources:
- Liu et al. (ORNL, 2022), HDV refuelling diurnal profile from measured diesel truck-stop data: https://www.osti.gov/biblio/1876290
- Hallenbeck & Rice (1997), vehicle volume distributions by classification (weekday/weekend truck factors): https://rosap.ntl.bts.gov/view/dot/48834
- Kurtz et al. (2020), predicting demand for hydrogen station fueling (only directly-measured H2 station hourly curve; light-duty): https://doi.org/10.1016/j.ijhydene.2019.10.014
- SCB Industrial Production Index (Swedish July industrisemester monthly trough): https://www.scb.se
- Kirchem & Schill (2023), flat hourly industrial H2 demand assumption: https://doi.org/10.1016/j.enpol.2023.113503
- Argus (2023), first ship-to-ship methanol bunkering at Gothenburg (green-fuel bunkering analogue): https://www.argusmedia.com/en/news-and-insights/latest-market-news/2412817

## Frequency-reserve prices (Sweden)

Nordic FCR capacity prices from Svenska kraftnät (the Swedish TSO). October 2024
monthly averages (capacity payment, EUR/MW per hour):

| Product | ~Price (Oct 2024) |
|---|---|
| FCR-N | ~29.9 EUR/MW/h |
| FCR-D up | ~6.9 EUR/MW/h |
| FCR-D down | ~4.1 EUR/MW/h |

FCR-N pays more than FCR-D because it is a continuously regulating, symmetric
product; FCR-D is a disturbance reserve activated only on large deviations.

Sources:
- Svenska kraftnät, monthly FCR/aFRR/mFRR price reports: https://www.svk.se/press-och-nyheter/nyheter/balansansvar/2025/manadsrapporter-om-priser-pa-fcr-afrr-och-mfrr/
- Svenska kraftnät, Mimer data portal (historical FCR prices by zone): https://mimer.svk.se/primaryregulation/primaryregulationindex

## Units: how the real numbers go in

`el1xr_opt` is **unit- and currency-agnostic with one declared currency** (no FX
in the model; the old `[MEUR]` comment at `oM_InputData.py:281` is stale per the
model's own `docs/factor1_electrolyser_dev_plan.md`). The shipped `H2VPP/Home1`
base case is already in physical units — power in kW, energy in kWh, hydrogen in
kgH2, money in SEK — and its prices are realistic (energy tax ~0.549 SEK/kWh,
FCR-N ~0.22 SEK/kW/h). Only the *investment* costs are illustrative.

`factor1` is the model's numerical-conditioning scale, and it is verified to work:
it is a true unit conversion that leaves the optimum unchanged (the invariance
test `test_sizing_factor1_invariant` passes for the Electrolyser and
H2TankCompressor sizing cases — solving at factor1 = 1 vs 2 gives the same cost
and decisions). It does not reconcile inconsistent inputs; it just rescales a
consistent problem.

So the real data above goes straight in, in one consistent system:
- keep power in kW, energy in kWh, hydrogen in kgH2;
- pick one currency (SEK to match the base case) and convert EUR figures at a
  stated rate — a data-prep step, cited, not a model conversion;
- so FCR prices become SEK/kW/h, energy prices SEK/kWh, CAPEX SEK/kW.

### Exchange rates (documented basis)

Conversions use the **European Central Bank euro foreign exchange reference
rates, 2024 annual average**. The annual average is used on purpose: capex is a
multi-year cost basis, so a single day's (or hour's) fixing would add noise with
no economic meaning. The ECB daily reference rate is itself one fixing published
each TARGET working day at about 16:00 CET, and the annual average is the mean of
those daily fixings over the year. We use **2025** (the same reference year as the
market data below).

| Pair | 2025 annual average | Use |
|---|---|---|
| EUR/SEK | 11.0671 | EUR figures (electrolyser, tank capex) -> SEK |
| EUR/USD | 1.1306 | to derive USD/SEK |
| USD/SEK | 11.0671 / 1.1306 = 9.79 | USD figures (battery capex) -> SEK |

USD/SEK is taken as the cross-rate (EUR/SEK divided by EUR/USD), not a separately
quoted average, so all three sit on one consistent ECB basis. These rates live in
`build_case.py` (`EUR_SEK`, `USD_SEK`). If a different reference year is wanted,
change them there and update this table.

## Real 2025 time series (the model's calibrated profiles)

Fetched into `experiments/h2vpp_fcr/inputs/real_data/year/` for the **full 2025
year (8736 h = 52 weeks)**, bidding zone **SE3** (Sweden west coast / Gothenburg,
the hydrogen-valley demand side). A week or month run slices the first N hours of
the year (from 2025-01-01; `HORIZON_START_HOUR` shifts the window). All cited in
`notes/data_sources.bib`.

| Series | File | Source | Range (full year, min/mean/max) |
|---|---|---|---|
| Day-ahead spot price | `year/spot_se3.csv` | ENTSO-E Transparency Platform (via elptools `fetch_day_ahead`) | -25 / 46 / 486 EUR/MWh |
| FCR capacity prices | `year/fcr_se.csv` | Svenska kraftnät Mimer (via elptools `fetch_fcr_prices`) | FCR-N mean ~27, FCR-D up ~6, FCR-D down ~6 EUR/MW |
| Site wind capacity factor | `year/wind_se3.csv` | ERA5 (Copernicus) via atlite, Vestas V112 3 MW at 57.5N, 12.1E | mean CF 0.305 (Swedish onshore ~30-35%); 1.9% h at rated, 9.8% h near zero |

The wind profile is **site-specific** (a single coastal SE3 location), not the SE3
zonal aggregate: aggregating all farms in a price zone smooths out the variability
a single VPP actually sees, which would bias against storage and reserve value.
The FCR price is a single national clearing price across SE1--SE4 (so zone-
independent); spot and wind are SE3-specific.

Sources:
- ECB euro foreign exchange reference rates (daily and annual): https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- ECB Swedish krona reference rate series: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-sek.en.html
- ECB US dollar reference rate series: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html

The one real subtlety left is **investment annualisation versus the operational
horizon**: `FixedInvestmentCost x FixedChargeRate` is an annual charge, but the
solved horizon is one day, so an annual CAPEX charged against one day looks ~365x
too dear and nothing is built. Use representative-period weighting (or annualise
the operation) so sizing is economically sensible — this is the lever to get the
electrolyser built and bidding under three-state.

## FCR activation record (added 2026-07-05 — provenance gap found during the bug fix)

The per-hour FCR activation coefficients (kappa: FCRD_Up/Down, FCRN_Up/Down) are NOT a
documented 2025 series: they are seeded from the el1xr `Home1` demo case
(`model/data/Home1/oM_Data_OperatingReserveActivation_Home1.csv`) and tiled to the year
by build_case. The seed's own provenance is unrecorded. Two consequences:

1. The raw seed carries per-hour ONE-WAY FCR-N activation (an hourly net-energy record),
   which is unphysical for a continuous symmetric product and created the free-energy
   artifact fixed on 2026-07-04/05 (see notes/bug_fcrn_activation_channel_2026-07-04.md).
   build_case now writes the gross-symmetric pair kappa_up = kappa_dn = (up+dn)/2 by
   default (`ACT_GROSS_SYM=0` restores the raw seed).
2. TODO (paper honesty, Erik to decide): either document the seed's origin, or replace
   the record with one derived from measured Nordic frequency data (per-hour fraction of
   time outside the FCR-N deadband, by direction — computable from public frequency
   series). The paper's fig_activation and the kappa values in eq (activation) rest on
   this record.

UPDATE 2026-07-05: the real record is now IN USE. `build_kappa_year.py` fetches Fingrid
dataset 177 (Nordic frequency, 3-min, full 2025: 174,954 samples) and derives per-hour
activation degrees -> `real_data/year/fcr_activation_2025.csv` (8736 h). Statistics:
FCR-N mean duty 0.110 up / 0.108 down, both directions active in 98.1% of hours;
FCR-D mean 0.0002 (rare, shallow; 3-min sampling under-resolves the seconds-scale
excursions -- indicative only). build_case prefers this record (REAL_KAPPA=0 falls back
to the symmetrised Home1 seed). NOTE for Methods: the bids are applied to the symmetric
per-hour MEAN of the measured FCR-N pair -- even the real record has unequal up/down
duties within each hour, and a deterministic perfect-foresight model would cherry-pick
the net direction (an information rent no provider has; worth ~55 kSEK/week in a test).
The duty/churn profile is preserved; the unforeseeable net drift belongs to the
settlement layer (RESERVE_DELIVERY).
