"""Re-run the four business-case robustness spokes (S6-S9) under the p4 pressure-resolved config.

The spokes were originally solved with the old flat-topology campaign, so their summaries do not
match the p4 headline table (Table 2). This re-runs each as A3 with ONE knob changed, under the SAME
env as the p4 campaign (jobs/done/p4_A3.cmd), so the numbers slot straight into Supplementary Table S6.

    set PYTHONPATH=model\\src & python experiments\\h2vpp_fcr\\run_p4_spokes_parallel.py

Outputs (under OUT_BASE=D:\\h2vpp_work\\results\\h2vpp_fcr):
  work_year_A3_S6_cycoff    CYCLING_SCALE=0      cycling-wear surcharge off (steady-state kept)
  work_year_A3_S7_bpoff     BYPRODUCT_SCALE=0    oxygen/heat byproduct credit off
  work_year_A3_S8_windppa   WIND_MODE=ppa        wind contracted off-site (not owned/sized)
  work_year_A3_S9_connfree  CONNECTION_SCALE=0   grid-connection capital cost socialised
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
LOGDIR = REPO / "results" / "p4_spokes"
LOGDIR.mkdir(parents=True, exist_ok=True)

WORKERS = int(os.environ.get("PWORKERS", "4"))
THREADS = int(os.environ.get("PTHREADS", "3"))

# The exact p4 campaign env (jobs/done/p4_A3.cmd), minus the per-cell knobs and THREADS.
COMMON = {
    "PYTHONPATH": "model\\src",
    "OUT_BASE": "D:\\h2vpp_work",
    "PRESSURE_NODES": "1", "ENHANCED_PROFILES": "1", "MONEY_BASE": "1000",
    "PEAK_THRESHOLD_LP": "1", "LP": "1", "AEL_N": "6", "PEM_N": "6",
    "COMPRESSOR_NAMEPLATE_KG": "1000", "WIND_MAX_POWER_KW": "60000",
    "LINE_TTC_KW": "60000", "ELE_BUY_CAP_KW": "60000",
    "TIMELIMIT": "7200", "THREADS": str(THREADS),
    "VARIANT": "A3", "H2VPP_HORIZON": "year",
}

SPOKES = [
    ("S6_cycoff", {"CYCLING_SCALE": "0"}),
    ("S7_bpoff", {"BYPRODUCT_SCALE": "0"}),
    ("S8_windppa", {"WIND_MODE": "ppa"}),
    ("S9_connfree", {"CONNECTION_SCALE": "0"}),
]


def run_job(tag: str, overrides: dict) -> tuple[str, int, float]:
    env = os.environ.copy()
    env.update(COMMON)
    env["RUN_TAG"] = tag
    env.update(overrides)
    t0 = time.time()
    with open(LOGDIR / f"{tag}.log", "w") as f:
        rc = subprocess.run([PY, str(RUN_YEAR)], env=env, cwd=str(REPO),
                            stdout=f, stderr=subprocess.STDOUT).returncode
    return tag, rc, time.time() - t0


def main() -> int:
    print(f"p4 spokes: {len(SPOKES)} jobs over {WORKERS} workers x {THREADS} threads", flush=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_job, tag, ov) for tag, ov in SPOKES]
        for fut in as_completed(futs):
            tag, rc, dt = fut.result()
            status = "ok" if rc == 0 else f"FAIL rc={rc}"
            failures += rc != 0
            print(f"  [{status}] {tag}  ({dt/60:.1f} min)", flush=True)
    print(f"=== P4 SPOKES DONE: {len(SPOKES)-failures}/{len(SPOKES)} ok, {failures} failed ===", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
