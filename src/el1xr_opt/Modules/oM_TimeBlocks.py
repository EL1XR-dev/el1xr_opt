# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Resolutions declared per asset and flow, on top of the timeline of oM_Time.
#
# A case may carry an optional table oM_Data_Resolution_<case>.csv, one row per unit, with columns
# Output, Charge, Commitment, Reserve and Inventory holding a resolution specification such as 'uniform 2h'
# or 'calendar day'. A blank cell keeps the resolution of the load levels. The value of a declared
# flow is constant within each of its blocks.
#
# A declared flow has one variable per block. Its variable component (for example vEleTotalOutput)
# becomes a Pyomo Reference over every load level, in which each level points to the variable of
# its block (vEleTotalOutput_blk). Every constraint and every result reads the flow per level as
# before, and gets the block value. Constraints written per level stay correct: sums weighted by
# pDuration give block value x block duration, and a limit repeated on the levels of a block is
# redundant, not wrong.
#
# Flows that can be declared, and the variables that share one value per block:
#   Output      total output (vEleTotalOutput, vHydTotalOutput)
#   Charge      total charge: vEleTotalCharge for an electricity store or an electrolyser,
#               vHydTotalCharge for a hydrogen store or a fuel cell
#   Commitment  commitment, and the standby state of an electrolyser
#   Reserve     the FCR-D up, FCR-D down and FCR-N bids
#   Inventory   the inventory of an electricity or hydrogen store (vEleInventory, vHydInventory)
# The second-block output stays per level: the total output is the second block plus the
# activated reserve, and the activation changes every level. Start-ups, shut-downs and inventories
# stay per level as well.
#
# The limits of a declared output or charge follow the Parameter BlockLimit:
#   Level (default): the flow stays within its lower and upper limits at every level of its
#                    block, so a 2-h constant output is below the lowest availability inside the
#                    2 h. The limits are set to the block's highest lower and lowest upper limit.
#                    A must-take profile that changes inside a block cannot be met and is refused
#                    when the case is read.
#   Mean:            both limits are replaced by their duration-weighted mean over the block, as
#                    in Gao et al., Applied Energy 396 (2025) 126267.
#
# A declared inventory is the stored energy at the end of each of its blocks. The storage balance
# is written once per block: the inventory at the end of a block is the inventory at the end of
# the previous block plus the net charge over the block (Gao et al., Algorithm 2). The storage
# limits are those of the last level of the block. Inside a block the inventory is not tracked,
# so the store may go beyond its limits between two block ends, and the cost can be lower than
# with an inventory per load level. This replaces the cycle set by StorageType, which must then
# be one load level (StorageType Hourly or Daily).

import time

import numpy as np
from pyomo.core.base.reference import Reference
from pyomo.environ import Constraint, Var, value
from pyomo.repn import generate_standard_repn
from pyomo.core.expr.visitor import identify_variables

from .oM_Time import from_spec
from .utils.oM_Utils import log_time

FLOWS = ('Output', 'Charge', 'Commitment', 'Reserve', 'Inventory')
_BIDS = ['vEleFreqContReserveDisUpwardBid', 'vEleFreqContReserveDisDownwardBid', 'vEleFreqContReserveNorBid']
FLOW_VARS = {
    ('Ele', 'Output'): ['vEleTotalOutput'],
    ('Hyd', 'Output'): ['vHydTotalOutput'],
    ('Ele', 'Commitment'): ['vEleGenCommitment'],
    ('Hyd', 'Commitment'): ['vHydGenCommitment', 'vHydGenStandBy'],
    ('Ele', 'Reserve'): _BIDS,
    ('Hyd', 'Reserve'): _BIDS,
    ('Ele', 'Inventory'): ['vEleInventory'],
    ('Hyd', 'Inventory'): ['vHydInventory'],
}
_LIMITS = {'Output': ('MinPower', 'MaxPower'), 'Charge': ('MinCharge', 'MaxCharge'),
           'Inventory': ('MinStorage', 'MaxStorage')}
CAPACITY_RULES = ('Level', 'Mean')


def _units_with(model, sector, flow):
    """Units that have the given flow."""
    return {('Ele', 'Output'): model.eg, ('Hyd', 'Output'): model.hg,
            ('Ele', 'Charge'): model.eh | model.he, ('Hyd', 'Charge'): model.eh | model.he,
            ('Ele', 'Commitment'): model.egt, ('Hyd', 'Commitment'): model.hg,
            ('Ele', 'Reserve'): model.ege2h, ('Hyd', 'Reserve'): model.ege2h,
            ('Ele', 'Inventory'): model.egs, ('Hyd', 'Inventory'): model.hgs}[(sector, flow)]


def _flow_vars(model, sector, unit, flow):
    """Names of the variables that share one value per block for a declared flow."""
    if flow == 'Charge':
        return ['vEleTotalCharge'] if unit in model.eh else ['vHydTotalCharge']
    return FLOW_VARS[(sector, flow)]


