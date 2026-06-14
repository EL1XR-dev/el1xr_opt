# Literature review: electrolyser FCR provision and co-sizing

Working document seeding the related-work and novelty sections of the planned paper on
electrolyser frequency containment reserve (FCR) in a MILP unit-commitment + investment model.
Reviews the five papers downloaded to `temp/papers_H2` (the paywalled set), plus the open-access
prior art already identified (Saretta 2023 and the techno-economic references surfaced in the
intros). Date: 2026-06-14.

## What we claim (to test against the literature)

Our model (already implemented in `oM_ModelFormulation.py` / `oM_Investment.py`):

- **(core)** A MILP unit-commitment **with investment/sizing** in which an electrolyser provides
  **FCR-D and FCR-N** as a controllable load (FCR-up = reduce consumption, FCR-down = increase
  consumption).
- **(b)** FCR-**down** provision endurance is bounded by **hydrogen-tank headroom at the node**:
  the extra hydrogen the electrolysers at a node would make while holding a down-bid over the
  endurance window must fit in the empty headroom of the H2 stores at that node.
- **(c)** **Joint co-sizing** of electrolyser + hydrogen tank (+ intended: compressor) where **FCR
  revenue is part of the capex business case**.

## Summary verdict

| Paper | Type | Electrolyser FCR by load modulation? | FCR-down + storage endurance? | Sizing/investment + FCR revenue? | Threat to our novelty |
|---|---|---|---|---|---|
| Ribeiro 2023 (Iberian, SEGAN) | Dynamic sim (swing eq.) | Yes (up only; FCR+SI+FFR) | No storage, no down-reserve | No (capacity exogenous; economics deferred) | **Closest prior art — but threatens nothing.** Cite for the qualitative claim. |
| Phan 2024 (IJHE) | Control/dynamic (droop+MPC) | Yes (up + down) | **Tank-limit mode-switch (dynamic), not an MILP constraint** | No economics, no sizing | Closest on (b) physically — cite as precedent; (b) as optimization constraint still novel |
| Ye 2026 (Applied Energy) | Multiphysics + HIL | Yes (droop; no D/N naming) | No | No | None — supports physical realism |
| Elhawash 2025 (IJHE) | PHIL hardware | Yes (FCR + FFR) | No (buffer assumed, not modelled) | No | None — hardware-validation citation |
| Ranaboldo 2024 (RSER) | Review (industrial DR) | No (only Al-smelter as curtailable load) | No | No | None — context/motivation only |

**Bottom line:** none of the five downloaded papers threaten (b) or (c). Four are at the
dynamics/control/hardware layer (sub-30-second frequency response); one is an industrial-demand-
response review. They are excellent *supporting* citations for physical realism and motivation, but
the real novelty risk for (c) lives in techno-economic MILP papers that are **not** in this set —
see "Critical gap" below.

---

## Paper 1 — Ribeiro et al. 2023 (closest prior art)

**The role of hydrogen electrolysers in frequency related ancillary services: A case study in the
Iberian Peninsula up to 2040.** F. J. Ribeiro, J. A. Peças Lopes, F. S. Fernandes, F. J. Soares,
A. G. Madureira. *Sustainable Energy, Grids and Networks* 35 (2023) 101084.
DOI 10.1016/j.segan.2023.101084. **Type:** MATLAB/Simulink electromechanical (swing-equation)
dynamic simulation — NOT optimization, scheduling, or capacity expansion.

**Section-by-section.**
- *Intro:* EU Hydrogen Strategy framing; rising RES lowers inertia; electrolysers (HEs) are
  controllable loads. Defines "critical inertia" (min inertia so reserves deploy before first
  under-frequency load shedding). Research question: can HEs providing reserve reduce the critical
  inertia in the Iberian Peninsula (IP)? Innovation claimed = large fleet (8 GW) collective response.
- *Methodology:* Two-area model (IP + Continental Europe), swing equation
  `df = (ΔP_G − ΔP_L)/(2H·s+D) + ΔP₁₋₂`, tie-line `ΔP₁₋₂ = Δδ·T·2πf`. Violation thresholds: nadir
  < 49.2 Hz, quasi-steady < 49.8 Hz, RoCoF > 1 Hz/s. Contingency = instantaneous 3 GW IBR (PV/wind)
  trip. Conventional FCR from coal/nuclear/gas (TGOV1)/hydro, aggregated one unit per area per tech.
  Calibrated against the 2011 Almaraz II 1 GW loss via particle swarm.
- *HE model:* "Seen from the grid, upward reserve from a generator = a load decrease in a HE." HEs
  assumed at nominal power at the contingency, so they provide **upward reserve only** (load
  reduction); the symmetric down-reserve is assumed handled by curtailable solar/wind. Three control
  loops = three services: FCR (droop −1/R, full activation < 49.8 Hz), Synthetic Inertia (responds to
  df/dt, gain K=5), FFR (step at 49.8 Hz). Each loop bounded by [0, AS-volume]; min = 0 (never
  down-reserve).
