"""Generic Mode A / B / C drivers for el1xr_opt.sweep. These contain NO case specifics --
they orchestrate cells (ordering, parallelism, skip-existing, manifest, comparison) and call
the SweepAdapter for the case-dependent build/solve. See core.SweepAdapter and README.md.

DRAFT (2026-07-07).
"""
from __future__ import annotations

import json
import time
import shutil
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from .core import SweepSpec, Cell, Summary, SweepAdapter, compare, now


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

def _new_manifest(spec: SweepSpec, spec_path, adapter: SweepAdapter, mode: str) -> dict:
    cells = [{"tag": c.tag, "params": dict(c.params), "work": adapter.workname(spec, c),
              "status": "pending", "objective": None, "termination": None, "wall_s": None}
             for c in spec.cells]
    return {"sweep": spec.name, "spec": str(spec_path), "mode": mode, "case": spec.case,
            "base": spec.base, "created": now(), "cells": cells}


def _save(sweep_dir: Path, manifest: dict) -> None:
    manifest["updated"] = now()
    (sweep_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def _finish(adapter: SweepAdapter, spec, cell: Cell, rec: dict, sweep_dir: Path) -> bool:
    """Read the cell's summary into its manifest record + copy it to the sweep dir."""
    sp = adapter.summary_path(spec, cell)
    if not sp.exists():
        return False
    summ = adapter.read_summary(sp)
    rec["objective"] = summ.objective
    rec["termination"] = summ.termination
    shutil.copy2(sp, sweep_dir / f"sum_{cell.tag}.json")
    return True


# --------------------------------------------------------------------------
# Mode A: cold registry (sequential)
# --------------------------------------------------------------------------

def run_registry(adapter: SweepAdapter, spec: SweepSpec, spec_path, sweep_dir: Path,
                 force: bool) -> int:
    manifest = _new_manifest(spec, spec_path, adapter, "A-registry")
    _save(sweep_dir, manifest)
    n = len(spec.cells)
    failures = 0
    for i, (cell, rec) in enumerate(zip(spec.cells, manifest["cells"]), 1):
        sp = adapter.summary_path(spec, cell)
        if sp.exists() and not force:
            rec["status"] = "done" if _finish(adapter, spec, cell, rec, sweep_dir) else "failed"
            rec["skipped_existing"] = True
            _save(sweep_dir, manifest)
            print(f"[{i}/{n}] {cell.tag} skipped (summary exists)  objective={rec['objective']}",
                  flush=True)
            continue
        rec["status"] = "running"
        _save(sweep_dir, manifest)
        print(f"[{i}/{n}] {cell.tag} running -> {rec['work']}", flush=True)
        t0 = time.time()
        rc = adapter.solve_cold(spec, cell, sweep_dir / f"log_{cell.tag}.txt")
        rec["wall_s"] = round(time.time() - t0, 1)
        ok = rc == 0 and _finish(adapter, spec, cell, rec, sweep_dir)
        rec["status"] = "done" if ok else "failed"
        failures += 0 if ok else 1
        _save(sweep_dir, manifest)
        print(f"[{i}/{n}] {cell.tag} {rec['status']} in {rec['wall_s']}s  "
              f"objective={rec['objective']}  ({rec['termination']})", flush=True)
    print(f"sweep {spec.name}: {n - failures}/{n} done -> {sweep_dir / 'manifest.json'}", flush=True)
    return failures


# --------------------------------------------------------------------------
# Mode B: overlay sweep (parallel)
# --------------------------------------------------------------------------

def run_overlay(adapter: SweepAdapter, spec: SweepSpec, spec_path, sweep_dir: Path,
                force: bool, jobs: int, threads_total: int | None = None) -> int:
    ok, why = adapter.overlay_eligible(spec)
    if not ok:
        print(f"Mode B not applicable: {why}; running cold Mode A instead", flush=True)
        return run_registry(adapter, spec, spec_path, sweep_dir, force)

    manifest = _new_manifest(spec, spec_path, adapter, "B-overlay-parallel")
    manifest["jobs"] = jobs
    _save(sweep_dir, manifest)
    base = adapter.materialize_base(spec)
    per = max(1, threads_total // jobs) if threads_total else None
    n = len(spec.cells)
    lock = threading.Lock()
    print(f"Mode B: {n} cells over {jobs} worker(s)"
          + (f", {per} solver thread(s) each" if per else ""), flush=True)

    def work(cell: Cell, rec: dict) -> int:
        sp = adapter.summary_path(spec, cell)
        if sp.exists() and not force:
            with lock:
                rec["status"] = "done" if _finish(adapter, spec, cell, rec, sweep_dir) else "failed"
                rec["skipped_existing"] = True
                _save(sweep_dir, manifest)
            print(f"[{cell.tag}] skipped (summary exists)", flush=True)
            return 0 if rec["status"] == "done" else 1
        with lock:
            rec["status"] = "running"
            _save(sweep_dir, manifest)
        print(f"[{cell.tag}] solving -> {rec['work']}", flush=True)
        t0 = time.time()
        wd = adapter.prepare_overlay_cell(spec, base, cell)
        rc = adapter.solve_prebuilt(spec, cell, wd, sweep_dir / f"log_{cell.tag}.txt", threads=per)
        rec["wall_s"] = round(time.time() - t0, 1)
        good = rc == 0 and _finish(adapter, spec, cell, rec, sweep_dir)
        rec["status"] = "done" if good else "failed"
        with lock:
            _save(sweep_dir, manifest)
        print(f"[{cell.tag}] {rec['status']} in {rec['wall_s']}s  objective={rec['objective']}  "
              f"({rec['termination']})", flush=True)
        return 0 if good else 1

    failures = 0
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(work, c, r) for c, r in zip(spec.cells, manifest["cells"])]
        for f in as_completed(futs):
            failures += f.result()
    print(f"sweep {spec.name} (Mode B, {jobs} workers): {n - failures}/{n} done -> "
          f"{sweep_dir / 'manifest.json'}", flush=True)
    return failures


# --------------------------------------------------------------------------
# Mode C: warm hot-swap (sequential warm-start chain)
# --------------------------------------------------------------------------

def run_warm(adapter: SweepAdapter, spec: SweepSpec, spec_path, sweep_dir: Path,
             force: bool) -> int:
    ok, why = adapter.warm_eligible(spec)
    if not ok:
        print(f"Mode C not applicable: {why}; running cold Mode A instead", flush=True)
        return run_registry(adapter, spec, spec_path, sweep_dir, force)

    manifest = _new_manifest(spec, spec_path, adapter, "C-warm")
    _save(sweep_dir, manifest)
    session = adapter.open_warm(spec)
    n = len(spec.cells)
    failures = 0
    try:
        for i, (cell, rec) in enumerate(zip(spec.cells, manifest["cells"]), 1):
            sp = adapter.summary_path(spec, cell)
            if sp.exists() and not force:
                rec["status"] = "done" if _finish(adapter, spec, cell, rec, sweep_dir) else "failed"
                rec["skipped_existing"] = True
                _save(sweep_dir, manifest)
                print(f"[{i}/{n}] {cell.tag} skipped (summary exists)", flush=True)
                continue
            rec["status"] = "running"
            _save(sweep_dir, manifest)
            print(f"[{i}/{n}] {cell.tag} warm solve (first={i == 1}) ...", flush=True)
            t0 = time.time()
            summ = session.solve_cell(cell, first=(i == 1))
            rec["wall_s"] = round(time.time() - t0, 1)
            if summ.termination == "optimal" and summ.objective is not None:
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_text(json.dumps(summ.raw, indent=2))
                _finish(adapter, spec, cell, rec, sweep_dir)
                rec["status"] = "done"
            else:
                rec["status"] = "failed"
                rec["termination"] = summ.termination
                failures += 1
            _save(sweep_dir, manifest)
            print(f"[{i}/{n}] {cell.tag} {rec['status']} in {rec['wall_s']}s  "
                  f"objective={rec['objective']}  ({rec['termination']})", flush=True)
    finally:
        session.close()
    print(f"sweep {spec.name} (warm): {n - failures}/{n} done -> "
          f"{sweep_dir / 'manifest.json'}", flush=True)
    return failures


# --------------------------------------------------------------------------
# Cross-mode validation: run one cell two ways and compare
# --------------------------------------------------------------------------

def validate(adapter: SweepAdapter, spec: SweepSpec, spec_path, sweep_dir: Path, tag: str,
             other: str, **kw) -> int:
    """Solve cell `tag` cold (Mode A) AND via `other` mode ('overlay' | 'warm'), then compare.
    The adapter is responsible for making the two solves land on the same vertex (e.g. force
    crossover) so the capacity comparison is meaningful on a degenerate LP."""
    cells = {c.tag: c for c in spec.cells}
    if tag not in cells:
        raise SystemExit(f"validate {tag}: no such cell; tags: {sorted(cells)}")
    base = dict(spec.base)
    base.update(adapter.validation_base_override())   # e.g. force crossover on a degenerate LP
    case = dict(spec.case)
    case.update(adapter.validation_case_override())   # e.g. downgrade to the cheap horizon
    one = SweepSpec(name=f"val_{spec.name}", cells=[cells[tag]], base=base, case=case)

    run_registry(adapter, one, spec_path, sweep_dir, force=True)
    a = adapter.read_summary(adapter.summary_path(one, cells[tag]))

    if other == "overlay":
        run_overlay(adapter, one, spec_path, sweep_dir, force=True, jobs=1, **kw)
    elif other == "warm":
        run_warm(adapter, one, spec_path, sweep_dir, force=True)
    else:
        raise SystemExit(f"validate: unknown comparison mode {other!r}")
    b = adapter.read_summary(adapter.summary_path(one, cells[tag]))

    ok, lines = compare(a, b, "cold", other)
    verdict = "PASS" if ok else "FAIL"
    out = sweep_dir / f"validate_{other}_{tag}.json"
    out.write_text(json.dumps({"cell": tag, "compared": ("cold", other), "verdict": verdict,
                               "detail": lines, "when": now()}, indent=2))
    print("\n".join(lines), flush=True)
    print(f"validate {tag} [cold vs {other}]: {verdict} -> {out}", flush=True)
    return 0 if ok else 1


# --------------------------------------------------------------------------
# CLI: a case wires this to its adapter factory (see README.md)
# --------------------------------------------------------------------------

def main(adapter: SweepAdapter, sweep_root: Path, argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="el1xr_opt.sweep runner (Mode A / B / C)")
    ap.add_argument("spec", help="sweep spec JSON")
    ap.add_argument("--force", action="store_true", help="re-run cells whose summary exists")
    ap.add_argument("--parallel", type=int, metavar="N", help="Mode B: N parallel overlay workers")
    ap.add_argument("--warm", action="store_true", help="Mode C: warm hot-swap")
    ap.add_argument("--threads", type=int, help="total solver-thread budget to split across workers")
    ap.add_argument("--validate", metavar="TAG", help="compare cell TAG: cold vs (overlay|warm)")
    args = ap.parse_args(argv)
    if args.parallel and args.warm:
        raise SystemExit("--parallel (Mode B) and --warm (Mode C) are mutually exclusive")
    spec = SweepSpec.load(args.spec)
    sweep_dir = Path(sweep_root) / f"sweep_{spec.name}"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    threads_total = args.threads or int(spec.base.get("THREADS") or 0) or None

    if args.validate:
        other = "overlay" if args.parallel else "warm"   # default validate: cold vs warm
        kw = {"threads_total": threads_total} if other == "overlay" else {}
        return validate(adapter, spec, args.spec, sweep_dir, args.validate, other, **kw)
    if args.parallel:
        return 1 if run_overlay(adapter, spec, args.spec, sweep_dir, args.force,
                                args.parallel, threads_total) else 0
    if args.warm:
        return 1 if run_warm(adapter, spec, args.spec, sweep_dir, args.force) else 0
    return 1 if run_registry(adapter, spec, args.spec, sweep_dir, args.force) else 0
