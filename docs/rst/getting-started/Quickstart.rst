Quickstart
==========

Run a minimal case
------------------
Python::

    from vy4e_optmodel import Model
    from vy4e_optmodel.data import load_case

    data = load_case("examples/case_small")
    m = Model.from_data(data)
    m.solve(solver="gurobi", time_limit=300)
    m.results.to_csv("results/")

CLI (if enabled)::

    vy4e-optmodel run --case examples/case_small --solver highs --out results/
