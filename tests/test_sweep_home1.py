"""Parity test for the SECOND sweep adapter (Home1), the one that stresses the abstraction.

Unlike test_sweep.py (a solver-free MockAdapter), this actually builds and solves Home1
through el1xr_opt.sweep, so it is marked `solve` and skipped in the fast suite. It proves the
generic drivers work on a real, structurally different case:

  * Mode A (cold registry) and Mode B (overlay) give the SAME objective per cell;
  * the sweep does something (the price / generation-capacity knobs move the objective);
  * Mode C falls back to the cold registry, because Home1 leaves warm unimplemented.

Home1 is truncated to 24 load levels here so each in-process HiGHS solve is well under a second.
"""
import json

import pytest

from el1xr_opt.sweep import SweepSpec, Cell, run_registry, run_overlay, run_warm


def _objs(sweep_dir):
    man = json.loads((sweep_dir / "manifest.json").read_text())
    return man["mode"], {c["tag"]: c["objective"] for c in man["cells"]}


@pytest.mark.solve
def test_home1_second_adapter_A_eq_B(tmp_path):
    from el1xr_opt.sweep.examples.home1_sweep import Home1Adapter

    ad = Home1Adapter(root=tmp_path, trunc=24)
    spec = SweepSpec(name="h1",
                     cells=[Cell("base", {}),
                            Cell("p150", {"PRICE_SCALE": "1.5"}),
                            Cell("g050", {"GEN_SCALE": "0.5"})],
                     base={}, case={})

    sd_a = tmp_path / "sweep_A"
    sd_a.mkdir()
    assert run_registry(ad, spec, "h1", sd_a, force=True) == 0
    mode_a, a = _objs(sd_a)
    assert mode_a == "A-registry"

    sd_b = tmp_path / "sweep_B"
    sd_b.mkdir()
    assert run_overlay(ad, spec, "h1", sd_b, force=True, jobs=2) == 0
    mode_b, b = _objs(sd_b)
    assert mode_b == "B-overlay-parallel"

    # A == B cell-for-cell (the overlay reproduces a cold build)
    for tag in a:
        assert a[tag] is not None
        assert a[tag] == pytest.approx(b[tag], abs=1e-6)
    # the price and generation knobs actually move the objective (3 distinct values)
    assert len({round(v, 6) for v in a.values()}) == 3


@pytest.mark.solve
def test_home1_warm_falls_back_to_cold(tmp_path):
    from el1xr_opt.sweep.examples.home1_sweep import Home1Adapter

    ad = Home1Adapter(root=tmp_path, trunc=24)
    spec = SweepSpec(name="h1w", cells=[Cell("p150", {"PRICE_SCALE": "1.5"})], base={}, case={})
    sd = tmp_path / "sweep_W"
    sd.mkdir()
    run_warm(ad, spec, "h1w", sd, force=True)          # Home1 has no warm family
    assert _objs(sd)[0] == "A-registry"                # so it falls back to the cold registry
