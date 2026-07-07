"""A second SweepAdapter: a Home1 demand / price / generation-capacity sweep.

Its whole purpose is to stress the SweepAdapter abstraction with a case shaped differently from
H2VPP, and it surfaces three real lessons:

  * DIFFERENT SOLVE PATH. It solves IN-PROCESS via el1xr_opt.Modules.oM_Sequence.routine (HiGHS),
    not a subprocess. The contract fits either way -- solve_cold / solve_prebuilt just have to
    write a summary and return 0.
  * DIFFERENT OVERLAY FILES. The overlay columns live in different files and, unlike H2VPP, in
    tables with BLANK-named index columns (the time series) and a per-unit table -- so the
    overlay round-trip must preserve each file's index shape (read with the right index_col,
    write with the index). This is why overlay application lives in the adapter, not the package.
  * NO WARM MODE. Home1 has no single hot-swappable coefficient family, so warm_eligible is left
    at its default False; --warm then falls back to the cold registry. The optional-mode design
    earns its keep.

GIL NOTE: because the solve is in-process (a pure-Python Pyomo build under the GIL), a module
lock serialises concurrent Mode B cells -- --parallel stays CORRECT but yields no speedup here.
A case that wants a genuinely parallel Mode B should shell out per cell as the H2VPP adapter
does. That contrast is the point of this example.

Usage:
    python -m el1xr_opt.sweep.examples.home1_sweep <spec.json> [--parallel N]
        [--validate TAG --parallel N]
"""
import os
import sys
import json
import shutil
import datetime
import threading
import contextlib
from pathlib import Path

import numpy as np
import pandas as pd

from el1xr_opt.sweep import SweepAdapter, Summary, main as sweep_main

CASE = "Home1"
HOME1_SRC = Path(__file__).resolve().parents[2] / CASE          # el1xr_opt/Home1
_SOLVE_LOCK = threading.Lock()   # in-process Pyomo build is not thread-safe; serialise cells

# knob -> [(file, index_cols, [data columns])]; each is a uniform scale on the base (knob=1.0).
_OVERLAY = {
    "DEMAND_SCALE": [(f"oM_Data_VarMaxDemand_{CASE}.csv", [0, 1, 2], ["EleD_01"])],
    "PRICE_SCALE":  [(f"oM_Data_VarEnergyPrice_{CASE}.csv", [0, 1, 2], ["EleR_01"])],
    "GEN_SCALE":    [(f"oM_Data_ElectricityGeneration_{CASE}.csv", [0], ["MaximumPower"])],
}


def _truncate(case_dir, trunc):
    """Blank the Duration of load levels past `trunc` so the solve is fast (one week by default),
    mirroring the el1xr_opt test harness."""
    p = case_dir / f"oM_Data_Duration_{CASE}.csv"
    df = pd.read_csv(p, index_col=[0, 1, 2])
    df.iloc[trunc:, df.columns.get_loc("Duration")] = np.nan
    df.to_csv(p)


def _apply_overlays(case_dir, params):
    """Scale the overlay columns by this cell's knob values, preserving each file's index shape."""
    for knob, targets in _OVERLAY.items():
        factor = float(params.get(knob, 1.0) or 1.0)
        if factor == 1.0:
            continue
        for fname, idx, cols in targets:
            fp = case_dir / fname
            df = pd.read_csv(fp, index_col=idx)
            for c in cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce") * factor
            df.to_csv(fp)


class Home1Adapter(SweepAdapter):
    def __init__(self, root=None, trunc=None):
        self.root = Path(root or os.environ.get("HOME1_SWEEP_ROOT", Path.cwd() / "home1_sweeps"))
        self.trunc = int(trunc or os.environ.get("HOME1_TRUNC", "168"))

    # identity + io
    def summary_path(self, spec, cell):
        return self.root / spec.name / cell.tag / "summary.json"

    def read_summary(self, path):
        d = json.loads(Path(path).read_text())
        return Summary(objective=d.get("objective"), capacities=d.get("capacities", {}),
                       termination=d.get("termination"), raw=d)

    # shared build + solve
    def _prepare(self, spec, cell):
        work = self.summary_path(spec, cell).parent
        cdir = work / CASE
        if cdir.exists():
            shutil.rmtree(cdir)
        cdir.mkdir(parents=True, exist_ok=True)
        for f in HOME1_SRC.glob("*.csv"):
            shutil.copy2(f, cdir / f.name)
        _truncate(cdir, self.trunc)
        _apply_overlays(cdir, cell.params)
        return work

    def _solve(self, spec, cell, work, log_path):
        from el1xr_opt.Modules.oM_Sequence import routine
        import pyomo.environ as pyo
        date = datetime.datetime.now().replace(second=0, microsecond=0)
        sp = self.summary_path(spec, cell)
        try:
            with _SOLVE_LOCK:
                os.environ["EL1XR_HIGHS_DETERMINISTIC"] = "1"   # reproducible objective
                with open(log_path, "w") as lf, contextlib.redirect_stdout(lf):
                    model = routine(dir=str(work), case=CASE, solver="highs", date=date,
                                    rawresults="False", plots="False", indlog="False",
                                    duckdbresults="False")
                obj = float(pyo.value(model.eTotalSCost))
            sp.write_text(json.dumps({"objective": obj, "capacities": {},
                                      "termination": "optimal", "params": dict(cell.params)},
                                     indent=2))
            return 0
        except Exception as exc:
            sp.write_text(json.dumps({"objective": None, "termination": f"error: {exc}"}))
            return 1

    # Mode A
    def solve_cold(self, spec, cell, log_path, threads=None):
        return self._solve(spec, cell, self._prepare(spec, cell), log_path)

    # Mode B
    def overlay_eligible(self, spec):
        unmapped = spec.varying_params() - set(_OVERLAY)
        if unmapped:
            return False, (f"cells vary in {sorted(unmapped)}, not overlay-mappable "
                           f"(only {sorted(_OVERLAY)} scale a fixed input-column set)")
        return True, ""

    def materialize_base(self, spec):
        return HOME1_SRC                       # the case is static CSVs; the base IS the source

    def prepare_overlay_cell(self, spec, base, cell):
        return self._prepare(spec, cell)

    def solve_prebuilt(self, spec, cell, workdir, log_path, threads=None):
        return self._solve(spec, cell, workdir, log_path)

    # Mode C: not implemented -> warm_eligible stays False -> --warm falls back to cold.


if __name__ == "__main__":
    root = Path(os.environ.get("HOME1_SWEEP_ROOT", Path.cwd() / "home1_sweeps"))
    sys.exit(sweep_main(Home1Adapter(root=root), root))
