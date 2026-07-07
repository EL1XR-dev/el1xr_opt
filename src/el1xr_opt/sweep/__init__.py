"""el1xr_opt.sweep -- a case-agnostic parameter-sweep runner with three modes.

DRAFT (2026-07-07). Promotes the sweep modes prototyped in the H2VPP paper into a reusable
package. A case implements SweepAdapter (build + solve hooks); the drivers own everything
else. See README.md for the design and the H2VPP adapter sketch.

Modes:
  A registry  -- build + solve each cell from scratch, sequentially.
  B overlay   -- build the case once, reproduce each cell by scaling a fixed set of input
                 columns, solve the cells in parallel. For sweeps whose knobs are pure input
                 scalings (the ones that would otherwise force a rebuild per cell).
  C warm      -- build the model once, hot-swap one coefficient family per cell, warm-start
                 re-solve. A serial chain; best when the expensive solve dominates and only a
                 single coefficient family changes.

Typical case entry point:
    from el1xr_opt.sweep import main
    raise SystemExit(main(MyCaseAdapter(), sweep_root=RESULTS))
"""
from .core import (Cell, SweepSpec, Summary, SweepAdapter, WarmSession, NotSupported, compare)
from .modes import run_registry, run_overlay, run_warm, validate, main

__all__ = ["Cell", "SweepSpec", "Summary", "SweepAdapter", "WarmSession", "NotSupported",
           "compare", "run_registry", "run_overlay", "run_warm", "validate", "main"]
