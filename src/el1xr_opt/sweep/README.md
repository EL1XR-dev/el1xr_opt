# el1xr_opt.sweep (DRAFT 2026-07-07)

A case-agnostic parameter-sweep runner with three modes. It generalises the sweep runner
prototyped in the H2VPP paper (`experiments/h2vpp_fcr/run_sweep.py`) so any el1xr_opt case
can sweep without copying the orchestration.

## Why a package

The paper runner already carries the three modes, but it is welded to that case's build
(`build_case.py`) and solve (`run_year.py`). The orchestration — cell ordering, parallelism,
skip-existing, manifest, cross-mode validation — is identical for every case. This package
keeps that orchestration in one place and puts the case-specific parts behind one interface,
`SweepAdapter`. openTEPES did the same: its runner lives in the package, not in a case.

## The split

- **Generic (this package):** `SweepSpec`/`Cell` (the spec), `Summary` + `compare` (the
  normalised result and its tolerance), the three drivers `run_registry` / `run_overlay` /
  `run_warm`, `validate`, the manifest, and a `main` CLI.
- **Case-specific (the adapter):** how a cell becomes a solved `Summary`. Everything else is
  the driver's job.

```
SweepSpec (json)  ->  driver (A/B/C)  ->  SweepAdapter hooks  ->  case build + solve
                          |                                            |
                          +-- manifest / compare / parallelism         +-- Summary
```

## The three modes

| Mode | Driver | Shape | Use when |
|------|--------|-------|----------|
| A registry | `run_registry` | build+solve each cell, serial | fallback; anything |
| B overlay | `run_overlay` | build once, scale input columns per cell, **parallel** | knobs are pure input scalings that would otherwise rebuild per cell (e.g. a DEG×price heatmap) |
| C warm | `run_warm` | build model once, hot-swap one coefficient family, warm-start, serial chain | the solve dominates and a single coefficient family changes (e.g. an FCR-price erosion curve) |

Overlay (B) and warm (C) are optional: an adapter that does not implement them returns
`(False, reason)` from `overlay_eligible` / `warm_eligible` and the driver falls back to A.

## Adapter contract (see `core.py`)

```python
class SweepAdapter(ABC):
    # all modes
    def summary_path(self, spec, cell) -> Path: ...          # where the cell summary lands
    def read_summary(self, path) -> Summary: ...             # parse -> {objective, capacities, ...}
    def workname(self, spec, cell) -> str: ...               # log/manifest label (default: tag)
    # Mode A
    def solve_cold(self, spec, cell, log_path, threads=None) -> int: ...
    # Mode B (optional)
    def overlay_eligible(self, spec) -> (bool, str): ...
    def materialize_base(self, spec) -> base: ...            # build once
    def prepare_overlay_cell(self, spec, base, cell) -> Path # scale columns -> workdir
    def solve_prebuilt(self, spec, cell, workdir, log_path, threads=None) -> int: ...
    # Mode C (optional)
    def warm_eligible(self, spec) -> (bool, str): ...
    def open_warm(self, spec) -> WarmSession: ...            # WarmSession.solve_cell(cell, first)
```

## How the H2VPP case adapts (sketch)

The existing `run_sweep.py` maps onto the adapter almost line for line — no new logic, just
relocation. Illustrative, not the final adapter:

