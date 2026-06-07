"""Benchmark the parallel Benders subproblem solve.

Builds an N-scenario el1xr case (N blocks coupled by the shared investment) and
times el1xr_benders for a range of worker counts, checking every run reaches the
same optimum. Prints a small table: workers, wall-clock, speedup, objective.

Usage:
    python tests/_par_bench.py [N_SCENARIOS] [TRUNC] [SOLVER] [WORKERS_CSV]
e.g.
    python tests/_par_bench.py 8 168 gurobi 1,2,4,8
"""
import datetime
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))


def main():
    n_scen = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    trunc = int(sys.argv[2]) if len(sys.argv) > 2 else 168
    solver = sys.argv[3] if len(sys.argv) > 3 else "appsi_highs"
    workers = [int(w) for w in (sys.argv[4].split(",") if len(sys.argv) > 4 else ["1", "2", "4"])]

    import _make_2scenario as gen
    from el1xr_opt.Modules.oM_Sequence import build_model
    from el1xr_opt.Modules.oM_Decomposition import el1xr_benders, BendersConfig

    work = tempfile.mkdtemp(prefix="parbench_")
    gen.build(work, n_scenarios=n_scen, trunc=trunc)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    nblocks = len(list(build_model(work, "Home1", date).ps))
    print(f"# case: {n_scen} scenarios -> {nblocks} blocks, horizon {trunc}, solver {solver}",
          flush=True)
    print(f"{'workers':>8} {'wall_s':>10} {'speedup':>8} {'iters':>6} {'objective':>16}", flush=True)

    base = None
    for nw in workers:
        t0 = time.time()
        res = el1xr_benders(work, "Home1", date, solver=solver,
                            config=BendersConfig(max_iterations=80, relative_gap=1e-6, n_workers=nw))
        dt = time.time() - t0
        if base is None:
            base = dt
            base_obj = res["objective"]
        match = abs(res["objective"] - base_obj) / abs(base_obj) < 1e-4
        flag = "" if (res["converged"] and match) else "  <-- CHECK"
        print(f"{nw:>8} {dt:>10.1f} {base / dt:>8.2f} {res['iterations']:>6} "
              f"{res['objective']:>16.4f}{flag}", flush=True)


if __name__ == "__main__":
    main()