- *2040 parameters:* All IP coal gone by 2030, conventional by 2035. 12 GW HE in IP (8 GW PEM
  modelled) — **exogenous, from forecast [33]**, not optimized. PEM ramps 2.5 pu/s (fast) / 0.5 pu/s
  (slow). H_IP,2040 = 2.95 pu·s. Tie-line to 6.5 GW by 2040.
- *Results:* Conventional FCR → RoCoF 0.83 Hz/s (near 1 Hz/s limit), uses only ~25% of the 430 MW IP
  FCR volume. HE FCR → fully uses 430 MW, RoCoF 0.63 Hz/s; ramp/comms-delay improvements barely help
  (0.63→0.60). Adding SI/FFR: SI > FFR for RoCoF; gains saturate beyond ~430 MW extra. Main outcome
  (Fig. 13): for RoCoF ≤ 0.6 Hz/s target, critical inertia falls from ~8 pu·s (conventional FCR) to
  ~4.2 pu·s (HE FCR) to < 3 pu·s (large fast-HE SI). Nadirs across 28 sims: 49.69–49.78 Hz.
- *Conclusions:* HEs outperform conventional FCR on RoCoF and reduce critical inertia.
  **"Future work will address the economics of FCR provision by HEs in existing markets."**

**Targeted extraction.** Up-reserve only (under-frequency); FCR-down explicitly disregarded
("only a loss of generation is simulated… downward reserve is disregarded"). Generic Continental
FCR + SI + FFR, **not** Nordic FCR-D/FCR-N. No optimization. **No storage, no tank, no compressor,
no endurance constraint, no economics.** Capacity exogenous; FCR noted as currently mandatory and
non-remunerated in IP.

**Novelty impact.** Must cite as the closest prior demonstration that Iberian electrolysers can
deliver frequency reserve as a controllable load. Threatens **neither (b) nor (c)**: it has no
storage/down-reserve (b absent) and no sizing/economics (c absent), and it explicitly names the
economics as future work — which we provide. Recommended framing: *"Ribeiro et al. establish the
dynamic feasibility of Iberian electrolyser frequency reserve but leave the economics and sizing to
future work; we provide exactly that."* There is a companion conference paper (ref [20], 2022 SEST,
FCR-only) to cite alongside.

---

## Paper 2 — Phan et al. 2024 (closest on the endurance idea)

**Advanced frequency control schemes and technical analysis for large-scale PEM and Alkaline
electrolyzer plants in renewable-based power systems.** L. V. Phan, N. P. Nguyen-Dinh, K. M. Nguyen,
T. Nguyen-Duc. *Int. J. Hydrogen Energy* 89 (2024) 1354–1367. DOI 10.1016/j.ijhydene.2024.09.360.
**Type:** Control/dynamic simulation (transfer-function system frequency response + MPC controller).

**Section-by-section.**
- *Intro:* Low-inertia motivation. Reviews techno-economic prior art (see Critical gap below) and
  technical/dynamic prior art. Gap targeted: prior physical models are computation-heavy with many
  parameters; little work on secondary control with advanced controllers. Four contributions:
  universal SFR (U-SFR) model, MPC secondary controller, evaluation on IEEE 39-bus with >50% wind,
  PEM-vs-Alkaline technical analysis.
- *Electrolyzer model:* First-order-with-deadtime power tracking `G(s)=e^{−T_ini·s}·K/(T·s+1)`.
  PEM: T_r=0.02 s, T_s=0.06 s; Alkaline: T_r=1 s, T_s=4 s (PEM ~40× faster). **Hydrogen storage
  sub-model:** production `m_H = η·P/LHV`; tank bound `V_min ≤ V(t) ≤ V_max`;
  `V(t)=V(t0)+∫(m_H − m'_H)dt`. While within bounds the plant freely modulates power; at a bound it
  cannot.
- *U-SFR:* swing equation collapsed to a fitted 2nd-order transfer function; parameters by particle
  swarm; validated vs PSS/E on modified IEEE 39-bus, 50.83% wind (RMSE ~1e-4 Hz).
- *Control scheme:* Primary = droop + virtual inertia (piecewise law, Eq. 10, deadband, ROCOF gain
  RD_ely); both up and down regulation. Secondary = MPC tracking frequency deviation AND RoCoF, with
  hard bound `ΔP_min ≤ ΔP_ely ≤ ΔP_max`.
- *Operating modes:* **Mode 1** normal (full support); **Mode 2** storage-constraint violation —
  when the tank nears a bound, the plant sets production = consumption, freezing tank content and
  **stopping further frequency support**; **Mode 3** internal fault → off.
- *Case studies (IEEE 39-bus):* Case I controllers (base nadir 49.236 Hz/RoCoF 0.958 → MPC 49.932 Hz,
  settling 3–5 s). Case II PEM vs Alkaline (PEM nadir 49.931 @2.14 s vs Alkaline 49.679 @2.62 s).
  Case III pre-contingency power sets available FCR headroom (0.4 GW base → only 0.3 GW FCR). **Case
  IV** downstream storage: initial 15 kg, min 10 kg, consumption 3 kg/s, production 5 kg/s; sustained
  up-regulation drops production below consumption, depletes tank to the floor in ~12 s → Mode 2 stops
  support; naive ramp-to-rated worsens nadir by ~0.52 Hz and overshoots to 51.29 Hz on a fault.
  *Finding: smaller tanks breach constraints more often, degrading frequency-support capability.*