```python
from el1xr_opt.sweep import SweepAdapter, Summary, WarmSession, main

class H2VPPAdapter(SweepAdapter):
    RESULTS = REPO / "results" / "h2vpp_fcr"

    def summary_path(self, spec, cell):
        return self.RESULTS / _work_name(spec, cell) / "summary_H2VPPFCR.json"

    def read_summary(self, path):
        d = json.loads(path.read_text())
        caps = {**d.get("ele_build", {}), **d.get("hyd_build", {}), **d.get("comp_build", {})}
        if d.get("ele_conn_cap_MW") is not None:
            caps["ele_conn_cap_MW"] = d["ele_conn_cap_MW"]
        return Summary(objective=d.get("eTotalSCost_SEK"), capacities=caps,
                       termination=d.get("termination"), raw=d)

    # Mode A: today's cold subprocess to run_year.py
    def solve_cold(self, spec, cell, log_path, threads=None):
        env = {**os.environ, **_cell_env(spec, cell)}
        if threads: env["THREADS"] = str(threads)
        with open(log_path, "w") as lf:
            return subprocess.run([PY, RUN_YEAR], env=env, cwd=REPO, stdout=lf,
                                  stderr=subprocess.STDOUT).returncode

    # Mode B: _OVERLAY_MAP + materialize_base + column scaling, then run_year with
    # SWEEP_PREBUILT_WORK=<workdir> (the build-skip knob already added to run_year.py)
    def overlay_eligible(self, spec):
        unmapped = spec.varying_params() - set(_OVERLAY_MAP)
        return (not unmapped, f"cells vary in {sorted(unmapped)}" if unmapped else "")
    def materialize_base(self, spec): ...        # build_case once at knob=1.0, patch options
    def prepare_overlay_cell(self, spec, base, cell): ...   # copy base + scale mapped columns
    def solve_prebuilt(self, spec, cell, workdir, log_path, threads=None): ...  # run_year PREBUILT

    # Mode C: gurobi_persistent build-once + chgCoeff on the FCR revenue family
    def warm_eligible(self, spec):
        vary = spec.varying_params()
        return (vary <= {"FCR_PRICE_SCALE"} and spec.base.get("LP") == "1", "...")
    def open_warm(self, spec) -> WarmSession: ...  # wraps _build_warm_model + _fcr_price_rows

if __name__ == "__main__":
    raise SystemExit(main(H2VPPAdapter(), sweep_root=H2VPPAdapter.RESULTS))
```

## Degenerate-LP note (carried over)

`compare` checks the objective (unique at the optimum) as the certificate and capacities as a
secondary check. On a degenerate LP two solves can share an objective but differ in the
capacity split, so the adapter must drive both solves to the **same vertex** before comparing
— e.g. force `Crossover=1` in the validation build. This bit both the warm and overlay gates
in the paper; the fix lives in the adapter's validation setup, not here.

## Status

- Reusable core + contract, import-clean (no case or Pyomo imports).
- **Wired:** the H2VPP case runs entirely through this package -- `experiments/h2vpp_fcr/
  run_sweep.py` is now `H2VPPAdapter` + `main(...)`. Gates pass through the adapter: Mode B
  overlay 5.5e-14, Mode C warm 5.1e-13 (on the box).
- **Tested:** `model/tests/test_sweep.py` -- a solver-free parity suite (a MockAdapter stands
  in for a case). 11 tests: spec parsing, compare tolerances, A==B==C parity, validate PASSES
  on agreement AND FAILS on a perturbed mode, overlay/warm fallback, skip-existing, the
  parallel pool. ~0.3 s, any OS, no solver.

## Second adapter (abstraction check)

`examples/home1_sweep.py` wires a Home1 price / generation-capacity / demand sweep to the same
contract, and it is deliberately *unlike* H2VPP:

- **in-process solve** via `oM_Sequence.routine` (HiGHS), not a subprocess;
- **different overlay files** with blank-named index columns (time series) and a per-unit table
  — the overlay round-trip preserves each file's index shape, which is why overlay application
  lives in the adapter, not here;
- **no warm mode** — `warm_eligible` stays False, so `--warm` falls back to the cold registry.

Lessons it surfaced: (1) the contract fits a second case unchanged; (2) an in-process solve is
GIL-bound, so its Mode B needs a per-cell lock and gives no speedup — a case wanting a genuinely
parallel Mode B should shell out per cell like H2VPP. Covered by `model/tests/test_sweep_home1.py`
(marked `solve`): Mode A == Mode B, and warm falls back.

## Next steps

- Promote any genuinely generic H2VPP helpers (the run_year subprocess wrapper) up here once a
  third case needs them.
