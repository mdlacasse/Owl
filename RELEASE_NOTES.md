### Version 2025.07.01

- Added Net Investment Income Tax calculations in self-consistent loop
- Added capability to load example Excel sheet directly in UI
- Added constraint for 5-year maturation rule on Roth conversions
- Added capability to read last 5 years in Wages and Contributions file
- Added option in UI to turn off sticky header
- Added RELEASE_NOTES file
- Improved color scheme in header gradient for visibility
- Removed long-term capital tax rate from options. Rate is now automatically calculated in self-consistent loop.
- Added option to use HiGHS library through PuLP for speed comparison with DrawdownCalc. Using HiGHS diretly is by far the fastest option.
- Add option for menu position thanks to Streamlit 1.46.
