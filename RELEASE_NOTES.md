### Version 2025.11.09
- Moved development status to production/stable in pyproject
- Made version propagate everywhere needed
- Added node limit on milp to avoid Streamlit server shutdown on memory consumption

### Version 2025.11.05
- Mentioning Owl as Optimal Wealth Lab
- Port to Streamlit 1.50 which broke many widgets
- Rework backprojection of assets to beginning of the year
- Rework Docker to smaller Alpine image and fix docs

### Version 2025.07.01
Added:
- Settings option for menu position thanks to Streamlit 1.46 top and sidebar capabilities. Default is top.
- Net Investment Income Tax calculations in self-consistent loop.
- Capability to load example Wages and Contributions Excel file from GitHub directly from UI.
- Constraint for 5-year maturation rule on Roth conversions.
- Extension to Wages and Contributions table 5 years in the past for tracking recent contributions to tax-free accounts and Roth conversions.
- Option in UI to turn off sticky header. This is useful for mobile or tablet use.
- A new case file allowing for direct comparison with DrawdownCalc. Both versions agree to the dollar, demonstrating that the compounding, withdrawals, and federal tax calculations are in perfect agreement despite using two completely different approaches to modeling the mixed-integer linear programming problem (direct matrix encoding vs PuLP high-level language).
- Option to use the HiGHS library through PuLP for speed comparison with DrawdownCalc. Using HiGHS directly is by far the fastest option.
- RELEASE_NOTES file.

Improvements:
- Changed color scheme in header gradient for visibility.
- Removed long-term capital tax rate from options. Rate is now automatically calculated in self-consistent loop.

