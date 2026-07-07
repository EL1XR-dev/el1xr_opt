"""Fast, no-solve tests for el1xr_opt.sweep -- the case-agnostic sweep runner.

These never build or solve a model: a deterministic MockAdapter stands in for a case, so the
tests run on every OS/Python in CI without a solver. They check the parts that must hold for
any case:

  * SweepSpec parsing (base_env/env aliases, variant/horizon hoist, varying_params, guards);
  * compare() tolerances (objective is the certificate; capacities secondary);
  * the three drivers all produce the SAME objectives on the same cells (parity);
  * validate() PASSES when the modes agree AND FAILS when a mode is perturbed (the gate works);
  * overlay/warm fall back to the cold registry when a spec is not eligible;
  * skip-existing and the parallel Mode B pool.
"""
import json
from pathlib import Path

import pytest

from el1xr_opt.sweep import (Cell, SweepSpec, Summary, SweepAdapter, WarmSession, compare,
                             run_registry, run_overlay, run_warm, validate)


# --------------------------------------------------------------------------
# A deterministic, solver-free stand-in for a real case
# --------------------------------------------------------------------------

class MockAdapter(SweepAdapter):
    """Objective is a fixed function of the cell knobs, so every mode MUST agree unless
    `buggy` perturbs one of them. Overlay knobs: DEG, PR. Warm knob: PR only."""

    def __init__(self, root, buggy=None):
        self.root = Path(root)
        self.buggy = buggy   # None | "overlay" | "warm" -> that mode returns a wrong objective

    def _obj(self, params, bump=0.0):
        deg = float(params.get("DEG", 1.0))
        pr = float(params.get("PR", 1.0))
        return -(100.0 + 10.0 * deg + 5.0 * pr) + bump

    def _raw(self, cell, bump=0.0):
        return {"obj": self._obj(cell.params, bump),
                "caps": {"a": float(cell.params.get("DEG", 1.0))}, "term": "optimal"}

    def _write(self, spec, cell, bump=0.0):
        p = self.summary_path(spec, cell)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._raw(cell, bump)))
        return 0

    # identity + io
    def summary_path(self, spec, cell):
        return self.root / spec.name / f"{cell.tag}.json"

    def read_summary(self, path):
        d = json.loads(Path(path).read_text())
        return Summary(objective=d["obj"], capacities=d["caps"], termination=d["term"], raw=d)

    # Mode A
    def solve_cold(self, spec, cell, log_path, threads=None):
        return self._write(spec, cell)

    # Mode B
    def overlay_eligible(self, spec):
        bad = spec.varying_params() - {"DEG", "PR"}
        return (not bad, f"unmapped {sorted(bad)}" if bad else "")

    def materialize_base(self, spec):
        return "BASE"

    def prepare_overlay_cell(self, spec, base, cell):
        return self.root / "wd" / cell.tag

    def solve_prebuilt(self, spec, cell, workdir, log_path, threads=None):
        return self._write(spec, cell, bump=0.5 if self.buggy == "overlay" else 0.0)

    # Mode C
    def warm_eligible(self, spec):
        bad = spec.varying_params() - {"PR"}
        return (not bad, f"warm only PR ({sorted(bad)})" if bad else "")

    def open_warm(self, spec):
        outer = self

        class _S(WarmSession):
            def solve_cell(self, cell, first):
                raw = outer._raw(cell, bump=0.5 if outer.buggy == "warm" else 0.0)
                return Summary(objective=raw["obj"], capacities=raw["caps"],
                               termination="optimal", raw=raw)
        return _S()


def _spec(name="s", knobs=("PR",), n=3):
    """A spec whose cells vary the given knob(s)."""
    cells = [Cell(tag=f"c{i}", params={k: str(round(1.0 - 0.25 * i, 2)) for k in knobs})
             for i in range(n)]
    return SweepSpec(name=name, cells=cells, base={"LP": "1"}, case={})


def _objs(sweep_dir):
    man = json.loads((sweep_dir / "manifest.json").read_text())
    return man["mode"], {c["tag"]: c["objective"] for c in man["cells"]}


# --------------------------------------------------------------------------
# spec + compare
# --------------------------------------------------------------------------

def test_spec_load_aliases(tmp_path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"variant": "A3", "horizon": "week",
                             "base_env": {"LP": "1"},
                             "cells": [{"tag": "a", "env": {"PR": "1.0"}},
                                       {"tag": "b", "env": {"PR": "0.5"}}]}))
    spec = SweepSpec.load(p)
    assert spec.name == "spec"
    assert spec.base == {"LP": "1"}                    # base_env alias
    assert spec.case == {"variant": "A3", "horizon": "week"}  # hoisted
    assert spec.cells[0].params == {"PR": "1.0"}       # env alias
    assert spec.varying_params() == {"PR"}