**Targeted extraction.** Modulates consumption both directions (down = increase load). Generic
"frequency support" (primary ≈ FCR/FFR, secondary ≈ aFRR), **not** FCR-D/FCR-N. Control/dynamic, not
MILP (embedded optimization is only PSO fitting + online MPC QP). **No sizing, no economics, no
compressor.** **Storage-headroom endurance: YES qualitatively** — Eqs. (5)–(6) + Case IV — but as a
real-time dynamic **mode switch**, not a reserve-vs-storage **constraint** in a scheduling/sizing
problem, and the tank (15 kg for a 1 GW plant) is an illustrative buffer, not a sized asset.

**Novelty impact.** This is the one paper that physically demonstrates "tank headroom limits
sustained electrolyser reserve." We therefore **cannot claim to be first to observe** the effect, and
must cite Phan 2024 (and Case IV) as the physical precedent for (b). **But our (b) as a tractable
MILP reserve-endurance constraint — a procured FCR-down quantity bounded by node-level tank headroom
over the delivery window, co-optimized with commitment and investment — is not done here.** Framing:
cite Phan for the physical effect, then state prior work captures it only as a dynamic mode switch
whereas we embed it as an optimization constraint. Also useful: Case III (pre-contingency operating
point sets reserve headroom) supports our 2nd-block headroom coupling; PEM-vs-Alkaline response data
supports ramp/reserve-capability parameters. **Phan's intro is also the single best lead to the
techno-economic papers that DO threaten (c)** (Johnsen, Zheng, Matute, Samani — see below).

---

## Paper 3 — Ye et al. 2026 (PEM dynamics + HIL)

**Dynamic modelling of PEM Electrolyzers for power system frequency control with power HIL
validation.** Y. Ye, J. Fang, X. Ai, S. Cui, H. Li, Z. Zhong, K. Hu, X. Yang, J. R. Svensson, J. Wen.
*Applied Energy* 413 (2026) 127504. DOI 10.1016/j.apenergy.2026.127504. **Type:** Multiphysics
dynamic model + droop control + power-hardware-in-the-loop (8-cell, 2.5 kW PEM stack; scaled to 1 MW).

**Section-by-section (condensed).** Builds a bubble-effect-dominated **two-stage** electrochemical
+ bubble-dynamics model explaining the second-scale response (Stage I near-instant power jump, Stage
II settles as bubble coverage rises with time constant T_b; settling T_s ≈ 5·T_b). Validated on a
power-HIL rig: voltage error 0.56%, power error 0.85% (beats RC and thermal models). Droop control
`K_el = ΔP/Δf` with reserve bounded by ramp and operating-point limits. Results: rise time 0.20 s
(vs generator 2.94 s); max ramp 0.644 pu/s (literature ~0.5 pu/s); simplified RC model overestimates
max frequency deviation by 78%. MW-scale simulation: trade-off between response speed (low flow rate,
slow bubble dynamics) and electrolytic efficiency.

**Targeted extraction.** Droop frequency response by consumption modulation; positive droop sign
(high frequency → increase consumption), consistent with FCR-down = increase load. **No** FCR-D/N
naming, **no** optimization, **no** sizing/economics, **no** hydrogen storage or endurance. Generic
single-bus swing-equation system; seconds/sub-second timescale.

**Novelty impact.** None to (b) or (c). Excellent **supporting** citation for physical realism:
ramp rate 0.644 pu/s, rise time 0.20 s, min load 5%, ~10 s settling — justifies treating FCR
provision as effectively instantaneous at UC time resolution; the 78% over-credit of simplified
models motivates an explicit physical bound; the over/under-frequency asymmetry supports separate
up/down (FCR-D vs FCR-N) treatment.

---

## Paper 4 — Elhawash et al. 2025 (PHIL validation, Iberian)

**Frequency support from PEM hydrogen electrolysers using Power-Hardware-in-the-Loop validation.**
A. M. Elhawash, R. E. Araújo, J. A. Peças Lopes. *Int. J. Hydrogen Energy* 175 (2025) 151203.
DOI 10.1016/j.ijhydene.2025.151203 (open access, CC BY-NC). **Type:** PHIL experiment — real 5 kW
PEM stack + custom 3-level interleaved buck converter coupled to a real-time RMS model of the 2040
Iberian / Continental Europe system (same INESC TEC lineage as Ribeiro 2023).

