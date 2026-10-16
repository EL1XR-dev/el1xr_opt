# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Resolutions declared per asset and flow, on top of the timeline of oM_Time.
#
# A case may carry an optional table oM_Data_Resolution_<case>.csv, one row per unit, with columns
# Output and Charge holding a resolution specification such as 'uniform 2h' or 'calendar day'. A
# blank cell keeps the resolution of the load levels. The value of a declared flow is constant
# within each of its blocks.
#
# Phase 2a: the flow keeps one variable per load level, and the values inside a block are tied
# to the first level of the block. Every constraint written per level then stays correct: sums
# weighted by pDuration give block value x block duration, and a limit repeated on the levels of
# a block is redundant, not wrong.
#
# The limits of a flow at a lower resolution than the load levels are chosen per case with the
# Parameter BlockLimit:
#   Level (default): the flow stays within its lower and upper limits at every level of its
#                    block, so a 2-h constant output is below the lowest availability inside the
#                    2 h. A must-take profile that changes inside a block cannot be met and is
#                    refused when the case is read.
#   Mean:            both limits are replaced by their duration-weighted mean over the block, as
#                    in Gao et al., Applied Energy 396 (2025) 126267.

import time

import numpy as np
from pyomo.environ import Constraint

from .oM_Time import from_spec
from .utils.oM_Utils import log_time

FLOWS = ('Output', 'Charge')
_VARS = {('Ele', 'Output'): 'vEleTotalOutput', ('Ele', 'Charge'): 'vEleTotalCharge',
         ('Hyd', 'Output'): 'vHydTotalOutput', ('Hyd', 'Charge'): 'vHydTotalCharge'}
_LIMITS = {'Output': ('MinPower', 'MaxPower'), 'Charge': ('MinCharge', 'MaxCharge')}
CAPACITY_RULES = ('Level', 'Mean')


def read_declarations(model, data_frames, parameters_dict):
    """Build the resolution of every declared flow and the first level of each of its blocks.

    Sets model.flow_res {(sector, unit, flow): Resolution} and model.block_start
    {(sector, unit, flow): {level: first level of its block}}. Units outside the base year are
    skipped, as the rest of the model skips them.
    """
    model.flow_res, model.block_start = {}, {}

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
    charging = {'Ele': set(model.eh), 'Hyd': set(model.he)}

    for unit, row in df.iterrows():
        sector = 'Ele' if unit in model.eg else 'Hyd' if unit in model.hg else None
        if sector is None:
            print(f'   Resolution: unit {unit!r} is not active in the base year and is skipped')
            continue
        for flow in FLOWS:
            spec = row.get(flow)
            if not isinstance(spec, str) or not spec.strip():
                continue
            if flow == 'Charge' and unit not in charging[sector]:
                raise ValueError(f'Resolution: unit {unit!r} has no charge flow')
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
            model.block_start[key] = first


def apply_capacity_rule(model, parameters_dict):
    """Apply BlockLimit to the lower and upper limits of each declared flow.

    Mean:  both limits are replaced by their duration-weighted mean over each block.
    Level: the limits stay per level; a block whose highest lower limit exceeds its lowest upper
           limit (a must-take profile that changes inside the block) cannot hold a constant
           value, and is refused here with the levels concerned.
    """
    rule = parameters_dict['pParBlockLimit']
    dur = parameters_dict['pDuration']
    for (sector, unit, flow), first in model.block_start.items():
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
                    if w.sum() > 0:
                        upper.loc[members, unit] = float((hi * w).sum() / w.sum())
                        if unit in lower.columns:
                            lower.loc[members, unit] = float((lo * w).sum() / w.sum())
                elif lo.max() > hi.min() + 1e-9:
                    raise ValueError(
                        f'{unit} {flow.lower()} cannot be constant over its block starting at {members[0][2]}: '
                        f'its lower limit reaches {lo.max():.6g} but its upper limit falls to {hi.min():.6g} '
                        f'inside the block (BlockLimit = Level). Use BlockLimit = Mean '
                        f'or a higher resolution for this flow.')


def create_time_blocks(model, optmodel, indlog):
    """Tie the value of each declared flow to the first level of its block."""
    if not getattr(model, 'block_start', None):
        return model
    start_time = time.time()
    for (sector, unit, flow), first in model.block_start.items():
        var = getattr(optmodel, _VARS[(sector, flow)])
        index = [(p, sc, n, unit) for p, sc in model.ps for n in first
                 if first[n] != n and (p, sc, n, unit) in var]

        def eFlowBlock(optmodel, p, sc, n, g, _var=var, _first=first):
            return _var[p, sc, n, g] == _var[p, sc, _first[n], g]
        name = f'e{sector}{flow}Block_{unit}'
        optmodel.__setattr__(name, Constraint(index, rule=eFlowBlock,
                             doc=f'{unit} {flow.lower()} constant within each block of {model.flow_res[(sector, unit, flow)].name}'))
    log_time('--- Declaring the per-flow time blocks:', start_time, ind_log=indlog)
    return model
