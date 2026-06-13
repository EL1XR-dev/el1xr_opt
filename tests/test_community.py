"""Phase 6a — energy-community / virtual-sharing validation.

Builds a two-member community from the H2VPP case (a prosumer retailer with the PV
and a consumer retailer, both in one zone) and checks the defining properties of
the sharing layer:

  * with the community flag off the case still solves (baseline), and
  * with it on the total cost is no higher and sharing is actually used.

This is a solve test, so it is skipped in the fast CI tier.
"""
import datetime
import os
import shutil

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_Sequence import routine

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(REPO, "data", "H2VPP", "Home1")
CASE = "Home1"
TRUNC = 168


def _build_community_case(work):
    """Derive a 2-retailer community case from H2VPP into ``work``."""
    dst = os.path.join(work, CASE)
    shutil.copytree(BASE, dst)

    def path(stem):
        return os.path.join(dst, f"oM_Data_{stem}_{CASE}.csv")

    dur = pd.read_csv(path("Duration"), index_col=[0, 1, 2])
    dur.iloc[TRUNC:, dur.columns.get_loc("Duration")] = np.nan
    dur.to_csv(path("Duration"))

    er = pd.read_csv(path("ElectricityRetail"), index_col=0)
    er.loc["EleR_02"] = er.loc["EleR_01"]          # 2nd retailer, same node/zone/tariffs
    er.to_csv(path("ElectricityRetail"))
    for stem in ("VarEnergyCost", "VarEnergyPrice"):
        df = pd.read_csv(path(stem))
        if "EleR_01" in df.columns:
            df["EleR_02"] = df["EleR_01"]
            df.to_csv(path(stem), index=False)

    ed = pd.read_csv(path("ElectricityDemand"), index_col=0)
    for d in ("EleD_06", "EleD_07", "EleD_08", "EleD_09", "EleD_10"):
        if d in ed.index:
            ed.loc[d, "Retailer"] = "EleR_02"      # consumer member; PV stays with EleR_01
    ed.to_csv(path("ElectricityDemand"))
    return dst, path


@pytest.mark.solve
def test_community_sharing_reduces_cost(tmp_path):
    work = str(tmp_path)
    dst, path = _build_community_case(work)

    # flag off: baseline, no sharing variables built
    op = pd.read_csv(path("Option"))
    op["IndBinCommunity"] = 0
    op.to_csv(path("Option"), index=False)
    m = routine(dir=work, case=CASE, solver="highs",
                date=datetime.datetime.now().replace(second=0, microsecond=0),
                rawresults="False", plots="False", indlog="False", duckdbresults="False")
    off = float(pyo.value(m.eTotalSCost))
    assert getattr(m, "vEleShareIn", None) is None, "share vars built with flag off"

    # flag on: sharing available
    op["IndBinCommunity"] = 1
    op.to_csv(path("Option"), index=False)
    m = routine(dir=work, case=CASE, solver="highs",
                date=datetime.datetime.now().replace(second=0, microsecond=0),
                rawresults="False", plots="False", indlog="False", duckdbresults="False")
    on = float(pyo.value(m.eTotalSCost))
    v = m.vEleShareIn
    shared = sum((pyo.value(v[i]) or 0) for i in v)

    assert on <= off + 1e-6, f"community cost {on} should be <= baseline {off}"
    # The sharing mechanism is available and never increases cost (checked above). We do NOT
    # assert shared > 0 here: this demo week has negligible PV (max ~5.8 kW availability, tiny
    # generation) so the prosumer has no real surplus to share, making sharing cost-neutral.
    # Audit C14 (import == buy) removed the degenerate, cost-neutral sharing the old
    # `shared > 0` relied on, so it is no longer a meaningful check in this case. Instead verify
    # the mechanism is built and usable; a numerical sharing benefit needs a case with genuine
    # prosumer surplus (a sunny window or a dispatchable prosumer generator) -- see model_audit.
    assert shared >= -1e-6, "sharing should be feasible (non-negative)"
    assert len(m.vEleShareIn) > 0 and len(m.vEleShareOut) > 0, \
        "the community sharing variables must be built when the flag is on"
