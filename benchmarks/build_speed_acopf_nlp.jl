# Build-speed prototype (NLP, JuMP/Julia) — exact AC optimal power flow, polar form.
#
# Same model as benchmarks/build_speed_acopf_nlp.py, so JuMP build time is directly
# comparable to Pyomo — the head-to-head for the AC-OPF backbone (the two tools
# that can express general non-convex NLP). Times the BUILD; solves a small case
# with Ipopt for the correctness check.
#
# Setup (once), into the jumpbench project:  Pkg.add("Ipopt")
#
# Usage:
#   julia build_speed_acopf_nlp.jl            # build-time sweep
#   julia build_speed_acopf_nlp.jl check      # also solve small, print objective
#   julia build_speed_acopf_nlp.jl N          # custom single size (N lines)
import Pkg
Pkg.activate(get(ENV, "JUMPBENCH_PROJECT", joinpath(homedir(), "jumpbench")); io=devnull)

using JuMP
const HAS_IPOPT = try
    @eval import Ipopt
    true
catch
    false
end

function _data(N)
    r = fill(0.01, N); x = fill(0.03, N)
    g = r ./ (r .^ 2 .+ x .^ 2)
    b = -x ./ (r .^ 2 .+ x .^ 2)
    Pd = vcat(0.0, fill(0.10, N))            # bus 1 = slack (no load)
    Qd = vcat(0.0, fill(0.05, N))
    cost = [1.0 + 0.05 * (i - 1) for i in 1:(N + 1)]
    return g, b, Pd, Qd, cost
end

function ybus_feeder(g, b, N)
    n = N + 1
    Gd = zeros(n); Bd = zeros(n)
    for k in 1:N                              # line k between bus k and k+1
        Gd[k] += g[k]; Gd[k + 1] += g[k]
        Bd[k] += b[k]; Bd[k + 1] += b[k]
    end
    nbradm(i, j) = (k = min(i, j); (-g[k], -b[k]))
    return Gd, Bd, nbradm
end

function build_model(N, data; do_solve=false)
    g, b, Pd, Qd, cost = data
    n = N + 1
    Gd, Bd, nbradm = ybus_feeder(g, b, N)
    nbrs(i) = filter(j -> 1 <= j <= n, (i - 1, i + 1))
    m = Model()
    @variable(m, 0.9 <= V[1:n] <= 1.1, start = 1.0)
    @variable(m, th[1:n], start = 0.0)
    @variable(m, 0 <= Pg[1:n] <= 5)
    @variable(m, -3 <= Qg[1:n] <= 3)
    fix(V[1], 1.0; force = true)
    fix(th[1], 0.0; force = true)
    @constraint(m, pb[i = 1:n],
        Pg[i] - Pd[i] == V[i]^2 * Gd[i] +
        sum(V[i] * V[j] * (nbradm(i, j)[1] * cos(th[i] - th[j]) + nbradm(i, j)[2] * sin(th[i] - th[j]))
            for j in nbrs(i)))
    @constraint(m, qb[i = 1:n],
        Qg[i] - Qd[i] == -V[i]^2 * Bd[i] +
        sum(V[i] * V[j] * (nbradm(i, j)[1] * sin(th[i] - th[j]) - nbradm(i, j)[2] * cos(th[i] - th[j]))
            for j in nbrs(i)))
    @objective(m, Min, sum(cost[i] * Pg[i] for i in 1:n))
    if do_solve
        set_optimizer(m, Ipopt.Optimizer)
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
    build_model(8, _data(8))   # warm up JIT
    println(rpad("builder", 10), lpad("N lines", 8), lpad("cons", 8), lpad("build_s", 10))
    for N in sizes
        println(rpad("jump", 10), lpad(N, 8), lpad(2 * (N + 1), 8),
                lpad(round(timed_build(N, _data(N)), digits=3), 10))
    end
end

function correctness()
    obj = build_model(8, _data(8); do_solve=true)
    println("\nCorrectness (small AC OPF NLP solve, N=8, JuMP+Ipopt):")
    println("  jump   obj=", obj, "   (Pyomo should match)")
end

nums = [parse(Int, a) for a in ARGS if occursin(r"^\d+$", a)]
run_sweep(length(nums) >= 1 ? [nums[1]] : [100, 1000, 10000])
"check" in ARGS && correctness()
