# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Time structure for el1xr_opt: a timeline counted in base units, resolutions as ordered lists of
# time blocks, and the overlap between any two resolutions.
#
# Method: Gao, Gazzani, Tejada-Arango, Soares Siqueira, Wang, Gibescu, Morales-Espana, "Fully
# flexible temporal resolution for energy system optimization", Applied Energy 396 (2025) 126267.
# Every variable, parameter and constraint series may have its own resolution. A variable is a rate,
# constant within its block. A constraint on instantaneous values uses the finest common resolution
# of its variables (their Algorithm 1); a constraint on accumulated values may use the coarsest
# (Algorithm 2). Variables enter a constraint weighted by their overlap with its blocks (Algorithm 3).
#
# This module knows nothing about Pyomo. Block positions are 0-based base units, and a block covers
# [start, end), so its length is end - start.

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BASE_UNIT_MINUTES = 1


@dataclass(frozen=True)
class RepPeriod:
    """A stretch of contiguous time. A case without representative periods has one, of weight 1."""
    name: str
    start: pd.Timestamp     # clock time at the start of the first base unit
    length: int             # number of base units
    weight: float = 1.0     # times the period is repeated to stand for the whole horizon


@dataclass
class Timeline:
    """Base unit and representative periods. The base unit is a ruler: no variable exists at it
    unless a resolution asks for it."""
    periods: list
    unit_minutes: int = BASE_UNIT_MINUTES
    _by_name: dict = field(init=False, repr=False)

    def __post_init__(self):
        self._by_name = {k.name: k for k in self.periods}
        if len(self._by_name) != len(self.periods):
            raise ValueError('representative period names must be unique')

    def period(self, name):
        return self._by_name[name]

    def units(self, minutes):
        """Convert minutes to base units; the result must be a whole number."""
        u = minutes / self.unit_minutes
        if abs(u - round(u)) > 1e-9:
            raise ValueError(f'{minutes} min is not a whole number of {self.unit_minutes}-min base units')
        return int(round(u))

    def hours(self, units):
        return np.asarray(units) * self.unit_minutes / 60.0

    def timestamps(self, period, units):
        """Clock time at the start of the given base units of a period."""
        k = self.period(period)
        return k.start + pd.to_timedelta(np.asarray(units) * self.unit_minutes, unit='min')


@dataclass(frozen=True)
class Resolution:
    """An ordered list of blocks [start, end) that covers one representative period exactly."""
    name: str
    period: str
    starts: np.ndarray
    ends: np.ndarray

    def __post_init__(self):
        s, e = np.asarray(self.starts, dtype=np.int64), np.asarray(self.ends, dtype=np.int64)
        object.__setattr__(self, 'starts', s)
        object.__setattr__(self, 'ends', e)
        if len(s) == 0 or s[0] != 0 or np.any(e <= s) or np.any(s[1:] != e[:-1]):
            raise ValueError(f'resolution {self.name!r}: blocks must be non-empty, contiguous and start at 0')

    @property
    def size(self):
        return len(self.starts)

    @property
    def lengths(self):
        return self.ends - self.starts

    @property
    def horizon(self):
        return int(self.ends[-1])

    def block_of(self, units):
        """Index of the block holding each base unit."""
        return np.searchsorted(self.ends, np.asarray(units), side='right')


def _check_cover(timeline, period, res):
    if res.horizon != timeline.period(period).length:
        raise ValueError(f'resolution {res.name!r} covers {res.horizon} base units, '
                         f'period {period!r} has {timeline.period(period).length}')
    return res


def from_lengths(timeline, period, lengths, name):
    """Resolution from a list of block lengths in base units."""
    ends = np.cumsum(np.asarray(lengths, dtype=np.int64))
    starts = np.concatenate([[0], ends[:-1]])
    return _check_cover(timeline, period, Resolution(name, period, starts, ends))


def uniform(timeline, period, minutes, name=None):
    """Blocks of equal length. A last block that does not fit is shortened."""
    step = timeline.units(minutes)
    length = timeline.period(period).length
    starts = np.arange(0, length, step)
    ends = np.minimum(starts + step, length)
    return Resolution(name or f'uniform {minutes}min', period, starts, ends)


