"""IEEE 33-bus radial distribution test feeder (Baran & Wu, 1989).

The canonical DistFlow benchmark. Buses 1..33 (1 = substation/slack), 32 radial
branches. Standard published base-case result: total active loss ~202.7 kW and
minimum bus voltage ~0.913 pu (bus 18), used here to validate ``oM_ACOPF``.

Per unit: Sbase = 1 MVA, Vbase = 12.66 kV -> Zbase = 12.66^2 / 1 = 160.2756 ohm.
"""
import pandas as pd

SBASE_MVA = 1.0
VBASE_KV = 12.66
ZBASE = VBASE_KV ** 2 / SBASE_MVA          # 160.2756 ohm

# branch: (from, to, R_ohm, X_ohm)
_BRANCHES = [
    (1, 2, 0.0922, 0.0470), (2, 3, 0.4930, 0.2511), (3, 4, 0.3660, 0.1864),
    (4, 5, 0.3811, 0.1941), (5, 6, 0.8190, 0.7070), (6, 7, 0.1872, 0.6188),
    (7, 8, 0.7114, 0.2351), (8, 9, 1.0300, 0.7400), (9, 10, 1.0440, 0.7400),
    (10, 11, 0.1966, 0.0650), (11, 12, 0.3744, 0.1238), (12, 13, 1.4680, 1.1550),
    (13, 14, 0.5416, 0.7129), (14, 15, 0.5910, 0.5260), (15, 16, 0.7463, 0.5450),
    (16, 17, 1.2890, 1.7210), (17, 18, 0.7320, 0.5740), (2, 19, 0.1640, 0.1565),
    (19, 20, 1.5042, 1.3554), (20, 21, 0.4095, 0.4784), (21, 22, 0.7089, 0.9373),
    (3, 23, 0.4512, 0.3083), (23, 24, 0.8980, 0.7091), (24, 25, 0.8960, 0.7011),
    (6, 26, 0.2030, 0.1034), (26, 27, 0.2842, 0.1447), (27, 28, 1.0590, 0.9337),
    (28, 29, 0.8042, 0.7006), (29, 30, 0.5075, 0.2585), (30, 31, 0.9744, 0.9630),
    (31, 32, 0.3105, 0.3619), (32, 33, 0.3410, 0.5302),
]

# load: bus -> (P_kW, Q_kVar); bus 1 is the slack (no load)
_LOADS = {
    2: (100, 60), 3: (90, 40), 4: (120, 80), 5: (60, 30), 6: (60, 20),
    7: (200, 100), 8: (200, 100), 9: (60, 20), 10: (60, 20), 11: (45, 30),
    12: (60, 35), 13: (60, 35), 14: (120, 80), 15: (60, 10), 16: (60, 20),
    17: (60, 20), 18: (90, 40), 19: (90, 40), 20: (90, 40), 21: (90, 40),
    22: (90, 40), 23: (90, 50), 24: (420, 200), 25: (420, 200), 26: (60, 25),
    27: (60, 25), 28: (60, 20), 29: (120, 70), 30: (200, 600), 31: (150, 70),
    32: (210, 100), 33: (60, 40),
}

SLACK = "B1"
PUBLISHED_LOSS_MW = 0.2027     # ~202.7 kW base-case active loss
PUBLISHED_VMIN = 0.913         # ~0.913 pu at bus 18


def network_df():
    """IEEE 33-bus branches as an el1xr ElectricityNetwork-format DataFrame
    (per-unit Resistance/Reactance, (InitialNode, FinalNode, Circuit) index)."""
    rows, idx = [], []
    for (f, t, r, x) in _BRANCHES:
        idx.append((f"B{f}", f"B{t}", "c1"))
        rows.append({"Resistance": r / ZBASE, "Reactance": x / ZBASE, "TTC": 10.0})
    return pd.DataFrame(rows, index=pd.MultiIndex.from_tuples(idx))


def loads_pu():
    """Per-unit net loads Pd, Qd keyed by bus name."""
    Pd = {f"B{b}": p / 1000.0 / SBASE_MVA for b, (p, q) in _LOADS.items()}
    Qd = {f"B{b}": q / 1000.0 / SBASE_MVA for b, (p, q) in _LOADS.items()}
    return Pd, Qd
