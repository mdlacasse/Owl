"""
Tests for Qualified Charitable Distributions (QCD).

A QCD is a direct transfer from a tax-deferred account to charity. It has four
properties the model must reproduce, and they are what these tests check:
excluded from AGI, credited against the RMD, drawn from the tax-deferred
balance, and never spendable cash.

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

from datetime import date

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_federal as tx

thisyear = date.today().year


def makePlan(*, birth="1950-01-15", expectancy=None, taxDeferred=1_500, taxable=300, taxFree=200):
    """A single retiree already past 70½, with enough tax-deferred wealth for RMDs to bite."""
    if expectancy is None:
        expectancy = (thisyear - int(birth[:4])) + 20
    p = owl.Plan(["Alice"], [birth], [expectancy], "QCD test", verbose=False)
    p.zeroWagesAndContributions()
    p.setAccountBalances(taxable=[taxable], taxDeferred=[taxDeferred], taxFree=[taxFree])
    p.setAllocationRatios("individual", generic=[[[60, 20, 20, 0], [60, 20, 20, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setSpendingProfile("flat", 60)
    p.setSocialSecurity([2_000], [70])
    return p


def solved(p, objective="maxSpending", **opts):
    options = {"solver": "HiGHS", "bequest": 0, **opts}
    p.solve(objective, options)
    assert p.caseStatus == "solved"
    return p


class TestQCDEligibility:
    def test_age_gate_rejects_a_too_young_donor(self):
        """A QCD requires age 70½; entering one earlier is an error, not a warning."""
        birth = f"{thisyear - 60}-01-15"
        p = makePlan(birth=birth)
        p.qcd_in[0, 0] = 10_000
        with pytest.raises(ValueError, match="70"):
            p.validateQCD()

    def test_age_gate_uses_the_half_year_convention(self):
        """
        Someone born in the second half of the year reaches 70½ the year they turn 71,
        matching how n595 handles the 59½ threshold.
        """
        early = makePlan(birth=f"{thisyear - 70}-03-15")  # 70½ this year
        late = makePlan(birth=f"{thisyear - 70}-09-15")  # 70½ next year
        assert early.n_qcd_i[0] == 0
        assert late.n_qcd_i[0] == 1

        late.qcd_in[0, 0] = 10_000
        with pytest.raises(ValueError, match="70"):
            late.validateQCD()

        late.qcd_in[0, 0] = 0
        late.qcd_in[0, 1] = 10_000
        late.validateQCD()  # eligible the following year

    def test_annual_cap_is_enforced_for_published_years(self):
        p = makePlan()
        cap = tx.qcdLimitForYear(thisyear)
        p.qcd_in[0, 0] = cap + 1
        with pytest.raises(ValueError, match="exclusion limit"):
            p.validateQCD()

        p.qcd_in[0, 0] = cap
        p.validateQCD()

    def test_cap_beyond_the_published_table_is_projected(self):
        """
        IRS publishes the limit a year at a time, so later years carry the last
        published figure forward at a fixed assumed inflation. Fixed, not the
        scenario's own inflation: this figure only validates user input, and a
        scenario-dependent bound would accept an entry on one Monte Carlo path and
        reject it on the next.
        """
        last = max(tx.qcdLimit)
        assert tx.qcdLimitForYear(last) == tx.qcdLimit[last]
        assert tx.qcdLimitForYear(last + 10) == pytest.approx(
            tx.qcdLimit[last] * (1 + tx.QCD_LIMIT_INFLATION) ** 10
        )

        p = makePlan()
        n = last - thisyear + 5
        assert n < p.N_n, "test needs a horizon reaching past the published table"
        p.qcd_in[0, n] = 10 * tx.qcdLimitForYear(thisyear)
        with pytest.raises(ValueError, match="projected"):
            p.validateQCD()

    def test_giving_indexed_to_inflation_is_not_rejected(self):
        """
        Why the cap is projected rather than held flat at the last published figure.
        A constant real gift is entered as growing nominal amounts; against a flat
        cap it would cross within a few years and be rejected for the rest of the
        plan, which is the ordinary way to express charitable giving.
        """
        p = makePlan()
        p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
        realGift = 0.9 * tx.qcdLimitForYear(thisyear)
        for n in range(p.N_n):
            p.qcd_in[0, n] = realGift * p.gamma_n[n]

        assert p.qcd_in[0, -1] > tx.qcdLimit[max(tx.qcdLimit)], "test needs to cross the flat cap"
        p.validateQCD()  # no exception

    def test_a_rejected_table_does_not_reach_the_plan(self):
        """
        setContributions validates before committing. A table refused for one bad cell
        must leave qcd_in as it was, rather than holding values the plan just rejected.
        """
        birth = f"{thisyear - 60}-01-15"  # too young for any QCD
        p = makePlan(birth=birth)
        df = p.timeLists["Alice"]
        df.loc[df["year"] == thisyear, "QCD"] = 10_000

        with pytest.raises(ValueError, match="70"):
            p.setContributions()
        assert np.all(p.qcd_in == 0)


class TestQCDMechanics:
    def test_zero_qcd_changes_nothing(self):
        """The whole feature must be inert when unused."""
        base = solved(makePlan())
        p = makePlan()
        p.qcd_in[:, :] = 0.0
        assert solved(p).basis == pytest.approx(base.basis, rel=1e-9)

    def test_drains_the_tax_deferred_balance(self):
        """b[i,1,n+1] must follow the recursion including the QCD term."""
        p = makePlan()
        p.qcd_in[0, 2] = 40_000
        solved(p)

        tau = np.sum(p.alpha_ijkn[0, 1, :, 2] * p.tau_kn[:, 2])
        expected = (1 + tau) * (p.b_ijn[0, 1, 2] - p.w_ijn[0, 1, 2] - p.x_in[0, 2] - p.qcd_in[0, 2])
        expected += p.kappa_ijn[0, 1, 2] * (1 + tau / 2)
        assert p.b_ijn[0, 1, 3] == pytest.approx(expected, abs=1.0)

    def test_is_excluded_from_taxable_income(self):
        """
        The exclusion is the point of the feature. Compare the same gift funded two
        ways, under maxBequest with a fixed budget so the RMD actually binds.

        The exclusion does NOT show up as a lower year-n tax bill: the QCD frees
        ordinary-income headroom, and an optimizing plan immediately refills it with
        a Roth conversion. Taxable income comes out identical and the benefit lands
        in the estate instead. Asserting on T_n[n] would fail against a correct
        implementation, so assert the substitution itself -- it is exact, and it
        pins the QCD to being worth precisely its face value in bracket space.
        """
        gift = 40_000
        n = 3
        opts = dict(netSpending=50)

        withQcd = makePlan()
        withQcd.qcd_in[0, n] = gift
        solved(withQcd, "maxBequest", **opts)

        withCash = makePlan()
        withCash.Lambda_in[0, n] -= gift  # same money out, but after tax
        solved(withCash, "maxBequest", **opts)

        assert withQcd.rho_in[0, n] * withQcd.b_ijn[0, 1, n] > 0, "test needs a binding RMD"

        # The forced taxable withdrawal drops by the full gift ...
        assert withCash.w_ijn[0, 1, n] - withQcd.w_ijn[0, 1, n] == pytest.approx(gift, abs=1.0)
        # ... the freed headroom is converted instead ...
        assert withQcd.x_in[0, n] - withCash.x_in[0, n] == pytest.approx(gift, abs=1.0)
        # ... so taxable income is unchanged.
        assert withQcd.G_n[n] == pytest.approx(withCash.G_n[n], abs=1.0)

        # The advantage is real, and it accrues over the horizon.
        assert np.sum(withQcd.T_n) < np.sum(withCash.T_n)
        assert withQcd.bequest > withCash.bequest

    def test_counts_toward_the_rmd(self):
        """A QCD covering the whole RMD frees the plan from withdrawing at all."""
        p = makePlan(taxDeferred=1_500, taxable=800)
        n = 2
        # Comfortably above the RMD on a $1.5M balance at this age.
        p.qcd_in[0, n] = 100_000
        solved(p)

        grossRmd = p.rho_in[0, n] * p.b_ijn[0, 1, n]
        assert grossRmd > 0, "test needs a year where an RMD is actually due"
        assert p.qcd_in[0, n] > grossRmd
        assert p.w_ijn[0, 1, n] == pytest.approx(0.0, abs=1.0)

    def test_is_not_spendable_cash(self):
        """Unlike a withdrawal, a QCD must not raise the spending budget."""
        base = solved(makePlan())
        p = makePlan()
        p.qcd_in[0, 2] = 40_000
        solved(p)
        assert p.basis < base.basis


class TestQCDReporting:
    def test_rmd_split_still_sums_to_the_withdrawal(self):
        """
        rmd_in + dist_in is a cash identity the sources decomposition depends on.
        A QCD lets w fall below the gross RMD, which is what used to break it.
        """
        p = makePlan(taxDeferred=1_500, taxable=800)
        p.qcd_in[0, 2] = 100_000
        solved(p)

        assert np.all(p.rmd_in >= -1e-6)
        assert np.all(p.dist_in >= -1e-6)
        assert np.allclose(p.rmd_in + p.dist_in, p.w_ijn[:, 1, :], atol=1.0)

    def test_qcd_rmd_is_capped_by_the_gross_rmd(self):
        """Only the part of a QCD that meets an RMD is reported as meeting one."""
        p = makePlan()
        p.qcd_in[0, 2] = 100_000
        solved(p)

        grossRmd = p.rho_in * p.b_ijn[:, 1, :-1]
        assert np.all(p.qcd_rmd_in <= grossRmd + 1e-6)
        assert np.all(p.qcd_rmd_in <= p.qcd_in + 1e-6)

    def test_giving_appears_in_the_lifetime_allocation(self):
        """
        A QCD leaves the portfolio without passing through the budget, so without an
        explicit slice the gift is invisible and silently inflates the portfolio
        residual. Both dicts must still sum to the same total.
        """
        gift, n = 40_000, 2
        p = makePlan()
        p.qcd_in[0, n] = gift
        solved(p)

        alloc = p.lifetime_allocation()
        assert alloc["outflows"]["charity"] == pytest.approx(gift / p.gamma_n[n], abs=1.0)
        assert sum(alloc["outflows"].values()) == pytest.approx(sum(alloc["income"].values()), abs=1.0)

        mix = p.annual_cashflow_mix()
        assert mix["outflows"]["charity"][n] == pytest.approx(gift / p.gamma_n[n], abs=1.0)

        # A plan without giving keeps a zero slice, which the backends drop.
        base = solved(makePlan())
        assert base.lifetime_allocation()["outflows"]["charity"] == 0

    def test_giving_is_described_as_year_runs(self):
        """
        explain_case reports the schedule in the shape run_from_params accepts, so a
        described case reads back as tool input. end_year is exclusive.
        """
        from owlplanner.cli.cmd_explain import _plan_to_explain, _runs

        assert _runs([0, 5, 5, 5, 0, 7], 2030) == [
            {"start_year": 2031, "end_year": 2034, "annual_amount": 5},
            {"start_year": 2035, "end_year": 2036, "annual_amount": 7},
        ]

        p = makePlan()
        p.qcd_in[0, 1:4] = 20_000
        described = _plan_to_explain(p, "memory", ())
        assert described["qcds"] == [
            {
                "person": "Alice",
                "start_year": int(p.year_n[1]),
                "end_year": int(p.year_n[4]),
                "annual_amount": 20_000,
            }
        ]
        assert _plan_to_explain(makePlan(), "memory", ())["qcds"] == []

    def test_cash_flow_identity_holds(self):
        """A QCD touches neither side of the cash balance; the check must stay silent."""
        p = makePlan()
        p.qcd_in[0, 2] = 40_000
        solved(p)

        lhs = p.g_n + p.s_n + p.T_n + p.U_n + p.J_n + p.st_T_n + p.medicare_n + p.aca_costs_n + p.debt_payments_n
        rhs = (
            np.sum(p.omega_in, axis=0)
            + np.sum(p.other_inc_in, axis=0)
            + np.sum(p.netinv_in, axis=0)
            + np.sum(p.zetaBar_in, axis=0)
            + np.sum(p.piBar_in, axis=0)
            + np.sum(p.spiaBar_in, axis=0)
            + np.sum(p.Lambda_in, axis=0)
            + p.fixed_assets_ordinary_income_n
            + p.fixed_assets_capital_gains_n
            + p.fixed_assets_tax_free_n
            + np.sum(p.w_ijn, axis=(0, 1))
        )
        assert np.max(np.abs(lhs - rhs)) < 1.0


class TestQCDCouple:
    @staticmethod
    def makeCouple():
        """Jo dies first, so the survivor inherits mid-plan."""
        p = owl.Plan(
            ["Jo", "Sam"],
            [f"{thisyear - 76}-01-15", f"{thisyear - 74}-01-15"],
            [80, 90],
            "QCD couple",
            verbose=False,
        )
        p.zeroWagesAndContributions()
        p.setAccountBalances(taxable=[300, 100], taxDeferred=[1_200, 400], taxFree=[100, 50])
        p.setAllocationRatios("individual", generic=[[[60, 20, 20, 0], [60, 20, 20, 0]]] * 2)
        p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
        p.setSpendingProfile("flat", 60)
        p.setSocialSecurity([2_000, 1_500], [70, 70])
        return p

    def test_final_year_qcd_is_carried_into_the_inherited_balance(self):
        """
        At n_d - 1 the deceased's own carryover row is zeroed (fac1 = 0) and their
        balance is folded into the survivor's row scaled by phi_j. A QCD in that
        year is therefore only ever accounted for in the survivor's branch --
        omitting it there loses the money silently, so check the identity directly
        rather than an inequality the optimizer could satisfy by other means.
        """
        p = self.makeCouple()
        n = p.n_d - 1
        i_d, i_s = p.i_d, p.i_s
        p.qcd_in[i_d, n] = 50_000
        solved(p, "maxBequest", netSpending=60)

        def tau(i):
            return np.sum(p.alpha_ijkn[i, 1, :, n] * p.tau_kn[:, n])

        def branch(i):
            t = tau(i)
            net = p.b_ijn[i, 1, n] - p.w_ijn[i, 1, n] - p.x_in[i, n] - p.qcd_in[i, n]
            return (1 + t) * net + p.kappa_ijn[i, 1, n] * (1 + t / 2)

        expected = branch(i_s) + p.phi_j[1] * branch(i_d)
        assert p.b_ijn[i_s, 1, n + 1] == pytest.approx(expected, abs=1.0)

        # Dropping the QCD from the survivor's branch would be off by this much.
        assert p.phi_j[1] * (1 + tau(i_d)) * 50_000 > 1.0

    def test_candidate_validation_uses_the_right_person(self):
        """
        validateQCD(qcd_in=...) checks values without touching the plan, for editors
        that want to reject a bad cell at entry. It indexes horizons/yobs/n_qcd_i
        positionally, so a caller must place values at the person's own row --
        a one-row array would check a spouse against the wrong birth date.
        """
        p = owl.Plan(
            ["Young", "Old"],
            [f"{thisyear - 60}-01-15", f"{thisyear - 76}-01-15"],
            [85, 90],
            "QCD gate",
            verbose=False,
        )
        p.zeroWagesAndContributions()

        values = np.zeros((p.N_i, p.N_n))
        values[1, 0] = 20_000  # Old is eligible
        p.validateQCD(qcd_in=values)  # no exception

        values = np.zeros((p.N_i, p.N_n))
        values[0, 0] = 20_000  # Young is not
        with pytest.raises(ValueError, match="Young"):
            p.validateQCD(qcd_in=values)

        # Candidate checks must not disturb the plan's own state.
        assert np.all(p.qcd_in == 0)

    def test_each_spouse_has_an_independent_age_gate(self):
        p = self.makeCouple()
        assert p.n_qcd_i[0] == 0 and p.n_qcd_i[1] == 0
        p.qcd_in[0, 1] = 20_000
        p.qcd_in[1, 1] = 30_000
        solved(p)
        assert np.sum(p.qcd_in) == 50_000
