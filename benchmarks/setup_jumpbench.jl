# One-time setup for the JuMP build-speed benchmark.
#
# Installs JuMP + HiGHS into an isolated Julia project (default: ~/jumpbench, or
# set JUMPBENCH_PROJECT) so the benchmark does not depend on - or modify - the
# machine's default Julia environment. Run once:
#
#   julia setup_jumpbench.jl
#
# then run the benchmark:
#
#   julia build_speed_storage_window.jl check
import Pkg
proj = get(ENV, "JUMPBENCH_PROJECT", joinpath(homedir(), "jumpbench"))
Pkg.activate(proj)
println("activating isolated project at ", proj)
Pkg.add(["JuMP", "HiGHS"])
Pkg.precompile()
import JuMP, HiGHS
println("OK: JuMP and HiGHS installed in ", proj)