**Section-by-section (condensed).** Two-bus IP+CE swing-equation model; FCR via droop (full at
49.8 Hz), FFR as a step. 2040 IP FCR = 430 MW (Spain 380 + Portugal 50) of a 3 GW area loss; 12 GW HE
assumed in IP. Real converter (3 legs, 120° shift, ripple ÷3, adaptive lead-lag current control,
1 pu/s ramp) on dSPACE at 40 kHz. Results: at 100% FCR the 430 MW maps to ~500 W (26%) on the 5 kW
stack at a 38% operating point; nadir ≈ 49.71 Hz. RoCoF: 0.97 (0% HE) → 0.93 (25%) → 0.81 Hz/s
(100%). With FFR at 25% FCR: 0.93 → 0.65 (4×) → 0.63 Hz/s (10×) — diminishing returns capped by the
1 pu/s ramp. Cross-border import cut ~141 MW (25% case). Experiment captures the double-layer
capacitance effect absent in simulation (minimal effect on nadir/RoCoF).

**Targeted extraction.** FCR (symmetric, both directions shown — over-frequency → increase
consumption) + FFR by load modulation; **no** FCR-D/N naming. PHIL hardware, **no** optimization,
**no** sizing/economics. A hydrogen buffer reservoir is mentioned only qualitatively to justify
ignoring balance-of-plant dynamics over the 30 s window — **no endurance constraint**.

**Novelty impact.** None to (b) or (c). Hardware-validated proof that a real PEM electrolyser
delivers FCR/FFR as a controllable load — strong empirical anchor. Note: the paper's open assumption
that a buffer "assures isolation" over the reserve window is exactly the hand-wave our endurance
constraint (b) replaces with a quantitative bound — a clean way to position (b).

---

## Paper 5 — Ranaboldo et al. 2024 (industrial DR review — context only)

**A comprehensive overview of industrial demand response status in Europe.** M. Ranaboldo et al.
*Renewable and Sustainable Energy Reviews* 203 (2024) 114797. DOI 10.1016/j.rser.2024.114797
(open access; FLEX4FACT project). **Type:** Literature review (184 refs).

**Section-by-section (condensed).** Flexibility gap and demand-side flexibility; industrial DR
taxonomy (implicit price-based vs explicit incentive-based; load shedding vs shifting); potential
(~4–5% of peak load short-term; Söder et al. 4.7–7.1% across seven Northern European countries;
industry = 38% of final energy, >40% of electricity, ~29% CO2); challenges (Table 5). Flexibility
markets: FCR/aFRR/mFRR/RR + EU platforms FCR Cooperation, PICASSO, MARI, TERRE; FCR (EU) full
activation 0.5 min, validity 240 min, min 1 MW; FCR Cooperation requires symmetrical bidding + high
technical requirements, excluding many energy-intensive loads. Energy-aware manufacturing scheduling
(SMSP/PMSP/FSSP/JSSP — dominated by implicit TOU/RTP; explicit DR under-studied). Aggregators as
VPPs. Digitalisation. EU research projects.

**Targeted extraction.** **No hydrogen electrolyser, no power-to-X, no FCR-D/N, no endurance, no
co-sizing.** The only "electrolyser" reference is an **aluminium-smelting electrolysis furnace** used
as a curtailable load / "virtual battery" (TRIMET/Entelios, up to 25% curtailment). The only explicit
FCR-provision example is a battery (Peleman/Next-Kraftwerke). No FCR prices given.

**Novelty impact.** None — pure context. Cite for: industrial-flexibility motivation and the
flexibility gap; the European balancing-market structure and the ~1 MW / symmetrical-bid barriers
that exclude energy-intensive loads; the review's own statement that explicit-DR (ancillary)
scheduling "has received limited attention" — which positions our electrolyser-FCR investment model
as filling that gap.

---

## Paper 6 — Saretta, Raheli & Kazempour 2023 (closest operational prior art)

**Electrolyzer Scheduling for Nordic FCR Services.** M. Saretta, E. Raheli, J. Kazempour (DTU).
2023 IEEE SmartGridComm, pp. 1–6. DOI 10.1109/SmartGridComm57358.2023.10333890; preprint
arXiv:2306.10962 (open). Code: github.com/mrc-srt/electrolyzer_nordic_FCR. **Type:** deterministic
MILP operational scheduling/bidding (price-taker, hourly, full-year 2022 perfect-foresight case).

**Section-by-section (condensed).**
- *Nordic FCR markets:* three products — FCR-N (symmetric, ±49.9–50.1 Hz droop), FCR-D Up, FCR-D
  Down; pay-as-bid D-2 (~80%) and D-1 (~20%) auctions; piecewise activation functions; alkaline
  ramp ~20%/s eligible for all three.
- *Model:* a 10 MW alkaline electrolyzer in DK2 buys grid power, makes/compresses/stores hydrogen,
  serves a weekly demand at a fixed €/kg, and bids FCR. **Objective** = hydrogen sales + the three
  FCR **capacity** payments − power (spot+TSO+DSO) − start-up. **Activation payment deliberately
  excluded** (FCR-N ~symmetric over a year; FCR-D activated <1% of hours in DK2).