def calendar(timeline, period, unit, name=None):
    """Blocks that follow the clock: 'hour', 'day' or 'month'. A period that does not start on a
    boundary gets a shorter first block."""
    length = timeline.period(period).length
    ts = timeline.timestamps(period, np.arange(length))
    key = {'hour': ts.floor('h'), 'day': ts.normalize(), 'month': ts.to_period('M').to_timestamp()}[unit]
    change = np.flatnonzero(np.asarray(key[1:] != key[:-1])) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [length]])
    return Resolution(name or f'calendar {unit}', period, starts, ends)


def from_spec(timeline, period, spec, name=None):
    """Resolution from a short specification: 'uniform 15min', 'uniform 1h', 'calendar day',
    'explicit 60,60,120' (block lengths in minutes)."""
    kind, _, arg = spec.strip().partition(' ')
    arg = arg.strip()
    if kind == 'uniform':
        minutes = float(arg[:-3]) if arg.endswith('min') else float(arg[:-1]) * 60 if arg.endswith('h') else None
        if minutes is None:
            raise ValueError(f'uniform resolution needs a length in min or h, got {arg!r}')
        return uniform(timeline, period, minutes, name or spec)
    if kind == 'calendar':
        return calendar(timeline, period, arg, name or spec)
    if kind == 'explicit':
        lengths = [timeline.units(float(x)) for x in arg.split(',')]
        return from_lengths(timeline, period, lengths, name or spec)
    raise ValueError(f'unknown resolution specification {spec!r}')


def overlap(a, b):
    """Overlap of every pair of blocks of two resolutions of the same period (Gao et al.,
    Algorithm 3). Returns a DataFrame with columns a, b (block indices) and units (> 0)."""
    if a.period != b.period or a.horizon != b.horizon:
        raise ValueError('overlap needs two resolutions of the same period')
    cuts = np.union1d(np.concatenate([a.starts, a.ends]), np.concatenate([b.starts, b.ends]))
    lo, hi = cuts[:-1], cuts[1:]
    df = pd.DataFrame({'a': a.block_of(lo), 'b': b.block_of(lo), 'units': hi - lo})
    return df.groupby(['a', 'b'], as_index=False, sort=True)['units'].sum()


def finest_common(resolutions, name='finest common'):
    """Gao et al., Algorithm 1: a new block starts whenever a block of any input starts. For
    constraints on instantaneous values (power balances, capacity limits)."""
    first = resolutions[0]
    starts = np.unique(np.concatenate([r.starts for r in resolutions]))
    ends = np.concatenate([starts[1:], [first.horizon]])
    return Resolution(name, first.period, starts, ends)


def coarsest_common(resolutions, name='coarsest common'):
    """Gao et al., Algorithm 2: each block runs to the latest end among the input blocks that hold
    its start. For constraints on accumulated values (energy contents, conversion balances)."""
    first = resolutions[0]
    starts, ends, s = [], [], 0
    while s < first.horizon:
        e = max(int(r.ends[r.block_of([s])[0]]) for r in resolutions)
        starts.append(s)
        ends.append(e)
        s = e
    return Resolution(name, first.period, starts, ends)


def resample(values, a, b, kind):
    """Map a series given per block of resolution a onto resolution b.

    kind='rate'   (price, power, per-unit profile): duration-weighted mean over each block of b.
    kind='amount' (energy or volume per block): split in proportion to the overlap and summed.
    """
    values = np.asarray(values, dtype=float)
    if len(values) != a.size:
        raise ValueError(f'{len(values)} values for {a.size} blocks of {a.name!r}')
    ov = overlap(a, b)
    if kind == 'rate':
        w = ov['units'].to_numpy()
        num = np.bincount(ov['b'], weights=values[ov['a']] * w, minlength=b.size)
        return num / b.lengths
    if kind == 'amount':
        share = ov['units'].to_numpy() / a.lengths[ov['a']]
        return np.bincount(ov['b'], weights=values[ov['a']] * share, minlength=b.size)
    raise ValueError(f"kind must be 'rate' or 'amount', got {kind!r}")
