# This script is part of the el1xr_opt package.
import shutil
import time

# def log_time(message, start_time, total_width=70):
#     """
#     Prints a formatted log line with aligned seconds column (no external packages).
#     - message: e.g. "--- Declaring the ObjFunc components:"
#     - start_time: time.time() when the step started
#     - total_width: column width before printing seconds
#     """
#     elapsed = round(time.time() - start_time, 1)  # one decimal precision
#     level = message.count('-')  # count hyphens to infer hierarchy
#
#     # Indentation and style (adjust as you like)
#     if level >= 3:
#         prefix = "   "  # deeper indentation for '---'
#     elif level == 2:
#         prefix = "  "
#     else:
#         prefix = ""
#
#     # Create aligned output
#     print(f"{prefix}{message:<{total_width}}{elapsed:>6} seconds")

def log_time(message: str,
             start_time: float,
             unit: str = "seconds",
             ind_log: str = 'False',
             decimals: int = 1,
             right_margin: int = 1,
             anchor_col: int | None = None,
             ensure_colon: bool = True):
    """
    Print `message` with elapsed time aligned to the right.
    - anchor_col: if given, align so the *end* of the time string lands at this column.
                  Otherwise align to the terminal's right edge.
    - right_margin: spaces to keep between the time string and the right edge (ignored if anchor_col is set).
    """
    # elapsed time string
    elapsed = time.time() - start_time
    fmt = f"{{:.{decimals}f}}" if decimals > 0 else "{:.0f}"
    time_str = f"{fmt.format(elapsed)} {unit}"

    # normalize message end
    msg = message.rstrip()
    if ensure_colon and not msg.endswith(":"):
        msg += ":"

    # terminal width (fallback to 80 if unknown)
    term_width = shutil.get_terminal_size((90, 24)).columns

    # where should the time end?
    if anchor_col is not None:
        end_col = anchor_col
    else:
        end_col = term_width - right_margin

    # compute spaces; +1 for a space before time_str
    spaces = end_col - len(msg) - len(time_str) - 1
    if ind_log == 'True':
        if spaces < 1:
            # too long; just print compactly
            print(f"{msg} {time_str}")
        else:
            print(f"{msg}{' ' * spaces} {time_str}")

def _update_parameters(df, dict, factor, indices, factoring_indices, data_key, prefix):
    for idx in indices:
        if idx in factoring_indices:
            dict[f'{prefix}{idx}'] = df[data_key][idx] * factor
        else:
            dict[f'{prefix}{idx}'] = df[data_key][idx]

def _psdn_init(m, dict):
    # (p, sc, d, n) with d = day(n)
    for p, sc, n in m.psn:
        d = dict[n]
        yield (p, sc, d, n)

def _psmd_init(m, dict):
    # (p, sc, m, d) with m = month(d)
    for p, sc, d in m.psd:
        mth = dict[d]
        yield (p, sc, mth, d)

def _psmdn_init(m, dict_n2d, dict_d2m):
    # (p, sc, m, d, n) with m = month(d), d = day(n)
    for p, sc, n in m.psn:
        d = dict_n2d[n]
        mth = dict_d2m[d]
        yield (p, sc, mth, d, n)

def _cartesian_4_psm(m, extra_set):
    for (p, sc, mo) in m.psm:
        for x in extra_set:
            yield (p, sc, mo, x)

def _cartesian_4_psd(m, extra_set):
    for (p, sc, d) in m.psd:
        for x in extra_set:
            yield (p, sc, d, x)

def _extend_psdn_filtered(m, link_set_name, extra_set, dimen=5):
    """
    Build (p, sc, d, n, x) from psdn and extra_set,
    keeping only those with (p, sc, n, x) in link_set.
    """
    psdn = m.psdn
    link = set(getattr(m, link_set_name))  # e.g., psner: (p, sc, n, er)
    for (p, sc, d, n) in psdn:
        for x in extra_set:
            if (p, sc, n, x) in link:
                yield (p, sc, d, n, x)

def _apply_mask_and_set_zero(pdict, key, sector_key, threshold):
    selected_rows = pdict[key].loc[:, sector_key]
    mask = selected_rows < threshold
    pdict[key].loc[:,sector_key] = selected_rows.where(~mask, 0.0)