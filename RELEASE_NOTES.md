### Version 2025.12.11
- Add more bubble help messages in Create Case
- Fixed bug in rates selection UI
- Remove reliance on GitHub for graphics and example files

### Version 2025.12.10
- Added date of birth due to funny social security rules when birthday on 1st and 2nd
- Modified FRA calculations accordingly 
- Added integration to ssa.tools

### Version 2025.12.09
- Improved instructions for developers
- Added link to ssa.tools on `Fixed Income` page
- Fixed bug on max age range for SS when month != 0
- Added table of federal income tax itemized by bracket

### Version 2025.12.05
- Added instructions for obtaining PIA
- Bug fix in Fixed Income UI

### Version 2025.12.03
- Coded social security to use monthly PIA instead of annual amount
    - Added exact routines for FRA and increase/decrease factors due to claiming age
    - Added exact spousal benefits
- Adjusted documentation for social security
- Added birth month for more precise calculation on first year of social security
- Added month to age for claiming social security 

### Version 2025.11.29
- Fixed social security for survivor
- Enhanced documentation for SS amounts

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