def read_declarations(model, data_frames, parameters_dict):
    """Build the resolution of every declared flow and the first level of each of its blocks.

    Sets model.flow_res {(sector, unit, flow): Resolution} and model.block_start
    {(sector, unit, flow): {level: first level of its block}}. For an inventory, which is read at
    the end of its block, the map gives the last level of the block instead, and
    model.inventory_blocks {unit: {last level: (last level of the previous block or None, levels
    of the block)}} gives the levels each storage balance sums over. Units outside the base year
    are skipped, as the rest of the model skips them.
    """
    model.flow_res, model.block_start, model.inventory_blocks = {}, {}, {}

    rule = parameters_dict.get('pParBlockLimit', 'Level')
    rule = rule.strip().capitalize() if isinstance(rule, str) and rule.strip() else 'Level'
    if rule not in CAPACITY_RULES:
        raise ValueError(f"BlockLimit must be one of {CAPACITY_RULES}, got {rule!r}")
    parameters_dict['pParBlockLimit'] = rule

    df = data_frames.get('dfResolution')
    if df is None or df.empty or not model.time_res:
        return

    level = model.time_res['level']
    level_starts = set(level.starts.tolist())
    n_list = list(model.n)

    for unit, row in df.iterrows():
        sector = 'Ele' if unit in model.eg else 'Hyd' if unit in model.hg else None
        if sector is None:
            print(f'   Resolution: unit {unit!r} is not active in the base year and is skipped')
            continue
        for flow in FLOWS:
            spec = row.get(flow)
            if not isinstance(spec, str) or not spec.strip():
                continue
            if unit not in _units_with(model, sector, flow):
                raise ValueError(f'Resolution: unit {unit!r} has no {flow.lower()} flow')
            res = from_spec(model.timeline, 'horizon', spec, name=f'{unit} {flow}')
            if res.horizon != level.horizon or not set(res.starts.tolist()) <= level_starts:
                raise ValueError(f'Resolution {spec!r} of {unit} {flow} does not start its blocks '
                                 f'on load level boundaries')
            # first load level of each block, and the first level of the block of every level
            block_first, first = {}, {}
            for i, n in enumerate(n_list):
                b = int(res.block_of([level.starts[i]])[0])
                block_first.setdefault(b, n)
                first[n] = block_first[b]
            key = (sector, unit, flow)
            model.flow_res[key] = res
            if flow == 'Inventory':
                members = {}
                for n, n0 in first.items():
                    members.setdefault(n0, []).append(n)
                last = {n: members[n0][-1] for n, n0 in first.items()}
                ends = [levels[-1] for levels in members.values()]
                model.inventory_blocks[unit] = {levels[-1]: (ends[i - 1] if i else None, levels)
                                                for i, levels in enumerate(members.values())}
                first = last
            model.block_start[key] = first


def apply_capacity_rule(model, parameters_dict):
    """Apply BlockLimit to the lower and upper limits of each declared output and charge.

    Level: each limit becomes constant over the block, at its tightest value inside the block
           (highest lower limit, lowest upper limit). A block whose highest lower limit exceeds its
           lowest upper limit (a must-take profile that changes inside the block) is refused.
    Mean:  both limits become their duration-weighted mean over the block.

    The storage limits of a declared inventory become those of the last level of each block,
    whatever BlockLimit is: the inventory is the stored energy at that level. A declared
    inventory also needs a storage cycle of one load level.
    """
    rule = parameters_dict['pParBlockLimit']
    dur = parameters_dict['pDuration']
    for (sector, unit, flow), first in model.block_start.items():
        if flow not in _LIMITS:
            continue
        if flow == 'Inventory':
            cycle = int(parameters_dict[f'p{sector}CycleTimeStep'][unit])
            if cycle != 1:
                raise ValueError(f'{unit} inventory has a resolution and a storage cycle of {cycle} load levels '
                                 f'(StorageType {parameters_dict[f"p{sector}GenStorageType"][unit]}). Use one of '
                                 f'the two: the resolution needs StorageType Hourly or Daily.')
            for name in _LIMITS[flow]:
                limit = parameters_dict[f'p{sector}{name}']
                if unit in limit.columns:
                    for p, sc in model.ps:
                        for n, n_end in first.items():
                            limit.loc[(p, sc, n), unit] = limit.loc[(p, sc, n_end), unit]
            continue
        lower_name, upper_name = _LIMITS[flow]
        lower = parameters_dict[f'p{sector}{lower_name}']
        upper = parameters_dict[f'p{sector}{upper_name}']
        if unit not in upper.columns:
            continue
        for p, sc in model.ps:
            blocks = {}
            for n, n0 in first.items():
                blocks.setdefault(n0, []).append((p, sc, n))
            for members in blocks.values():
                hi = upper.loc[members, unit].to_numpy(dtype=float)
                lo = lower.loc[members, unit].to_numpy(dtype=float) if unit in lower.columns else np.zeros(len(members))
                if rule == 'Mean':
                    w = np.array([dur[m] for m in members], dtype=float)
                    if w.sum() == 0:
                        continue
                    new_hi, new_lo = float((hi * w).sum() / w.sum()), float((lo * w).sum() / w.sum())
                else:
                    if lo.max() > hi.min() + 1e-9:
                        raise ValueError(
                            f'{unit} {flow.lower()} cannot be constant over its block starting at {members[0][2]}: '
                            f'its lower limit reaches {lo.max():.6g} but its upper limit falls to {hi.min():.6g} '
                            f'inside the block (BlockLimit = Level). Use BlockLimit = Mean '
                            f'or a higher resolution for this flow.')
                    new_hi, new_lo = float(hi.min()), float(lo.max())
                upper.loc[members, unit] = new_hi
                if unit in lower.columns:
                    lower.loc[members, unit] = new_lo


