"""
Shared preparation for the conversion-regret plot, used by both plot backends.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import numpy as np


def _regret_units(objective):
    """Return (divisor, suffix, axis label fragment) for the objective's natural units."""
    if objective == "maxSpending":
        # The first year's spending, matching the spending pages and the netSpending goal
        # (see _regret_objective_value). Hundreds or thousands of dollars per year, so
        # plain dollars read better than $k.
        return 1.0, "", "in first-year net spending ($/yr)"
    return 1000.0, "k", "in final after-tax bequest ($k)"


def prepare_regret_plot(grid, mean_regret, lo_band, hi_band, summary, objective):
    """
    Turn a sweep summary into the primitives both plot backends draw.

    Returns a dict with the curve in display units, the dense PCHIP interpolation used
    between solved points, the axis ranges, and every annotation that survived the
    robustness screening. Anything the summary says is unresolvable comes back as None so
    that neither backend can draw a number the data does not support.
    """
    div, suffix, ylabel = _regret_units(objective)
    x = np.asarray(grid, dtype=float) / 1000.0          # committed conversion, always $k
    y = np.asarray(mean_regret, dtype=float) / div
    lo = None if lo_band is None else np.asarray(lo_band, dtype=float) / div
    hi = None if hi_band is None else np.asarray(hi_band, dtype=float) / div

    # Dense monotone interpolation between the points actually solved. Markers are drawn
    # at the solved points as well, so a 7-point preset can never pass for a 19-point run.
    xd = yd = None
    good = np.isfinite(y)
    if good.sum() >= 2:
        try:
            from scipy.interpolate import PchipInterpolator

            interp = PchipInterpolator(x[good], y[good])
            xd = np.linspace(float(x[good][0]), float(x[good][-1]), 200)
            yd = interp(xd)
        except Exception:
            xd = yd = None

    by_grid = summary.get("regret_by_grid", [])
    ninf = np.array([g.get("n_infeasible", 0) or 0 for g in by_grid], dtype=int)
    onset = None
    if ninf.size and ninf.max() > 0:
        onset = {"x": float(x[int(np.argmax(ninf > 0))]), "n": int(ninf.max())}

    # Bootstrap interval on the mean itself. This is the band that visibly tightens as
    # more scenarios are swept, so it is what tells the reader a cheap preset is cheap.
    mlo = mhi = None
    mci = summary.get("mean_ci_by_grid")
    if mci:
        mlo = np.array([np.nan if e["p10"] is None else e["p10"] / div for e in mci], dtype=float)
        mhi = np.array([np.nan if e["p90"] is None else e["p90"] / div for e in mci], dtype=float)

    floor = float(summary.get("resolution_floor", 0.0) or 0.0) / div
    resolvable = bool(summary.get("valley_resolvable", True))

    valley = None
    if resolvable and summary.get("valley") and summary["valley"].get("mean_regret") is not None:
        ci = summary.get("valley_ci")
        valley = {
            "x": float(summary["valley"]["x"]) / 1000.0,
            "y": float(summary["valley"]["mean_regret"]) / div,
            "lo": None if ci is None else float(ci["p10"]) / 1000.0,
            "hi": None if ci is None else float(ci["p90"]) / 1000.0,
        }

    band = None
    if resolvable and summary.get("commit_band"):
        cb = summary["commit_band"]
        band = {"lo": float(cb["x_lo"]) / 1000.0, "hi": float(cb["x_hi"]) / 1000.0,
                "pct": 100.0 * float(cb["band_frac"])}

    # The value of converting at all, and whether it is big enough to normalize against.
    nc = summary.get("value_of_converting")
    pct_ok = bool(summary.get("pct_axis_ok"))
    skip_y1 = float(y[0]) if good.size and good[0] else None
    ratio = None
    if pct_ok and skip_y1 is not None and skip_y1 > 0:
        ratio = (nc / div) / skip_y1

    ymax = float(np.nanmax(hi if hi is not None else y))
    if mhi is not None and np.isfinite(mhi).any():
        ymax = max(ymax, float(np.nanmax(mhi)))
    ymin = min(0.0, float(np.nanmin(y)))
    ymax = ymax * 1.08 if ymax > 0 else 1.0

    return {
        "x": x, "y": y, "lo": lo, "hi": hi, "xd": xd, "yd": yd,
        "mean_lo": mlo, "mean_hi": mhi,
        "onset": onset, "floor": floor, "resolvable": resolvable,
        "valley": valley, "band": band,
        "never_convert": None if nc is None else nc / div,
        "pct_ok": pct_ok, "pct_max": (100.0 * ymax * div / nc) if pct_ok else None,
        "pct_min": (100.0 * ymin * div / nc) if pct_ok else None,
        "skip_y1": skip_y1,
        "skip_y1_pct": (100.0 * skip_y1 * div / nc) if (pct_ok and skip_y1 is not None) else None,
        "ratio": ratio,
        "ylabel": f"Regret {ylabel}", "suffix": suffix, "div": div,
        "ymin": ymin, "ymax": ymax,
        "n_scenarios": int(summary.get("n_scenarios", 0)),
    }


def regret_caption(prep, summary):
    """One-sentence reading of the graph, or the honest refusal when it has none."""
    n = prep["n_scenarios"]
    if summary.get("conversions_blocked"):
        return ("No commitment above zero is feasible in this case - conversions are either "
                "disallowed or unaffordable in essentially every scenario - so there is nothing "
                "to weigh.")
    if not prep["resolvable"]:
        return (f"Across {n} scenarios the curve is flat within the resolution of this run: "
                "no committed amount is measurably better than another.")
    bits = []
    if summary.get("valley_at_grid_edge"):
        bits.append("The curve is still falling where the grid ends, so the best "
                    "commitment is a lower bound rather than a located minimum.")
    if prep["band"] is not None:
        b = prep["band"]
        if b["hi"] - b["lo"] <= 0:
            # A band narrower than one grid step is not a precise answer, it is a steep
            # curve: no other commitment on the grid stays within the tolerance.
            bits.append(f"No commitment other than about ${b['lo']:,.0f}k stays within "
                        f"{b['pct']:.0f}% of the best one, so the amount matters here.")
        else:
            bits.append(f"Any first-year conversion between ${b['lo']:,.0f}k and ${b['hi']:,.0f}k "
                        f"gives up less than {b['pct']:.0f}% of what converting is worth.")
    if prep["ratio"] is not None and prep["ratio"] > 1.5:
        bits.append(f"Skipping only this year costs {prep['skip_y1_pct']:.0f}% of that value; "
                    f"never converting costs 100% — {prep['ratio']:.0f}x more.")
    if not bits:
        bits.append(f"Mean regret over {n} scenarios against each scenario's own optimum.")
    return " ".join(bits)
