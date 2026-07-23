@echo off
REM ============================================================================
REM NATIVE-EUR full-year LP campaign. Same variant matrix as
REM comillas_combined_campaign.cmd, but the model runs in native EUR
REM (H2VPP_CURRENCY=EUR) instead of SEK.
REM
REM Differences from the SEK campaign (all three validated by the A3 gate,
REM 2026-07-07, and the year A3 re-check):
REM   set H2VPP_CURRENCY=EUR   build_case emits the case in EUR (uniform /EUR_SEK)
REM   set MONEY_BASE=100       EUR conditioning matches the proven SEK@1000 basis
REM                            (probe 2026-07-07; year capex coef ~2.7e4, under the guard)
REM   set RUN_TAG=eur          results go to work_year_<VARIANT>_eur, so the validated
REM                            SEK results in work_year_<VARIANT> are NOT clobbered
REM
REM Each writes results/h2vpp_fcr/work_year_<VARIANT>_eur/summary_H2VPPFCR.json
REM (the summary carries "currency": "EUR", so the display layer must NOT convert again).
REM
REM PREREQUISITE: ship the updated model\src + experiments\h2vpp_fcr to
REM C:\Users\ealvarezq\h2vpp_run first (build_case.py must carry the H2VPP_CURRENCY refactor).
REM ============================================================================
cd /d C:\Users\ealvarezq\h2vpp_run
set PYTHONPATH=model\src
set H2VPP_HORIZON=year
set H2VPP_CURRENCY=EUR
set MONEY_BASE=100
set RUN_TAG=eur
set LP=1
set METHOD=2
set CROSSOVER=0
set BARHOMOGENEOUS=1
set NUMERICFOCUS=3
set THREADS=8
set TIMELIMIT=5400
REM A4/A5 dropped 2026-07-08 (fuel cell is a baseline candidate everywhere; old A4=A3, A5=A2).
for %%V in (A3 A1 A2 B0 B1 B2 D1 D2 S1 S2 S3 C2) do (
  set VARIANT=%%V
  echo ============================================================
  echo === VARIANT %%V  ^(year LP, native EUR^)
  echo ============================================================
  "C:\Miniforge3\envs\power\python.exe" experiments\h2vpp_fcr\run_year.py
)
echo === EUR CAMPAIGN DONE ===