- *Constraints:* power split electrolyzer/compressor; three-state on/standby/off; start-up
  detection; **5-segment piecewise-linear part-load efficiency**; compressor power `p^c = K^c·h^p`;
  **hydrogen storage SOC** `h^s_t = h^p_t − d_t + h^s_{t-1}`, bounded `h^s_t ≤ H^max`; weekly
  minimum-delivery (HPA) constraint. **Reserve-allocation (the headroom logic):**
  `p^e − r^{FCR-N} − r^{FCR-D↑} ≥ P^min` (room to reduce load) and
  `p^e + r^{FCR-N} + r^{FCR-D↓} ≤ P^max` (room to increase load); FCR-N bounded by (P^max−P^min)/2.
- *Results:* annual profit **0.73 M€**, revenue 3.43 M€ split hydrogen 28% / FCR-N 2% / FCR-D Down
  30% / FCR-D Up 40% → **72% of revenue from FCR**. Conclusion explicitly: this profit is *"still
  insufficient to recover the investment cost… an in-depth analysis is left for future work"*
  (alkaline capex ~1 M€/MW).

**Targeted extraction.** FCR-D Up/Down and FCR-N by consumption modulation, up = reduce / down =
increase, **three separate bids, FCR-N symmetric** — a precise match to our operational framing.
Deterministic MILP, price-taker, hourly. **Crucially: it HAS a hydrogen tank, a compressor, part-load
PWL efficiency, three-state commitment, and an HPA constraint — the same operational skeleton as
el1xr.** But: **(b)** reserves are bounded **only by the electrical range [P^min, P^max]**; the
storage SOC is driven solely by *baseline* production/demand and is **never coupled to the reserve
bid** — there is no "FCR-down must fit in tank headroom" constraint (they justify this by negligible
activation). **(c)** all capacities (10 MW, 60,500 kg tank, compressor) are **fixed parameters** — no
sizing; investment recovery is **named as future work**.

**Novelty impact.** This is the **single closest prior art** for the operational FCR-D/N electrolyzer
model and must be cited as the baseline (including its electrical-headroom reserve constraints, which
mirror ours). It does **not** do (b) — its reserve is power-bounded, not tank-headroom-bounded — and
it does **not** do (c) — fixed assets, investment explicitly deferred. So Saretta *clears* both our
contributions and even hands us (c) as its stated future work. One caveat it exposes: our
tank-headroom FCR-down endurance constraint only **binds** when the tank is scarce and/or activation
is non-negligible — state that assumption explicitly so a referee sees why our constraint is needed
where Saretta's is not.

## Paper 7 — Dadkhah et al. 2022 (the (c) pre-emption)

**Techno-Economic Analysis and Optimal Operation of a Hydrogen Refueling Station Providing Frequency
Ancillary Services.** A. Dadkhah, D. Bozalakov, J. De Kooning, L. Vandevelde. *IEEE Trans. Industry
Applications* 58(4):5171–5183, 2022. DOI 10.1109/TIA.2022.3167377 (green OA, UGent). **Type:**
probabilistic (scenario) MILP for **joint sizing + operation** of a hydrogen refuelling station (HRS).

**What it does.** Maximizes annual profit = hydrogen sales (mobility + industry + gas grid) + FAS
capacity + activation revenue − electricity − **annualized CAPEX of every subcomponent**. Decision
variables include the **sizes** of the electrolyser `C^E`, each compressor `C_c`, and each storage
tank `C_t` (Eq. 1 CAPEX term `Σ_u 1.1·C^u·(IC+RC)+C^u·OC`). Products: **continental symmetric FCR +
aFRR-up/down + mFRR-up** (NOT Nordic FCR-D/N). Single HRS at Zeebrugge, hourly, 8784 h, 100 scenarios,
price-taker. **No unit commitment** (no on/off binary, min-up/down, or start-up — the 5–100% FCR
baseline keeps it always on). Results: electrolyser sized 4.5→6.5 MW to host FCR/aFRR-down; profit
uplift FCR +5%, aFRR-down +18%, **aFRR-up +58%**, mFRR-up +27%.

**Decisive extraction.** **(c): YES — it jointly sizes electrolyser + compressor + tank with
ancillary revenue in the capex objective.** Quote (contribution 3): *"The economic feasibility of the
investment… is further improved via optimal sizing of subcomponents acknowledging the effect of
providing various grid services on the system rating."* **This pre-empts the GENERAL (c) claim.**
**(b): NO.** The down-reserve bid `R_s` is bounded **only by electrical power** (Eq. 2a:
`0.05·C^E + R_s ≤ P^0 ≤ C^E − R_s`). Storage appears as an SOC balance (Eqs. 11–12) + an upper cap
`S ≤ C_St` (Eq. 16) + a demand-based **minimum floor** (Eq. 17, `max_h H^demand ≤ S` — a *lower*
bound for supply security, the opposite direction). **No headroom bound ties the down-reserve bid to
remaining empty tank volume.** (b) survives.

**Novelty impact.** Cite as the paper that already co-sizes electrolyser + compressor + tank with
frequency-reserve revenue — **do not claim that combination as new.** Differentiators: Nordic FCR-D/N
(vs continental FCR + aFRR/mFRR), genuine unit-commitment (they have none), transmission-node/network
(they are a single station), and the tank-headroom FCR-down endurance constraint (b). Companion paper
worth pulling to fully secure the boundary: Dadkhah et al. 2021, IJHE 46(2):1488–1500
(DOI 10.1016/j.ijhydene.2020.10.130).

