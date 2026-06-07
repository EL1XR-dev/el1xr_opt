# Build-speed prototype (SDP, JuMP/Julia) — semidefinite relaxation, AC-OPF style.
#
# Same model as benchmarks/build_speed_sdp.py, so the JuMP build time is directly
# comparable to CVXPY (the only Python tool that can express an SDP). PSD matrix
# variable W >= 0, fixed diagonal, linear objective trace(C W) with C the ring
# (cycle) adjacency — the canonical max-cut / AC-OPF-relaxation SDP structure.
#
# Setup (once): the jumpbench project plus Clarabel (a pure-Julia SDP-capable
# conic solver):  julia --project=<jumpbench> -e 'import Pkg; Pkg.add("Clarabel")'
#
# Usage:
#   julia build_speed_sdp.jl            # build-time sweep
#   julia build_speed_sdp.jl check      # also solve small, print objective
#   julia build_speed_sdp.jl N          # custom single dimension n
import Pkg
Pkg.activate(get(ENV, "JUMPBENCH_PROJECT", joinpath(homedir(), "jumpbench")); io=devnull)

using JuMP
const HAS_CLARABEL = try
    @eval import Clarabel
    true
catch
    false
end

function cost_matrix(n)   # ring (cycle C_n) adjacency
    C = zeros(n, n)
    for k in 1:n
        j = k == n ? 1 : k + 1
        C[k, j] = 1.0
        C[j, k] = 1.0
    end
    return C
end

function build_model(n; do_solve=false)
    C = cost_matrix(n)
    m = Model()
    @variable(m, W[1:n, 1:n], PSD)
    @constraint(m, diagfix[k = 1:n], W[k, k] == 1.0)
    @objective(m, Min, sum(C[i, j] * W[i, j] for i in 1:n, j in 1:n))
    if do_solve
        set_optimizer(m, Clarabel.Optimizer)
        set_silent(m)
        optimize!(m)
        return objective_value(m)
    end
    return nothing
end

function timed_build(n; repeats=2)
    best = Inf
    for _ in 1:repeats
        GC.gc()
        best = min(best, @elapsed build_model(n))
    end
    return best
end

function run_sweep(sizes)
    build_model(8)   # warm up the JIT (untimed)
    println(rpad("builder", 10), lpad("n(dim)", 7), lpad("vars~", 9), lpad("build_s", 10))
    for n in sizes
        println(rpad("jump", 10), lpad(n, 7), lpad(n * (n + 1) ÷ 2, 9),
                lpad(round(timed_build(n), digits=3), 10))
    end
end

function correctness()
    obj = build_model(10; do_solve=true)
    println("\nCorrectness (small SDP solve, n=10, JuMP+Clarabel):")
    println("  jump   obj=", round(obj, digits=8), "   (CVXPY: ~-20.0)")
end

nums = [parse(Int, a) for a in ARGS if occursin(r"^\d+$", a)]
run_sweep(length(nums) >= 1 ? [nums[1]] : [50, 100, 200])
"check" in ARGS && correctness()
