import pytest


@pytest.fixture
def deterministic_highs(monkeypatch):
    """Force HiGHS to solve single-threaded to a zero MIP gap.

    The golden-cost tests assert an exact objective to a tight tolerance. A parallel
    MILP returns a different within-the-gap incumbent depending on the thread count
    and the HiGHS version, so those assertions flake from one machine to another. With
    this fixture the solve is deterministic and returns the proven optimum, which is
    reproducible. See the EL1XR_HIGHS_DETERMINISTIC switch in oM_ProblemSolving.
    """
    monkeypatch.setenv("EL1XR_HIGHS_DETERMINISTIC", "1")