## Paper 8 — Johnsen et al. 2026 (the (b) near-miss — cite and differentiate carefully)

**The value of ancillary services for electrolyzers.** A. G. Johnsen, L. Mitridati, D. Zarrilli,
J. Kazempour. *Computers & Chemical Engineering* 204:109360 (2026); preprint arXiv:2310.04321 (open).
**Type:** deterministic MILP day-ahead self-scheduling + reserve bidding of a **single fixed-capacity**
electrolyzer + analytical reserve bid-curve (opportunity-cost) derivation. DK1 data 2021–2023,
price-taker.

**What it does.** Objective = hydrogen + mFRR-up/down capacity + FCR (4-h block) capacity − day-ahead
energy; **no capex, no sizing variable** (capacity fixed 10 MW; compressor folded into the production
curve). Products: **continental symmetric FCR + mFRR-up** (NOT Nordic FCR-D/N). PWL efficiency,
three-state on/standby/off. Headline: reserve participation lifts profit **~27% (2021) … ~47%
(2023)**; FCR's 4-h block disadvantages it vs mFRR; tube-trailer storage; unserved-H2 analysis.

**Decisive extraction.** **(c): NO — nothing is sized** (fixed 10 MW, no capex term, compressor not
modelled). Does NOT pre-empt (c). **(b): the closest existing construct — must cite and differentiate
precisely.** Two places: (i) the reserve-**capacity** bid bound (Eq. 3b
`r^F + r^{m↓} ≤ C^e(1−z^off) − p^tot`) is **purely electrical, no tank term**; (ii) at the
**activation-feasibility** stage (Eqs. 4j–4n), the extra hydrogen from *activated* down-reserve must
fit tube-trailer storage via an SOC accumulation `s^d_t = s^d_{t−1} + h^d_t`, `s^d_t ≤ S^d`. So they
**do couple down-activation to storage SOC** — but as an *activated-mass feasibility check*, not a
**headroom bound on the reserve capacity bid**, and not for Nordic products.

**Novelty impact — IMPORTANT framing caveat.** The claim *"no prior work links down-reserve to
hydrogen storage"* is **too strong and would be challenged** — Johnsen couples down-activation to a
storage SOC balance. The defensible claim is sharper: *Johnsen et al. couple down-reserve **activation
feasibility** to a storage SOC balance at the bidding stage; we instead bound the down-reserve
**capacity** directly by node-level tank headroom as an endurance constraint, inside an investment
model that co-sizes the tank.* Cite Johnsen as the strongest operational prior art; their public code
(github.com/andreagloppen/Value_of_AS_ELY) can confirm Eq. 3b has no storage term before finalizing
the wording.

## Final novelty verdict (after all 8 papers)

**(c) "co-size electrolyser + tank + compressor with ancillary-service revenue" — NOT novel in
general.** Dadkhah 2022 does exactly this (and Scolaro & Kittner sizes the electrolyser). Do not claim
it as new.

**(b) "tank-headroom-bounded FCR-down endurance" — survives, but frame precisely.** No reviewed paper
puts a tank-headroom term in the reserve **capacity** constraint. The nearest is Johnsen's
SOC-coupled *activation*-feasibility check — cite and distinguish (capacity-headroom/endurance vs
activated-mass SOC). Dadkhah/Saretta bound reserve only electrically.

**The defensible contribution is the COMBINATION, stated honestly:** each ingredient has a precedent
— Saretta (Nordic FCR-D/N **operation**), Dadkhah (co-sizing with **continental** AS revenue), Johnsen
(down-reserve↔storage coupling) — but no prior work brings them together. Specifically novel:
1. **Nordic FCR-D + FCR-N co-sizing** — no one sizes assets for the Nordic asymmetric-D/symmetric-N
   products (Saretta does D/N but fixed assets; Dadkhah/Johnsen size/operate but continental FCR).
2. **Tank-headroom FCR-down endurance in the reserve-capacity bound** — distinct from Johnsen's
   activation-feasibility SOC check.
3. **Genuine unit-commitment + investment at a transmission node / network** — Dadkhah (no UC, single
   station), Johnsen (no sizing, single asset), Saretta (no sizing, single asset) each lack at least
   one of {UC, investment, network}.

Recommended one-line positioning: *"Prior work either schedules an electrolyser for Nordic FCR-D/N
with fixed assets (Saretta 2023), or co-sizes an electrolyser-storage-compressor system for
continental FCR/aFRR/mFRR revenue (Dadkhah 2022; Johnsen 2026) — but none co-sizes for the Nordic
FCR-D/N products, embeds a hydrogen-tank-headroom FCR-down endurance constraint in the reserve
capacity, or does so within a network unit-commitment-and-investment model. We close that gap."*

## Cross-cutting novelty assessment