def test_spec_guards(tmp_path):
    dup = tmp_path / "dup.json"
    dup.write_text(json.dumps({"cells": [{"tag": "a"}, {"tag": "a"}]}))
    with pytest.raises(ValueError):
        SweepSpec.load(dup)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"cells": []}))
    with pytest.raises(ValueError):
        SweepSpec.load(empty)


def test_compare_tolerances():
    a = Summary(objective=-100.0, capacities={"x": 1.0})
    assert compare(a, Summary(objective=-100.0 + 1e-9, capacities={"x": 1.0}), "a", "b")[0]
    assert not compare(a, Summary(objective=-100.5, capacities={"x": 1.0}), "a", "b")[0]
    # objective agrees but a capacity is off -> fail
    assert not compare(a, Summary(objective=-100.0, capacities={"x": 1.1}), "a", "b")[0]


# --------------------------------------------------------------------------
# drivers + parity
# --------------------------------------------------------------------------

def test_registry_runs(tmp_path):
    ad = MockAdapter(tmp_path)
    spec = _spec()
    sd = tmp_path / "sweep_s"
    sd.mkdir()
    assert run_registry(ad, spec, "s.json", sd, force=True) == 0
    mode, objs = _objs(sd)
    assert mode == "A-registry"
    assert len(objs) == 3 and all(v is not None for v in objs.values())
    assert (sd / "sum_c0.json").exists()               # copied for the figure layout


def test_modes_parity(tmp_path):
    """The heart of it: A, B and C must agree cell-for-cell on a PR-only sweep."""
    spec = _spec(knobs=("PR",), n=4)
    runs = {}
    for label, fn in [("A", lambda sd: run_registry(MockAdapter(tmp_path), spec, "s", sd, True)),
                      ("B", lambda sd: run_overlay(MockAdapter(tmp_path), spec, "s", sd, True,
                                                   jobs=3, threads_total=6)),
                      ("C", lambda sd: run_warm(MockAdapter(tmp_path), spec, "s", sd, True))]:
        sd = tmp_path / f"sweep_{label}"
        sd.mkdir()
        assert fn(sd) == 0
        runs[label] = _objs(sd)[1]
    for tag in runs["A"]:
        assert runs["A"][tag] == pytest.approx(runs["B"][tag], abs=1e-12)
        assert runs["A"][tag] == pytest.approx(runs["C"][tag], abs=1e-12)
    # cells are actually distinct (the sweep does something)
    assert len(set(runs["A"].values())) == 4


def test_validate_pass(tmp_path):
    spec = _spec(knobs=("PR",))
    sd = tmp_path / "sweep_val"
    sd.mkdir()
    assert validate(MockAdapter(tmp_path), spec, "s", sd, "c1", "overlay") == 0
    assert validate(MockAdapter(tmp_path), spec, "s", sd, "c1", "warm") == 0


def test_validate_catches_divergence(tmp_path):
    """A perturbed mode MUST make the gate fail -- otherwise the gate is worthless."""
    spec = _spec(knobs=("PR",))
    sd = tmp_path / "sweep_bug"
    sd.mkdir()
    assert validate(MockAdapter(tmp_path, buggy="overlay"), spec, "s", sd, "c1", "overlay") == 1
    assert validate(MockAdapter(tmp_path, buggy="warm"), spec, "s", sd, "c1", "warm") == 1


# --------------------------------------------------------------------------
# eligibility fallbacks + orchestration
# --------------------------------------------------------------------------

def test_overlay_falls_back_when_ineligible(tmp_path):
    spec = _spec(knobs=("OTHER",))                     # OTHER is not overlay-mappable
    sd = tmp_path / "sweep_ov"
    sd.mkdir()
    run_overlay(MockAdapter(tmp_path), spec, "s", sd, force=True, jobs=2)
    assert _objs(sd)[0] == "A-registry"                # fell back to cold


def test_warm_falls_back_when_ineligible(tmp_path):
    spec = _spec(knobs=("DEG",))                        # warm only accepts PR
    sd = tmp_path / "sweep_wm"
    sd.mkdir()
    run_warm(MockAdapter(tmp_path), spec, "s", sd, force=True)
    assert _objs(sd)[0] == "A-registry"


def test_skip_existing(tmp_path):
    ad = MockAdapter(tmp_path)
    spec = _spec()
    sd = tmp_path / "sweep_skip"
    sd.mkdir()
    run_registry(ad, spec, "s", sd, force=True)
    run_registry(ad, spec, "s", sd, force=False)       # summaries exist now
    man = json.loads((sd / "manifest.json").read_text())
    assert all(c.get("skipped_existing") for c in man["cells"])


def test_parallel_pool_completes(tmp_path):
    spec = _spec(knobs=("PR",), n=8)
    sd = tmp_path / "sweep_par"
    sd.mkdir()
    assert run_overlay(MockAdapter(tmp_path), spec, "s", sd, force=True, jobs=4,
                       threads_total=8) == 0
    mode, objs = _objs(sd)
    assert mode == "B-overlay-parallel"
    assert len(objs) == 8 and all(v is not None for v in objs.values())
