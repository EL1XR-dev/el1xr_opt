"""Core types for el1xr_opt.sweep: the spec, the normalised summary, and the adapter
contract a case implements so the generic mode drivers can drive it.

DRAFT (2026-07-07). Promotes the three sweep modes prototyped in the H2VPP paper's
experiments/h2vpp_fcr/run_sweep.py into a reusable, case-agnostic package. The paper
runner becomes a thin adapter (see README.md). Nothing here imports paper code or Pyomo;
all case specifics live behind SweepAdapter.
"""
from __future__ import annotations

import json
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class NotSupported(RuntimeError):
    """Raised by an adapter for a mode (overlay / warm) it does not implement."""


# --------------------------------------------------------------------------
# Spec + summary
# --------------------------------------------------------------------------

@dataclass
class Cell:
    """One sweep point: a short unique tag plus the case parameters that define it."""
    tag: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SweepSpec:
    """A sweep: a named set of cells over a shared baseline. `base` holds parameters
    common to every cell (the case's flags/solver options); `case` carries any extra
    case-level fields the adapter needs (e.g. variant, horizon). Deliberately generic --
    the adapter interprets `params` / `base` / `case`, this package never inspects them."""
    name: str
    cells: list[Cell]
    base: dict[str, Any] = field(default_factory=dict)
    case: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "SweepSpec":
        path = Path(path)
        d = json.loads(path.read_text())
        cells = [Cell(tag=c["tag"], params=dict(c.get("params") or c.get("env") or {}))
                 for c in d.get("cells", [])]
        if not cells:
            raise ValueError(f"spec {path} has no cells")
        tags = [c.tag for c in cells]
        if len(set(tags)) != len(tags):
            raise ValueError(f"spec {path}: cell tags must be unique")
        case = dict(d.get("case") or {})
        for k in ("variant", "horizon"):          # convenience: hoist common case fields
            if k in d:
                case[k] = d[k]
        return cls(name=d.get("name") or path.stem, cells=cells,
                   base=dict(d.get("base") or d.get("base_env") or {}), case=case)

    def varying_params(self) -> set[str]:
        """Param keys whose value is not identical across all cells."""
        keys: set[str] = set().union(*[set(c.params) for c in self.cells]) if self.cells else set()
        return {k for k in keys if len({str(c.params.get(k)) for c in self.cells}) > 1}


@dataclass
class Summary:
    """Normalised solve result the drivers compare on. The adapter maps its own summary
    schema into this; `raw` keeps the full case-specific dict for the report."""
    objective: float | None
    capacities: dict[str, float] = field(default_factory=dict)
    termination: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def compare(a: Summary, b: Summary, la: str, lb: str,
            obj_rtol: float = 1e-6, cap_atol: float = 1e-6) -> tuple[bool, list[str]]:
    """Objective to a relative tol, capacities to an absolute+relative tol. The objective
    is the certificate (unique at the LP optimum); capacities are only well-defined when the
    two solves land on the same vertex, so drive both to a vertex before comparing."""
    lines: list[str] = []
    if a.objective is None or b.objective is None:
        return False, [f"missing objective: {la}={a.objective} {lb}={b.objective}"]
    rel = abs(a.objective - b.objective) / max(abs(a.objective), abs(b.objective), 1.0)
    ok = rel <= obj_rtol
    lines.append(f"objective: {la}={a.objective:.6f}  {lb}={b.objective:.6f}  "
                 f"rel_diff={rel:.3e}  {'OK' if ok else 'FAIL'}")
    for u in sorted(set(a.capacities) | set(b.capacities)):
        xa, xb = a.capacities.get(u, 0.0), b.capacities.get(u, 0.0)
        good = abs(xa - xb) <= cap_atol * (1.0 + max(abs(xa), abs(xb)))
        ok &= good
        if not good:
            lines.append(f"{u}: {la}={xa:.8f}  {lb}={xb:.8f}  diff={abs(xa - xb):.3e}  FAIL")
    if ok:
        lines.append("capacities: all within tol")
    return ok, lines


# --------------------------------------------------------------------------
# Adapter contract
# --------------------------------------------------------------------------

class WarmSession(ABC):
    """A built-once model plus persistent solver for Mode C. `solve_cell` rescales the warm
    coefficient family to the cell and re-solves (warm-started after the first cell)."""

    @abstractmethod
    def solve_cell(self, cell: Cell, first: bool) -> Summary: ...

    def close(self) -> None:  # optional resource cleanup
        pass


class SweepAdapter(ABC):
    """What a case implements so el1xr_opt.sweep can run Mode A/B/C over it.

    A/B/C differ only in HOW a cell is turned into a solved Summary; everything else
    (ordering, parallelism, skip-existing, manifest, comparison) lives in the drivers.
    Overlay (B) and warm (C) are optional -- the default eligibility says "no" and the
    driver falls back to the cold registry (A).
    """

    # --- identity + io (all modes) ---
    @abstractmethod
    def summary_path(self, spec: SweepSpec, cell: Cell) -> Path:
        """Absolute path where this cell's summary file lands (also used for skip-existing)."""

    @abstractmethod
    def read_summary(self, path: Path) -> Summary:
        """Parse a summary file written by a solve into the normalised Summary."""

    def workname(self, spec: SweepSpec, cell: Cell) -> str:
        """Short human label for logs/manifest (default: the tag)."""
        return cell.tag

    def validation_base_override(self) -> dict[str, Any]:
        """Extra base params applied to BOTH sides during validate(), so the two solves are
        comparable. Default: none. A case with a degenerate LP returns e.g. {'CROSSOVER': '1'}
        so both land on the same vertex and the capacity check is meaningful (and may pin a
        solver here, e.g. fall back to a free solver when the licensed one is unavailable)."""
        return {}

    def validation_case_override(self) -> dict[str, Any]:
        """Extra case fields applied to BOTH sides during validate(). Default: none. A case
        typically returns its cheapest horizon here so validation is fast, e.g. {'horizon':
        'week'}."""
        return {}

    # --- Mode A: cold registry ---
    @abstractmethod
    def solve_cold(self, spec: SweepSpec, cell: Cell, log_path: Path,
                   threads: int | None = None) -> int:
        """Build AND solve this cell from scratch, writing its summary to summary_path(cell).
        Return 0 on success. Runs one at a time (Mode A) or in a worker pool (Mode B fallback)."""

    # --- Mode B: in-memory overlay (optional) ---
    def overlay_eligible(self, spec: SweepSpec) -> tuple[bool, str]:
        return False, "overlay (Mode B) not implemented for this case"

    def materialize_base(self, spec: SweepSpec) -> Any:
        """Build the shared baseline ONCE; return a handle the overlay steps understand."""
        raise NotSupported

    def prepare_overlay_cell(self, spec: SweepSpec, base: Any, cell: Cell) -> Path:
        """Produce this cell's inputs by overlaying `base` (no rebuild); return its work dir."""
        raise NotSupported

    def solve_prebuilt(self, spec: SweepSpec, cell: Cell, workdir: Path, log_path: Path,
                       threads: int | None = None) -> int:
        """Solve a cell whose inputs are already materialised at `workdir`; write its summary."""
        raise NotSupported

    # --- Mode C: warm hot-swap (optional) ---
    def warm_eligible(self, spec: SweepSpec) -> tuple[bool, str]:
        return False, "warm (Mode C) not implemented for this case"

    def open_warm(self, spec: SweepSpec) -> WarmSession:
        """Build the model + persistent solver once; return a WarmSession over the cells."""
        raise NotSupported


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")