1. **Layer split.** All four technical papers operate at the **dynamics/control/hardware layer**
   (sub-30-second frequency response, RoCoF, nadir). Our work is at the **operations + investment
   layer** (UC + sizing economics). They answer "can the electrolyser physically deliver the reserve
   fast enough?" — we answer "how much to build and is the FCR revenue worth the capex?" These are
   complementary; cite them to establish physical feasibility, then state the economic/sizing question
   is open.

2. **(b) tank-headroom FCR-down endurance.** Physically precedented by **Phan 2024** (Case IV /
   Mode 2: tank limit stops sustained support) — cite it. Not precedented as an **MILP reserve-
   endurance constraint** anywhere in this set. Likely novel as a formulation; claim it carefully
   ("we encode, as a tractable UC+investment constraint, the storage-headroom limit that prior work
   captures only as a dynamic mode switch").

3. **(c) joint co-sizing with FCR revenue.** Untouched by all six reviewed papers (the five dynamics
   papers + Saretta all use fixed capacities). **But NOT cleared, and now at real risk:** the DOI
   round found that **Dadkhah 2022** sizes electrolyser + compressor + storage tanks with capex AND is
   storage-aware for reserve, and **Johnsen** (CCE 2026 / arXiv:2310.04321) does operation + sizing
   with storage-limited reserve and FCR-D/N. So "co-size an electrolyser + tank + compressor while
   earning ancillary-service revenue" is, in general, **already done** (Dadkhah; also Scolaro sizes
   the electrolyser). The defensible novelty must therefore be **narrowed** to the specific
   combination not yet shown: **(i) FCR-D + FCR-N (Nordic primary reserve) specifically**, with
   **(ii) the tank-headroom-bounded FCR-DOWN endurance constraint (b)**, inside **(iii) a
   transmission-node UC+investment model** — Dadkhah uses aFRR/mFRR (not FCR-D/N) for a single
   refuelling station, and on abstract evidence none couple FCR-down to tank headroom. Confirm by
   reading Dadkhah and Johnsen in full before claiming any "first".

4. **FCR-D / FCR-N (Nordic split).** None of the five use it; they use generic Continental FCR (+ SI
   + FFR) or generic FCR. Our explicit FCR-D + FCR-N treatment with separate up/down and symmetric N
   is a distinguishing detail (shared with the open-access Saretta 2023 Nordic scheduling paper).

## Techno-economic MILP papers — resolved fetch list + threat assessment

DOIs resolved 2026-06-14. These are the real novelty risks for **(c)** (and possibly **(b)**),
because several actually SIZE the assets — unlike the five dynamics papers and Saretta. Abstract-level
flags below; the two HIGH open-access ones must be read in full before any "first co-sizing" claim.

| # | Paper | DOI / id | Open? | Sizes assets? | Storage-aware reserve? | Reserve product | Priority |
|---|---|---|---|---|---|---|---|
| 1 | **Johnsen et al.** "The value of ancillary services for electrolyzers" | 10.1016/j.compchemeng.2025.109360; preprint **arXiv:2310.04321** | preprint YES | **Yes (operation + sizing)** | **Yes (storage-limited reserve)** | FCR-D/FCR-N + mFRR (DK1) | **HIGH** |
| 2 | Zheng et al. "P2H providing frequency regulation reserves, Denmark" | 10.1016/j.ijhydene.2023.03.253 | YES (DTU Orbit) | unclear | unclear | FCR + aFRR | MED |
| 3 | Matute et al. "Multi-MW electrolyser grid services, Spain (FCEV)" | 10.1016/j.ijhydene.2019.05.092 | No (paywalled) | feasibility across sizes | not flagged | secondary freq. control | MED-HIGH |
| 4 | Samani et al. "25 MW electrolyser primary reserve, Belgium" | 10.1049/iet-rpg.2020.0453 (IET) | YES (OA) | No (fixed 25 MW, set-point) | not flagged | FCR (100 mHz symmetric) | MED |
| 5 | Scolaro & Kittner "Hybrid offshore wind H2, Germany" | 10.1016/j.ijhydene.2021.12.062 | No (paywalled) | **Yes (sizes electrolyzer)** | not flagged | German control reserve (generic) | **HIGH** |
| 6 | **Dadkhah et al.** "Probabilistic MILP, HRS providing frequency ancillary services" | 10.1109/TIA.2022.3167377 | YES (green, UGent) | **Yes (electrolyser + compressor + tanks, with capex)** | **Yes (storage-aware reserve)** | aFRR-Up/Down + mFRR-Up (not FCR-D/N) | **HIGH** |
| 7 | Saretta et al. (reviewed above) | 10.1109/SmartGridComm57358.2023.10333890; arXiv:2306.10962 | YES | No | No | FCR-D + FCR-N | done |

**This sharpens the novelty picture — see the verdict below.** Identity corrections vs the original
leads: Scolaro is *Michele* (not Manuel), IJHE not Energy Policy; Matute is **2019** not 2021–23;
Samani (not Amani) is IET RPG; Saretta is IEEE SmartGridComm 2023; Johnsen's "57%" figure is from an
unpublished 2022 DTU thesis, citable version is CCE 2026 / arXiv:2310.04321 (refined to "up to 47%").