def alias_block_variables(model, optmodel, indlog):
    """Give each declared flow one variable per block.

    Called right after the variables are declared and before any bound, fix or constraint. The
    variable component keeps its name and its index over every load level, as a Reference whose
    entries point to the block variables.
    """
    if not getattr(model, 'block_start', None):
        return
    start_time = time.time()
    first_of = {}                                   # variable name -> {unit: {level: first level}}
    for (sector, unit, flow), first in model.block_start.items():
        for name in _flow_vars(model, sector, unit, flow):
            first_of.setdefault(name, {})[unit] = first
    for name, units in first_of.items():
        old = getattr(optmodel, name)
        full = list(old.keys())
        target = {idx: (idx[0], idx[1], units[idx[3]][idx[2]], idx[3]) if idx[3] in units else idx
                  for idx in full}
        blocks = list(dict.fromkeys(target.values()))
        domain, start_value = old[full[0]].domain, old[full[0]].value
        doc = old.doc
        optmodel.del_component(old)
        raw = Var(blocks, within=domain, initialize=start_value, doc=f'{doc} (one per block)')
        setattr(optmodel, f'{name}_blk', raw)
        setattr(optmodel, name, Reference({idx: raw[target[idx]] for idx in full}, ctype=Var))
    log_time('--- Declaring the per-flow block variables:', start_time, ind_log=indlog)


def _row_key(con):
    """A comparable form of one linear constraint row, or None when the row is not linear.

    The key holds every variable of the row, fixed ones included: a fixed variable may be freed
    later (the solve fixes and frees binaries to read duals), so two rows that differ only in a
    fixed variable are not the same row.
    """
    repn = generate_standard_repn(con.body, compute_values=True)
    if repn.nonlinear_expr is not None or repn.quadratic_vars:
        return None
    coefs = {}
    for v, c in zip(repn.linear_vars, repn.linear_coefs):
        coefs[id(v)] = coefs.get(id(v), 0.0) + float(c)
    every_var = frozenset(id(v) for v in identify_variables(con.body, include_fixed=True))
    lb = None if con.lower is None else float(value(con.lower))
    ub = None if con.upper is None else float(value(con.upper))
    return float(repn.constant), frozenset(coefs.items()), every_var, lb, ub


def drop_repeated_rows(model, optmodel, indlog):
    """Write each constraint of a declared unit at its own resolution (Gao et al., Algorithm 1).

    A constraint row indexed by (period, scenario, level, unit) for a declared unit is compared
    with the row of the same unit at the start of each of the unit's blocks. When it has the same
    variables, coefficients, constant and bounds, it says nothing new and is deactivated: the row
    that remains holds for the whole block, and its dual is the shadow price of the block. Rows
    that also involve a variable per load level differ from level to level and stay. The solution
    and the cost do not change.
    """
    if not getattr(model, 'block_start', None):
        return 0
    start_time = time.time()
    firsts = {}                                     # unit -> list of {level: first level}
    for (sector, unit, flow), first in model.block_start.items():
        firsts.setdefault(unit, []).append(first)
    dropped = 0
    for con in optmodel.component_objects(Constraint, active=True, descend_into=True):
        if not con.is_indexed():
            continue
        for idx in list(con.keys()):
            if not (isinstance(idx, tuple) and len(idx) == 4 and idx[3] in firsts):
                continue
            row = con[idx]
            if not row.active:
                continue
            p, sc, n, g = idx
            starts = {first[n] for first in firsts[g] if n in first and first[n] != n}
            key = None
            for n0 in starts:
                ref = (p, sc, n0, g)
                if ref not in con or not con[ref].active:
                    continue
                key = _row_key(row) if key is None else key
                if key is not None and key == _row_key(con[ref]):
                    row.deactivate()
                    dropped += 1
                    break
    model.repeated_rows_dropped = dropped
    log_time(f'--- Dropping {dropped} constraint rows repeated within a block:', start_time, ind_log=indlog)
    return dropped
