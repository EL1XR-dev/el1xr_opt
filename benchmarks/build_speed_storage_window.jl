# Build-speed prototype (JuMP/Julia) — the cycle-window storage balance.
#
# Same model as benchmarks/build_speed_storage_window.py, so the JuMP build time
# is directly comparable to the Python builders (pyomo-rule / LinearExpression /
# linopy / pyoframe). Times only the model BUILD, not the solve.
#
# Model (B cycles, C steps per cycle, G units):
#   inv[b,g] - inv[b-1,g] - sum_c (eta_c*cha[b,c,g] - dis[b,c,g]/eta_d) = 0   (b > 1)
#   inv[1,g]               - sum_c (eta_c*cha[1,c,g] - dis[1,c,g]/eta_d) = inv0[g]   (b = 1)
#
# Julia compiles on first use, so the first build is dominated by JIT. We warm up
# once (untimed) and report the best of two subsequent builds — the fair measure
# for iterative development.
#
# Setup (once): julia setup_jumpbench.jl   (installs JuMP+HiGHS in ~/jumpbench)
#
# Usage:
#   julia build_speed_storage_window.jl            # build-time sweep
#   julia build_speed_storage_window.jl check      # also solve small, check objective

# Use an isolated project so this does not depend on (or modify) the machine's
# default Julia environment. Set JUMPBENCH_PROJECT to override the location.
import Pkg
Pkg.activate(get(ENV, "JUMPBENCH_PROJECT", joinpath(homedir(), "jumpbench")); io=devnull)

using JuMP
using HiGHS

const ETA_C = 0.95
const ETA_D = 0.95

# Build the model; time this function only.
function build_model(B::Int, C::Int, G::Int, inv0::Vector{Float64}; with_obj::Bool=false)
    m = Model()
    @variable(m, inv[1:B, 1:G] >= 0)
    @variable(m, cha[1:B, 1:C, 1:G] >= 0)
    @variable(m, dis[1:B, 1:C, 1:G] >= 0)
    @constraint(m, bal[b = 1:B, g = 1:G],
        inv[b, g] - (b == 1 ? 0.0 : inv[b - 1, g])
        - sum(ETA_C * cha[b, c, g] - dis[b, c, g] / ETA_D for c in 1:C)
        == (b == 1 ? inv0[g] : 0.0))
    if with_obj
        @objective(m, Min, sum(cha) + sum(dis))
    end
    return m
end

function timed_build(B, C, G, inv0; repeats=2)
    best = Inf
    for _ in 1:repeats
        GC.gc()
        t = @elapsed build_model(B, C, G, inv0)
        best = min(best, t)
    end
    return best, B * G
end

function run_sweep(sizes)
    # warm up the JIT (compile the @constraint code for these types) — untimed.
    build_model(3, 4, 2, fill(0.5, 2))
    println(rpad("builder", 16), lpad("B", 6), lpad("C", 5), lpad("G", 5),
            lpad("cons", 9), lpad("build_s", 10))
    for (B, C, G) in sizes
        inv0 = fill(0.5, G)
        t, ncon = timed_build(B, C, G, inv0)
        println(rpad("jump", 16), lpad(B, 6), lpad(C, 5), lpad(G, 5),
                lpad(ncon, 9), lpad(round(t, digits=3), 10))
    end
end

function correctness()
    B, C, G = 6, 4, 2
    inv0 = fill(0.5, G)
    target = inv0 .+ 1.0
    m = build_model(B, C, G, inv0; with_obj=true)
    inv = m[:inv]
    @constraint(m, [g = 1:G], inv[B, g] == target[g])
    set_optimizer(m, HiGHS.Optimizer)
    set_silent(m)
    optimize!(m)
    println("\nCorrectness (small solve with forced charging):")
    println("  jump             obj=", round(objective_value(m), digits=6))
    println("  (Python builders give 2.105263)")
end

# Custom single size from args: `julia script.jl B C G` (plus optional `check`).
nums = [parse(Int, a) for a in ARGS if occursin(r"^\d+$", a)]
sizes = length(nums) >= 3 ? [(nums[1], nums[2], nums[3])] :
        [(7, 24, 10), (365, 24, 10), (365, 24, 50)]
run_sweep(sizes)
if "check" in ARGS
    correctness()
end
