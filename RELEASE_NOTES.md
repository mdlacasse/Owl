### Version 2026.01.15
- Fix LTCG tax computation (self-consistent stacking accuracy)
- Add non-taxable portion of SS to MAGI
- Fix cash-flow to include all fixed-asset proceeds
- Apply max Roth conversion cap across both spouses
- Clarify SS tax fraction vs LTCG effective rate
- Align documentation and reproducibility baselines with code

### Version 2026.01.12
- Merged binary exclusion constraints for both spouses (one set per year instead of per individual)
  - Updated paper to reflect that binary variables $z_{nz}$ are shared across both spouses
  - Reduced binary variable count from $4N_iN_n$ to $4N_n$ for married couples
- Improved loop detection for oscillatory solutions
- Exposed tolerance and bigM parameters for experimenting with solver
- Added time limit of 15 min for solution
- Fixed rare condition in UI when starting Upload case and hopping to Logs
- Changed convergence criteria to only consider objective function (not solution vector)
- Split bigM between XOR exclusion constraints and IRMAA Medicare conditions

### Version 2026.01.08
- Fixed dividends being taxed twice on taxable account withdrawals
- Removed int32 normalization of seed (reverted from 2026.01.07)
- Removed unused file-based rates parameters (rateFile, rateSheetName, workbook_file, worksheet_name)
  - Cleaned up leftover code from deprecated file method for reading rates
  - Removed from plan.py, config.py, owlbridge.py, and Rates_Selection.py
  - Updated PARAMETERS.md to remove file method documentation
- Added tip help to case Delete operation in UI
- Updated paper PDF to reflect change in dividend tax calculation
- Replaced duplicate owl.tex and images with symlinks to avoid duplication
- Refactored code in config.py, debts.py, fixedassets.py, and utils.py
- Added tests to increase coverage and harden code

