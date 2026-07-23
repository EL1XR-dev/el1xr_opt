@echo off
REM ### NATIVE-EUR variant (auto-derived from comillas_fcr_erosion.cmd): H2VPP_CURRENCY=EUR,
REM ### MONEY_BASE=100, every RUN_TAG suffixed _eur so EUR results do not clobber SEK.
REM ### FIX_INVEST (if any) points at the EUR year-A3 optimum. Ship build_case.py with the
REM ### H2VPP_CURRENCY refactor first. Validated by the A3 gate + year A3 re-check (2026-07).
REM ============================================================================
REM FCR price-erosion sensitivity (A3, year LP) on Gurobi -- authoritative numbers.
REM
REM Scales every FCR capacity price (all products, all hours) by FCR_PRICE_SCALE to
REM emulate reserve prices eroding as a fleet of such plants enters the market. Tests
REM how far the battery's reserve-driven build and the plant's profit survive.
REM   scale 1.0 = 2025 SE3 prices (reference); 0.0 = reserve pays nothing.
REM
REM This is the Gurobi version of the local HiGHS month-LP preview; we run the full
REM YEAR LP here so the sensitivity matches the headline solve and the rest of the paper.
REM
REM Settings = the same well-conditioned matrix that won the barrier campaign, with
REM crossover ON for a clean vertex (as in the D1/S1/C2 re-run):
REM   MONEY_BASE=1000, SCALEFLAG=2, NUMERICFOCUS=3, BARHOMOGENEOUS=1
REM   METHOD=2 (barrier) then automatic crossover; CONCURRENT_FALLBACK=1 as a safety net.
REM
REM RUN_TAG=fcr<tag> -> outputs in results\h2vpp_fcr\work_year_A3_fcr<tag>\, e.g.
REM   fcr10 fcr075 fcr05 fcr025 fcr00. Pull each summary_H2VPPFCR.json back to the Mac as
REM   results/h2vpp_fcr/sweep_fcr/sum_s<tag>.json, then re-run analysis/figs_casestudy.py.
REM
REM PREREQUISITE: model\src + experiments\h2vpp_fcr on the box must include the
REM FCR_PRICE_SCALE knob (build_case.py) shipped 2026-06-26. Re-ship experiments\ first.
REM ============================================================================
cd /d C:\Users\ealvarezq\h2vpp_run
set PYTHONPATH=model\src
set VARIANT=A3
set H2VPP_HORIZON=year
set H2VPP_CURRENCY=EUR
set LP=1
set ELE_3STATE_TIGHT=1
set PEAK_THRESHOLD_LP=1
set ELE_OPER_SYMBREAK=1
set RESERVE_DELIVERY=1
set ELE_RAMP_CAP=1
set METHOD=2
set CROSSOVER=-1
set MONEY_BASE=100
set SCALEFLAG=2
set NUMERICFOCUS=3
set BARHOMOGENEOUS=1
set CONCURRENT_FALLBACK=1
set THREADS=12
set TIMELIMIT=7200
for %%P in ("10 1.0" "075 0.75" "05 0.5" "025 0.25" "00 0.0") do (
  for /f "tokens=1,2" %%a in (%%P) do (
    set RUN_TAG=fcr%%a_eur
    set FCR_PRICE_SCALE=%%b
    echo ============================================================
    echo === A3 year LP  FCR_PRICE_SCALE=%%b  ^(tag fcr%%a^)
    echo ============================================================
    "C:\Miniforge3\envs\power\python.exe" experiments\h2vpp_fcr\run_year.py
  )
)
echo === FCR EROSION SWEEP DONE ===
