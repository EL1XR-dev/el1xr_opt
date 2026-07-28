"""Full campaign re-run under the response-speed reserve realism (ELE_FCR_RESPONSE=1).

Generalising the FCR-down endurance across the pressure cascade let the electrolyser take ~100% of
every reserve; the response-speed cap (an electrolyser can offer only ramp x activation-window of its
capacity, tight for the fast FCR-D, looser for FCR-N) brings the split back to a physical division of
labour. This re-runs the 14 headline cases (Table 2) and the 4 business-case spokes (Table S6) under
the SAME p4 config that built the originals (jobs/done/p4_A3.cmd) plus ELE_FCR_RESPONSE=1, so the only
change is the response realism. Figure-data cells (econ/cycling/heatmap/fcr) are a separate follow-up.

    set PYTHONPATH=model\\src & python experiments\\h2vpp_fcr\\run_resp_campaign_parallel.py

Outputs (under OUT_BASE=D:\\h2vpp_work): headline -> work_year_<V>_resp; spokes -> work_year_A3_<tag>_resp.
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
LOGDIR = REPO / "results" / "resp_campaign"
LOGDIR.mkdir(parents=True, exist_ok=True)

WORKERS = int(os.environ.get("PWORKERS", "4"))
THREADS = int(os.environ.get("PTHREADS", "3"))

# The authoritative p4 campaign env (jobs/done/p4_A3.cmd) + the response-speed realism.
COMMON = {
    "PYTHONPATH": "model\\src",
    "OUT_BASE": "D:\\h2vpp_work",
    "PRESSURE_NODES": "1", "ENHANCED_PROFILES": "1", "MONEY_BASE": "1000",
    "PEAK_THRESHOLD_LP": "1", "LP": "1", "AEL_N": "6", "PEM_N": "6",
    "COMPRESSOR_NAMEPLATE_KG": "1000", "WIND_MAX_POWER_KW": "60000",
    "LINE_TTC_KW": "60000", "ELE_BUY_CAP_KW": "60000",
    "TIMELIMIT": "7200", "THREADS": str(THREADS), "H2VPP_HORIZON": "year",
    "ELE_FCRD_RAMPGATE": "1", "AEL_FCRD_RAMP_PER_S": "0.02", "PEM_FCRD_RAMP_PER_S": "0.10",
}

HEADLINE = ["A1", "A2", "A3", "B0", "B1", "B2", "C2", "D1", "D2", "S1", "S2", "S3", "S4", "S5"]
SPOKES = [
    ("S6_cycoff", {"CYCLING_SCALE": "0"}),
    ("S7_bpoff", {"BYPRODUCT_SCALE": "0"}),
    ("S8_windppa", {"WIND_MODE": "ppa"}),
    ("S9_connfree", {"CONNECTION_SCALE": "0"}),
]


def _jobs():
    jobs = []
    for v in HEADLINE:
        jobs.append((f"{v}", {"VARIANT": v, "RUN_TAG": "resp"}))
    for tag, ov in SPOKES:
        d = {"VARIANT": "A3", "RUN_TAG": f"{tag}_resp"}
        d.update(ov)
        jobs.append((f"A3_{tag}", d))
    return jobs


def run_job(label, overrides):
    env = os.environ.copy()
    env.update(COMMON)
    env.update(overrides)
    t0 = time.time()
    with open(LOGDIR / f"{label}.log", "w") as f:
        rc = subprocess.run([PY, str(RUN_YEAR)], env=env, cwd=str(REPO),
                            stdout=f, stderr=subprocess.STDOUT).returncode
    return label, rc, time.time() - t0


def main():
    jobs = _jobs()
    print(f"resp campaign: {len(jobs)} year jobs over {WORKERS} workers x {THREADS} threads", flush=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_job, lbl, ov) for lbl, ov in jobs]
        for fut in as_completed(futs):
            label, rc, dt = fut.result()
            status = "ok" if rc == 0 else f"FAIL rc={rc}"
            failures += rc != 0
            print(f"  [{status}] {label}  ({dt/60:.1f} min)", flush=True)
    print(f"=== RESP CAMPAIGN DONE: {len(jobs)-failures}/{len(jobs)} ok, {failures} failed ===", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