**Paywalled DOIs to fetch with RISE credentials → `temp/papers_H2`:** #3
`10.1016/j.ijhydene.2019.05.092` (Matute) and #5 `10.1016/j.ijhydene.2021.12.062` (Scolaro &
Kittner). Everything else (Johnsen preprint, Zheng, Samani, Dadkhah, Saretta) is open access.

**Immediate next reads (open access, no credentials):** #1 Johnsen (arXiv:2310.04321) and #6 Dadkhah
(IEEE TIA 2022) — the only two flagged as doing BOTH sizing AND storage-aware reserve. They are the
decisive tests of (b) and (c).

## Consolidated BibTeX

```bibtex
@article{Ribeiro2023HydrogenElectrolysersFrequencyAS,
  author  = {Ribeiro, Fernando J. and Pe{\c{c}}as Lopes, Jo{\~a}o A. and Fernandes, Francisco S. and Soares, Filipe J. and Madureira, Andr{\'e} G.},
  title   = {The role of hydrogen electrolysers in frequency related ancillary services: A case study in the Iberian Peninsula up to 2040},
  journal = {Sustainable Energy, Grids and Networks},
  volume  = {35}, pages = {101084}, year = {2023},
  issn = {2352-4677}, doi = {10.1016/j.segan.2023.101084}, publisher = {Elsevier}
}
@article{Phan2024ElectrolyzerFrequencyControl,
  author  = {Phan, Long Van and Nguyen-Dinh, Nghia Phu and Nguyen, Khai Manh and Nguyen-Duc, Tuyen},
  title   = {Advanced frequency control schemes and technical analysis for large-scale {PEM} and {Alkaline} electrolyzer plants in renewable-based power systems},
  journal = {International Journal of Hydrogen Energy},
  volume  = {89}, pages = {1354--1367}, year = {2024},
  issn = {0360-3199}, doi = {10.1016/j.ijhydene.2024.09.360}, publisher = {Elsevier}
}
@article{Ye2026PEMElectrolyzerFrequencyHIL,
  author  = {Ye, Yurun and Fang, Jiakun and Ai, Xiaomeng and Cui, Shichang and Li, Hao and Zhong, Zhiyao and Hu, Kewei and Yang, Xiaobo and Svensson, Jan R. and Wen, Jinyu},
  title   = {Dynamic modelling of {PEM} Electrolyzers for power system frequency control with power {HIL} validation},
  journal = {Applied Energy},
  volume  = {413}, pages = {127504}, year = {2026},
  issn = {0306-2619}, doi = {10.1016/j.apenergy.2026.127504}, publisher = {Elsevier}
}
@article{Elhawash2025FrequencySupportPEM,
  author  = {Elhawash, Abdelrahman M. and Ara{\'u}jo, Rui Esteves and Pe{\c{c}}as Lopes, Jo{\~a}o A.},
  title   = {Frequency support from {PEM} hydrogen electrolysers using Power-Hardware-in-the-Loop validation},
  journal = {International Journal of Hydrogen Energy},
  volume  = {175}, pages = {151203}, year = {2025},
  issn = {0360-3199}, doi = {10.1016/j.ijhydene.2025.151203}, note = {Open access, CC BY-NC 4.0}
}
@article{Ranaboldo2024IDR,
  author  = {Ranaboldo, M. and Arag\"{u}\'{e}s-Pe\~{n}alba, M. and Arica, E. and others},
  title   = {A comprehensive overview of industrial demand response status in Europe},
  journal = {Renewable and Sustainable Energy Reviews},
  volume  = {203}, pages = {114797}, year = {2024},
  issn = {1364-0321}, doi = {10.1016/j.rser.2024.114797}, note = {Open access (CC BY-NC)}
}
@article{Saretta2023ElectrolyzerNordicFCR,
  author  = {Saretta, Marco and Raheli, Enrica and Kazempour, Jalal},
  title   = {Electrolyzer Scheduling for {Nordic} {FCR} Services},
  journal = {arXiv preprint arXiv:2306.10962}, year = {2023}, eprint = {2306.10962}
}
```

## Recommended citation map per claim

- "Electrolysers can physically deliver fast FCR/FFR as a controllable load" → Ye 2026, Elhawash 2025
  (hardware), Phan 2024, Ribeiro 2023.
- "Iberian electrolyser frequency reserve, feasibility shown, economics left open" → Ribeiro 2023
  (+ companion conf. [20]).
- "Hydrogen-storage headroom physically limits sustained electrolyser reserve" → Phan 2024 (Case IV).
- "Industrial-flexibility / DR market context and barriers" → Ranaboldo 2024.
- "Operational FCR-D/FCR-N electrolyzer scheduling (Nordic)" → Saretta 2023.
- Our distinct contributions: (b) storage-headroom-bounded FCR-down endurance as an MILP constraint;
  (c) joint co-sizing of electrolyser + tank + compressor with FCR revenue — pending the
  techno-economic review round above.
