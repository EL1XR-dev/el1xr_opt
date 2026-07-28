"""Run the four figure-data campaigns under the p4 pressure-resolved config PLUS the
response-speed reserve realism (ELE_FCR_RESPONSE=1), matching the resp campaign.

The paper's figure scripts need full-output/sweep data that the 14-case p4 summary campaign did not
write. This runner reproduces that data with the SAME env as the p4 campaign (jobs/done/p4_A3.cmd)
so the figures match Table 2, and runs the 35 cells over a worker pool instead of four serial loops.

Mirrors the run_variants_parallel.py / run_heatmap_parallel.py pattern (ThreadPoolExecutor of
run_year.py subprocesses, each in its own work dir so they do not race). Tune PWORKERS x PTHREADS.

    set PYTHONPATH=model\\src & python experiments\\h2vpp_fcr\\run_p4_figs_parallel.py

Outputs (under OUT_BASE=D:\\h2vpp_work\\results\\h2vpp_fcr):
  fig_econ    -> work_year_{A1,A2,A3,C2}_econ / results.duckdb   (FULL_OUTPUT year)
  fig_cycling -> work_month_A3_monthfull      / results.duckdb   (FULL_OUTPUT month)
  fig_heatmap -> work_month_A3_hm_d<D>p<a>    / summary          (25-cell deg x H2-price)
  fig_fcr     -> work_year_A3_fcr<tag>        / summary          (5-cell FCR-price scan)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
RUN_YEAR = HERE / "run_year.py"
LOGDIR = REPO / "results" / "p4_figs"
LOGDIR.mkdir(parents=True, exist_ok=True)

WORKERS = int(os.environ.get("PWORKERS", "3"))
THREADS = int(os.environ.get("PTHREADS", "4"))

# The exact p4 campaign env (jobs/done/p4_A3.cmd), minus the per-cell knobs and THREADS. Solver
# config is left at run_year.py defaults, as in the p4 campaign, so the LP vertex (and the FCR
# split) matches the headline table rather than a differently-conditioned barrier.
COMMON = {
    "PYTHONPATH": "model\\src",
    "OUT_BASE": "D:\\h2vpp_work",
    "PRESSURE_NODES": "1", "ENHANCED_PROFILES": "1", "MONEY_BASE": "1000",
    "PEAK_THRESHOLD_LP": "1", "LP": "1", "AEL_N": "6", "PEM_N": "6",
    "COMPRESSOR_NAMEPLATE_KG": "1000", "WIND_MAX_POWER_KW": "60000",
    "LINE_TTC_KW": "60000", "ELE_BUY_CAP_KW": "60000",
    "ELE_FCRD_RAMPGATE": "1", "AEL_FCRD_RAMP_PER_S": "0.02", "PEM_FCRD_RAMP_PER_S": "0.10",
    "TIMELIMIT": "7200", "THREADS": str(THREADS),
}


def _jobs() -> list[tuple[str, dict]]:
    jobs: list[tuple[str, dict]] = []
    # fig_econ: 4 cases, year, full duckdb -> work_year_<V>_econ
    for v in ("A1", "A2", "A3", "C2"):
        jobs.append((f"econ_{v}", {"VARIANT": v, "H2VPP_HORIZON": "year",
                                   "FULL_OUTPUT": "1", "RUN_TAG": "econ"}))
    # fig_cycling: A3 month full duckdb -> work_month_A3_monthfull
    jobs.append(("cycling_A3", {"VARIANT": "A3", "H2VPP_HORIZON": "month",
                                "FULL_OUTPUT": "1", "RUN_TAG": "monthfull"}))
    # fig_heatmap: 25-cell DEG x H2-price, A3 month -> work_month_A3_hm_d<D>p<a>
    for d in ("0", "2", "5", "8", "12"):
        for ptag, pval in (("06", "0.6"), ("08", "0.8"), ("10", "1.0"), ("12", "1.2"), ("14", "1.4")):
            jobs.append((f"hm_d{d}p{ptag}", {"VARIANT": "A3", "H2VPP_HORIZON": "month",
                                             "DEG_SCALE": d, "H2_PRICE_SCALE": pval,
                                             "RUN_TAG": f"hm_d{d}p{ptag}"}))
    # fig_fcr: 5-cell FCR-price scan, A3 year -> work_year_A3_fcr<tag>
    for tag, pval in (("10", "1.0"), ("075", "0.75"), ("05", "0.5"), ("025", "0.25"), ("00", "0.0")):
        jobs.append((f"fcr{tag}", {"VARIANT": "A3", "H2VPP_HORIZON": "year",
                                   "FCR_PRICE_SCALE": pval, "RUN_TAG": f"fcr{tag}"}))
    return jobs


def run_job(label: str, overrides: dict) -> tuple[str, int, float]:
    env = os.environ.copy()
    env.update(COMMON)
    env.update(overrides)
    t0 = time.time()
    with open(LOGDIR / f"{label}.log", "w") as f:
        rc = subprocess.run([PY, str(RUN_YEAR)], env=env, cwd=str(REPO),
                            stdout=f, stderr=subprocess.STDOUT).returncode
    return label, rc, time.time() - t0


def main() -> int:
    jobs = _jobs()
    # Heaviest first (year jobs) so the long poles start early and month cells backfill the pool.
    jobs.sort(key=lambda j: 0 if j[1].get("H2VPP_HORIZON") == "year" else 1)
    print(f"p4 figs: {len(jobs)} jobs over {WORKERS} workers x {THREADS} threads", flush=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_job, lbl, ov) for lbl, ov in jobs]
        for fut in as_completed(futs):
            label, rc, dt = fut.result()
            status = "ok" if rc == 0 else f"FAIL rc={rc}"
            failures += rc != 0
            print(f"  [{status}] {label}  ({dt/60:.1f} min)", flush=True)
    print(f"=== P4 FIGS DONE: {len(jobs)-failures}/{len(jobs)} ok, {failures} failed ===", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
