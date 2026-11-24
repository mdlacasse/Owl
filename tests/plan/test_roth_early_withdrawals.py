"""
Before 59 1/2, Roth withdrawals stay within what went into the account (#209).

A Roth IRA distribution comes from contributions first, then conversions, and earnings last
(IRC 408A(d)(4)(B)); before 59 1/2 its earnings part is taxable and carries the 10% additional
tax (408A(d)(2)(A); Pub. 590-B). Owl forbids early earnings rather than taxing them: cumulative
Roth withdrawals before the 59 1/2 year are capped at the starting balance plus conversions and
contributions to date.

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

import io
import warnings

import numpy as np

import owlplanner as owl


def _plan(roth_k, expectancy=59):
    """Born 1976-07-15: 59 1/2 in January 2036, plan year 10 from 2026."""
    p = owl.Plan(["A"], ["1976-07-15"], [expectancy], "roth-early", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[30], taxDeferred=[200], taxFree=[roth_k], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 4, 2.5])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve("maxSpending", {"bequest": 0, "withMedicare": "None"})
    assert p.caseStatus == "solved"
    return p


def _early_room(p, i=0):
    """Basis left at the end of each year before 59 1/2: inflows to date minus withdrawals to date."""
    n = int(p.n595[i])
    inflow = p.b_ijn[i, 2, 0] + np.cumsum(p.xnet * p.x_in[i, :n] + p.kappa_ijn[i, 2, :n])
    return inflow - np.cumsum(p.w_ijn[i, 2, :n])


def test_no_earnings_withdrawn_before_59_and_a_half():
    """#209 repro: an empty Roth and a plan ending before 59 1/2. The Roth used to take $51,506 of
    conversions and give back $74,387, $22,881 of it earnings, untaxed and unpenalized."""
    p = _plan(0)
    assert int(p.n595[0]) == p.N_n  # no year of the plan is past 59 1/2
    assert np.all(_early_room(p) >= -1.0)
    assert p.w_ijn[0, 2].sum() <= p.xnet * p.x_in[0].sum() + 1.0


def test_starting_balance_counts_as_basis():
    """The whole starting Roth balance can still come out early (Owl has no input for its basis)."""
    p = _plan(100)
    assert np.all(_early_room(p) >= -1.0)
    assert p.w_ijn[0, 2, : int(p.n595[0])].sum() > 0  # the starting balance is used before 59 1/2


def test_rows_stop_at_59_and_a_half():
    """One row per year before the 59 1/2 year; a longer plan has none past it."""
    p = _plan(0, expectancy=70)
    years = sorted(n for tag in p.A.tags if isinstance(tag, tuple) and tag[0] == "roth_early_basis"
                   for n in [tag[2]])
    assert years == list(range(int(p.n595[0])))


def test_rows_stop_at_the_first_death():
    """A surviving spouse can keep the deceased's Roth as an inherited Roth (no 10%): no rows from
    the first death on. A (born 1976) dies after 2030; B (born 1978) reaches 59 1/2 in 2038."""
    p = owl.Plan(["A", "B"], ["1976-07-15", "1978-07-15"], [54, 90], "roth-couple", verbose=False,
                 logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[30, 30], taxDeferred=[200, 200], taxFree=[50, 50], startDate="01-01")
    p.setAllocationRatios("spouses", generic=[[60, 40, 0, 0], [60, 40, 0, 0]])
    p.setRates("user", values=[6, 4, 4, 2.5])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve("maxSpending", {"bequest": 0, "withMedicare": "None"})
    assert p.caseStatus == "solved"
    rows = {(i, n) for tag in p.A.tags if isinstance(tag, tuple) and tag[0] == "roth_early_basis"
            for _, i, n in [tag]}
    n_d = int(p.n_d)
    assert n_d < int(p.n595[1])  # the survivor is still under 59 1/2 at the first death
    assert rows == {(i, n) for i in (0, 1) for n in range(n_d)}


def _rows_holding_x(p, family):
    """{m: [n of each row tagged `family` that carries the conversion x[0, m]]}, read from p.A."""
    x_of = {p.vm["x"].idx(0, m): m for m in range(p.N_n)}
    held = {}
    for r, tag in enumerate(p.A.tags):
        if tag and tag[0] == family and tag[1] == 0:
            for k in p.A.Aind[r]:
                if k in x_of:
                    held.setdefault(x_of[k], []).append(tag[2])
    return held


def _law_10pct_on_roth(p, i=0):
    """The 10% that IRC 408A(d)(4)(B) and (d)(3)(F) charge on the plan's Roth withdrawals before 59 1/2:
    conversions come out oldest first, then earnings; a year-m conversion is charged through year m+4,
    earnings always. The starting balance counts as basis, as in Owl."""
    layers, law = [[-99, float(p.b_ijn[i, 2, 0])]], np.zeros(p.N_n)
    for n in range(p.N_n):
        if p.x_in[i, n] > 0:
            layers.append([n, p.xnet * p.x_in[i, n]])
        out = p.w_ijn[i, 2, n]
        for layer in layers:
            take = min(out, layer[1])
            layer[1] -= take
            out -= take
            law[n] += take if n < layer[0] + 5 else 0
        law[n] += out
    law[int(p.n595[i]):] = 0
    return 0.1 * law


def test_a_conversion_is_held_through_its_fifth_taxable_year_only():
    """#224: the 5-taxable-year period of 408A(d)(3)(F) begins with the year of the conversion, so a
    year-m conversion is free in year m+5. It enters the balance in m+1, so the maturation rows hold it
    in m+1..m+4; they held it through m+5, a year more than the law."""
    p = _plan(0, expectancy=85)
    held = _rows_holding_x(p, "roth_maturation")
    for m in range(3):
        assert held[m] == [m + 1, m + 2, m + 3, m + 4], (m, held[m])


def test_only_matured_conversions_count_as_basis_before_59_and_a_half():
    """#223: a conversion still in its period, the year's own included, is what a withdrawal beyond the
    matured ones takes first (408A(d)(4)(B)), and is charged the 10% before 59 1/2. The #209 row of year
    n counts conversions up to year n-5 only."""
    p = _plan(0)
    held = _rows_holding_x(p, "roth_early_basis")
    for m, rows in held.items():
        assert min(rows) == m + 5, (m, rows)


def test_no_same_year_conversion_and_withdrawal_of_earnings():
    """#223's case: $20,000 converted in 2026 (pinned), the whole plan before 59 1/2. Counting every
    conversion as basis let a later year convert X and withdraw X from a Roth holding only earnings,
    which the ordering rules charge the 10% (in 2033, $748). The 2026 conversion now comes out in 2031,
    its first free year, and nothing the law charges goes uncharged."""
    p = owl.Plan(["A"], ["1976-07-15"], [59], "roth-recapture", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[30], taxDeferred=[200], taxFree=[0], startDate="01-01")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 4, 2.5])
    p.myRothX_in[0, 0], p.rothXfixed_in[0, 0] = 20_000, True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p.solve("maxSpending", {"bequest": 0, "withMedicare": "None"})
    assert p.caseStatus == "solved"
    assert _law_10pct_on_roth(p).sum() < 1.0
    first_out = int(np.argmax(p.w_ijn[0, 2] > 1.0))
    assert p.year_n[first_out] == 2031