### Version 2026.01.07
- Normalized seed to fit in signed int32 (issue #59)
- Removed animation
- Updated Adamodar rates for 2025
- Made kim+sam cases consistent
- Minor edits in About page

### Version 2026.01.05
- Migrated examples and TOML configuration to snake_case (closing issue #52)
    - Optimizer still uses camelCase for distinction
- Added reproducibility flag and merged reproducibility branch
- Added year field for Fixed Assets (issue #57)
- Added check on Debts validation
- Fixed bug in timelist when missing years
- Fixed config withMedicare that is no longer Boolean
- Added confirm button to case delete in UI
- Added preliminary file listing TOML parameters (PARAMETERS.md)
- Added script to build container on MacOS/linux
- Fixed Streamlit race condition and column conditioning
- Updated all cases and repro tests for 2026
- Improved documentation on self-consistent loops and Medicare
- Improved documentation and terminology on fixed assets
- Made Create Case page more consistent
- Updated About page to point to AUTHORS file
- Added one-to-many map for HFP-case in examples
- Updated kim+sam example for sharing
- Cleaned license and authorship
- Cosmetic improvements on Summary output

### Version 2025.12.29
- Integrated loguru logging system with global log and filters
    - Split logger per object
    - Added persistence in TOML file
    - Update logger when case is renamed
    - Use a stack for verbose status
    - Address multiline logs (issue #36)
    - Check case name in first line of log group
- Added id to allow name change and log filtering (issue #36)
- Fixed issue #48 caused by past contributions
- Propagate HFP filename to TOML if unedited
- Minor fixes on HFP filenames
- Removed hydra-core dependency (pull request #44)
- Simplified CLI, removed hydra dependencies
- Fixed SSA issues
- Changed word "claiming" to "starting" for SSA
- Added different tool tip for those born on 1st and 2nd
- Improved benefits explanations
- Regen efficiency & no correlation for fixed rates
- Improved error message in tax202x
- Warning on clearing logs - yOBBBA year rebase
- Made OBBA expiration year idiot proof
- Fixed typo (issue #47)

### Version 2025.12.20
- Implemented Debts and Fixed Assets capabilities
    - Mortgages, loans, restricted stocks, etc. and fixed lump-sum annuities can now be modeled
    - Debts and fixed assets at end of plan included in bequest
- Extended Wages and Contributions page which was renamed Household Financial Profile
- Added debt payment and fixed assets bequest reporting to Synopsis
- Improved logic on bequest constraint
- Added constraint on fixed assets
- Fixed bug in Debts and Fixed Assets tables
- Included Debts and Fixed Assets in example HFPs
- Improved user interface
- Improved integration with ssa.tools

### Version 2025.12.16
- Fixed error message when dates are empty in Create_Case
- Added fix to prevent stored TOML age from being out of range
- Renamed duplicate to copy
- Fixed input error on months
- Prepared for new tax season
- Carried minor fixes from dev version

### Version 2025.12.11
- Added more bubble help messages in Create Case
- Fixed bug in rates selection UI
- Removed reliance on GitHub for graphics and example files
- Updated UI to use new file locations
- Added new owl.png logo

### Version 2025.12.10
- Added date of birth due to social security rules when birthday on 1st and 2nd
- Modified FRA calculations accordingly
- Added integration to ssa.tools
- Added Dale's help message for date of birth

### Version 2025.12.09
- Improved instructions for developers
- Added link to ssa.tools on Fixed Income page
- Fixed bug on max age range for SS when month != 0
- Added table of federal income tax itemized by bracket
- Improved instructions for ssa.tools

### Version 2025.12.05
- Added instructions for obtaining PIA
- Enhanced documentation for obtaining PIA
- Added generic reference for PIA calculation
- Fixed bug in Fixed Income UI
- Fixed error in month input
- Added hint for birth month

### Version 2025.12.03
- Coded social security to use monthly PIA instead of annual amount
    - Added exact routines for FRA and increase/decrease factors due to claiming age
    - Added exact spousal benefits
- Adjusted documentation for social security
- Added birth month for more precise calculation on first year of social security
- Added month to age for claiming social security

### Version 2025.11.29
- Fixed social security for survivor benefits
- Enhanced documentation for SS amounts
- Added caveat on account allocation ratios in documentation
- Fixed typo in documentation

### Version 2025.11.09
- Moved development status to production/stable in pyproject
- Made version propagate everywhere needed
- Added node limit on MILP to avoid Streamlit server shutdown on memory consumption
- Updated documentation and README for clarity
- Updated section titles for clarity
- Clarified options for running Owl in README
- Updated GitHub star request wording in Quick Start

### Version 2025.11.05
- Mentioned Owl as Optimal Wealth Lab
- Ported to Streamlit 1.50 which broke many widgets
- Fixed UI bugs from port to Streamlit 1.50
- Reworked backprojection of assets to beginning of the year
- Improved backprojection when not January 1
- Reworked Docker to smaller Alpine image and fixed docs
- Clarified instructions for Docker
- Updated FI Calc link to use full URL
- Fixed tests and error messages
- Fixed graph settings
- Made case naming consistent

### Version 2025.07.01
- Added settings option for menu position (top or sidebar) thanks to Streamlit 1.46 capabilities
    - Default is top menu
- Added Net Investment Income Tax calculations in self-consistent loop
- Added capability to load example Wages and Contributions Excel file from GitHub directly from UI
- Added constraint for 5-year maturation rule on Roth conversions
- Extended Wages and Contributions table 5 years in the past for tracking recent contributions to tax-free accounts and Roth conversions
- Added option in UI to turn off sticky header (useful for mobile or tablet use)
- Added new case file allowing for direct comparison with DrawdownCalc
    - Both versions agree to the dollar, demonstrating perfect agreement in compounding, withdrawals, and federal tax calculations
    - Uses two different approaches: direct matrix encoding vs PuLP high-level language
- Added option to use HiGHS library through PuLP for speed comparison
    - Using HiGHS directly is the fastest option
- Added RELEASE_NOTES file
- Changed color scheme in header gradient for visibility
- Removed long-term capital tax rate from options
    - Rate is now automatically calculated in self-consistent loop

