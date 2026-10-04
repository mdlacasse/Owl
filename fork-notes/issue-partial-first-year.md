# Draft upstream issue (mdlacasse/Owl): a mid-year start date applies a full year of flows to balances already net of them

**Filed upstream by the user on 2026-10-04** (issue number not recorded yet). A design question, so no patch.

**Title:** Partial first year: balances entered after Jan 1 are back-projected for growth only, then charged a full year of spending, income and contributions

---

With a `startDate` after January 1, `_add_initial_balances` divides each balance by `1 + yearSpent * tau` (`yearSpent = 1 - yearFracLeft`). That removes the market growth since January 1 and nothing else. Year 0 then runs a full year of wages, contributions, SS, pensions and spending from the back-projected balance. `yearFracLeft` is used nowhere else in the model, only in one report line (`export.py`, "Net spending remaining in year"). A balance read on October 1 already reflects nine months of that year's spending and income, and the model applies them again. For a retiree this understates wealth by about three quarters of a year's net withdrawal, which is conservative. For a worker it double-counts three quarters of a year's net saving, which is optimistic.

**Repro** (on `dev`, `c1e5619`), from the repository root. The same $1M balance, entered as of January 1 and as of October 1:

```python
import io
import owlplanner as owl

for start in ("01-01", "10-01"):
    p = owl.Plan(["Bo"], ["1958-06-15"], [90], "partial", verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0], taxDeferred=[1000], taxFree=[0], startDate=start)
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("user", values=[6, 4, 3, 2.5])
    p.setSocialSecurity([2500], [67])
    p.solve("maxSpending", {"bequest": 0, "withMedicare": "None", "withSSTaxability": 0.85})
    w0 = p.w_ijn[0, 1, 0]
    print(f"start {start}: yearFracLeft {p.yearFracLeft:.3f}  year-0 balance {p.b_ijn[0, 1, 0]:,.0f}"
          f"  year-0 withdrawal {w0:,.0f}  year-0 spending {p.g_n[0]:,.0f}  basis {p.basis:,.0f}/yr")
```

```
start 01-01: yearFracLeft 1.000  year-0 balance 1,000,000  year-0 withdrawal 68,542  year-0 spending 77,013  basis 77,013/yr
start 10-01: yearFracLeft 0.252  year-0 balance 962,563  year-0 withdrawal 62,548  year-0 spending 75,382  basis 75,382/yr
```

On October 1 only a quarter of the year's spending remains to be funded from the $1M. The model funds a full year from it, after removing nine months of growth, and the spending basis comes out 2.1% lower than for the same balance on January 1. Both effects push the same way here: the growth removed and the flows already spent but charged again.

**Options**, for the maintainer to choose:

1. **Prorate year 0.** Scale year-0 flows (wages, contributions, SS, pensions, other income, spending, debt payments, the RMD) by `yearFracLeft`, and grow balances over `yearFracLeft` of a year instead of back-projecting them. This is the most faithful option. It touches many rows and reports (the spending profile is anchored on `g_0`, so the objective would read the full-year basis while year 0 spends a fraction of it), and it changes every case whose start date isn't January 1.
2. **Back-project the elapsed net flows too.** Keep full-year rows, but make the January 1 balance an LP variable tied to the entered balance by `b_0 (1 + yearSpent tau) + yearSpent * (net flows into the account in year 0) = beta`. This is closer to the current structure, but the net flows of an account depend on LP variables, and splitting the household's spending across accounts is arbitrary.
3. **Document it.** Tell users to enter balances as of January 1, or to treat the start date as only the date on which the plan's ages and the "remaining in year" report are computed.

Option 3 costs nothing. Option 1 is what a user who enters "today's" balances expects.
