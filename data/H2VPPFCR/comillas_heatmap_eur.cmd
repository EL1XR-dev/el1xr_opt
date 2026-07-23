@echo off
REM ### NATIVE-EUR variant (auto-derived from comillas_heatmap.cmd): H2VPP_CURRENCY=EUR,
REM ### MONEY_BASE=100, every RUN_TAG suffixed _eur so EUR results do not clobber SEK.
REM ### FIX_INVEST (if any) points at the EUR year-A3 optimum. Ship build_case.py with the
REM ### H2VPP_CURRENCY refactor first. Validated by the A3 gate + year A3 re-check (2026-07).
REM ============================================================================
REM Degradation x H2-price heatmap sweep (fig_heatmap), consistent with the corrected-tariff
REM + 3-state-facet campaign. 25 cells: DEG_SCALE in {0,2,5,8,12} x H2_PRICE_SCALE in
REM {0.6,0.8,1.0,1.2,1.4}, A3 month LP. RUN_TAG=hm_d<D>p<a> -> work_month_A3_hm_d<D>p<a>.
REM Robust barrier config + ELE_3STATE_TIGHT=1 (matches the campaign). Crossover off, as in
REM the original heatmap sweep, so the FCR split matches the campaign relaxation.
REM Pull each work_month_A3_hm_d<D>p<a>\summary_H2VPPFCR.json -> sweep_hm\sum_d<D>p<a>.json.
REM ============================================================================
cd /d C:\Users\ealvarezq\h2vpp_run
set PYTHONPATH=model\src
set VARIANT=A3
set H2VPP_HORIZON=month
set H2VPP_CURRENCY=EUR
set LP=1
set ELE_3STATE_TIGHT=1
set PEAK_THRESHOLD_LP=1
set ELE_OPER_SYMBREAK=1
set RESERVE_DELIVERY=1
set ELE_RAMP_CAP=1
set METHOD=2
set CROSSOVER=0
set PRESOLVE=2
set NUMERICFOCUS=3
set BARHOMOGENEOUS=1
set SCALEFLAG=2
set MONEY_BASE=100
set CONCURRENT_FALLBACK=1
set THREADS=12
set TIMELIMIT=7200
set FULL_OUTPUT=
for %%D in (0 2 5 8 12) do (
  for %%P in ("06 0.6" "08 0.8" "10 1.0" "12 1.2" "14 1.4") do (
    for /f "tokens=1,2" %%a in (%%P) do (
      set DEG_SCALE=%%D
      set H2_PRICE_SCALE=%%b
      set RUN_TAG=hm_d%%Dp%%a_eur
      echo === A3 month LP  DEG=%%D  PRICE=%%b  ^(hm_d%%Dp%%a^) ===
      "C:\Miniforge3\envs\power\python.exe" experiments\h2vpp_fcr\run_year.py
    )
  )
)
echo === HEATMAP SWEEP DONE ===
