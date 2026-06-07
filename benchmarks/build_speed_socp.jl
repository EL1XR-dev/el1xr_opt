# Build-speed prototype (SOCP, JuMP/Julia) — branch-flow / DistFlow AC-OPF relaxation.
#
# Same model as benchmarks/build_speed_socp.py, so the JuMP build time is directly
# comparable to the Python tools (pyomo / pyoframe / cvxpy). JuMP expresses the
# rotated cone with its native RotatedSecondOrderCone set; the Python tools use
# quadratic constraints (Gurobi-recognised) or the CVXPY norm form - each the
# idiomatic SOCP for that tool. Times only the model BUILD (warm-up first).
#
# Setup (once): julia setup_jumpbench.jl   then add Clarabel:
#   julia --project=<jumpbench> -e 'import Pkg; Pkg.add("Clarabel")'
#
# Usage:
#   julia build_speed_socp.jl            # build-time sweep
#   julia build_speed_socp.jl check      # also solve small, print objective
#   julia build_speed_socp.jl N          # custom single size (N buses)
import Pkg
Pkg.activate(get(ENV, "JUMPBENCH_PROJECT", joinpath(homedir(), "jumpbench")); io=devnull)

using JuMP

# Clarabel (pure-Julia conic solver) is only needed for the correctness solve, not
# for the build sweep; load it if present.
const HAS_CLARABEL = try
    @eval import Clarabel
    true
catch
    false
end

const V0 = 1.0

_data(N) = (fill(0.01, N), fill(0.02, N), fill(0.02, N), fill(0.01, N))   # r, x, p, q

function build_model(N, data; do_solve=false)
    r, x, p, q = data
    m = Model()
    @variable(m, P[1:N])
    @variable(m, Q[1:N])
    @variable(m, l[1:N] >= 0)
    @variable(m, v[1:N] >= 0)
    vprev(j) = j == 1 ? V0 : v[j - 1]
    @constraint(m, pb[j = 1:N], P[j] - r[j] * l[j] - (j == N ? 0.0 : P[j + 1]) == p[j])
    @constraint(m, qb[j = 1:N], Q[j] - x[j] * l[j] - (j == N ? 0.0 : Q[j + 1]) == q[j])
    @constraint(m, vd[j = 1:N],
        v[j] == vprev(j) - 2 * (r[j] * P[j] + x[j] * Q[j]) + (r[j]^2 + x[j]^2) * l[j])
    # rotated cone: l*vprev >= P^2 + Q^2  <=>  2*l*(vprev/2) >= P^2+Q^2
    @constraint(m, soc[j = 1:N], [l[j], 0.5 * vprev(j), P[j], Q[j]] in RotatedSecondOrderCone())
    @objective(m, Min, sum(r[j] * l[j] for j in 1:N))
    if do_solve
        set_optimizer(m, Clarabel.Optimizer)
        set_silent(m)
        optimize!(m)
        return objective_value(m)
    end
    return nothing
end

function timed_build(N, data; repeats=2)
    best = Inf
    for _ in 1:repeats
        GC.gc()
        best = min(best, @elapsed build_model(N, data))
    end
    return best
end

function run_sweep(sizes)
    build_model(8, _data(8))   # warm up the JIT (untimed)
    println(rpad("builder", 12), lpad("N(buses)", 10), lpad("cons", 9), lpad("build_s", 10))
    for N in sizes
        println(rpad("jump", 12), lpad(N, 10), lpad(4 * N, 9), lpad(round(timed_build(N, _data(N)), digits=3), 10))
    end
end

function correctness()
    obj = build_model(8, _data(8); do_solve=true)
    println("\nCorrectness (small SOCP solve, JuMP+Clarabel):")
    println("  jump   obj=", round(obj, digits=8), "   (Python tools: ~0.00104456)")
end

nums = [parse(Int, a) for a in ARGS if occursin(r"^\d+$", a)]
run_sweep(length(nums) >= 1 ? [nums[1]] : [100, 1000, 10000])
"check" in ARGS && correctness()
