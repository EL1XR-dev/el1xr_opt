"""The command line: exit codes of el1xr-run and python -m el1xr_opt, and the Home1 copy in data/."""
import filecmp
import os
import shutil
import subprocess
import sys

import pytest

from el1xr_opt import el1xr_Main

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_cli_exits_with_zero_after_a_run(monkeypatch):
    """main() returns the model; cli() turns a finished run into exit code 0."""
    monkeypatch.setattr(el1xr_Main, "main", lambda: object())
    assert el1xr_Main.cli() == 0


def test_cli_lets_a_failed_run_raise(monkeypatch):
    def fail():
        raise FileNotFoundError("no case")
    monkeypatch.setattr(el1xr_Main, "main", fail)
    with pytest.raises(FileNotFoundError):
        el1xr_Main.cli()


def test_console_script_points_at_cli():
    text = open(os.path.join(REPO, "pyproject.toml")).read()
    assert 'el1xr-run = "el1xr_opt.el1xr_Main:cli"' in text


def test_data_home1_matches_the_packaged_case():
    """``--dir data --case Home1`` runs the same case as the package's Home1."""
    src = os.path.join(REPO, "src", "el1xr_opt", "Home1")
    dst = os.path.join(REPO, "data", "Home1")
    names = sorted(f for f in os.listdir(src) if f.endswith(".csv"))
    match, mismatch, missing = filecmp.cmpfiles(src, dst, names, shallow=False)
    assert not mismatch and not missing, (mismatch, missing)


@pytest.mark.solve
def test_python_m_exits_with_zero(tmp_path):
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", "Home1"), tmp_path / "Home1")
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "src"))
    run = subprocess.run([sys.executable, "-m", "el1xr_opt", "--dir", str(tmp_path), "--case", "Home1",
                          "--solver", "highs", "--date", "2025-01-01 00:00:00", "--rawresults", "False",
                          "--plots", "False", "--duckdbresults", "False", "--indlog", "False"],
                         env=env, capture_output=True, text=True, timeout=900)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
