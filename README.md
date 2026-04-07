
# Owl - Optimal Wealth Lab

[![CI](https://github.com/mdlacasse/owl/actions/workflows/github-actions-runtests.yml/badge.svg)](https://github.com/mdlacasse/owl/actions/workflows/github-actions-runtests.yml)
[![GitHub release](https://img.shields.io/github/v/release/mdlacasse/owl)](https://github.com/mdlacasse/owl/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/owlplanner)](https://pypi.org/project/owlplanner/)
[![Python](https://img.shields.io/pypi/pyversions/owlplanner)](https://pypi.org/project/owlplanner/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Docker](https://img.shields.io/docker/v/owlplanner/owldocker.static?label=docker)](https://hub.docker.com/r/owlplanner/owldocker.static)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://owlplanner.streamlit.app)

## A retirement exploration tool based on mixed-integer linear programming

<img align="right" src="papers/images/owl.png" width="250">

-------------------------------------------------------------------------------------

### TL;DR
Owl is a retirement financial planning tool that uses a
mixed-integer linear programming optimization algorithm to provide
guidance on retirement decisions
such as contributions, withdrawals, Roth conversions, and more.
Users can select varying return rates to perform historical back testing,
stochastic rates for performing Monte Carlo analyses,
or fixed rates either derived from historical averages, or set by the user.

Owl is designed for US retirees as it considers US federal tax laws,
ACA marketplace premiums (pre-65), Medicare premiums, rules for 401k including
required minimum distributions, maturation rules for Roth accounts and conversions,
social security rules, etc.

Among open-source retirement planning tools, Owl stands out for its unmatched capabilities and the rigor of its financial modeling. While the full API rewards those willing to invest time, the Streamlit web interface provides an accessible entry point for all users.

There are three ways to run Owl (from easiest to more complex):

1) **Streamlit Hub:** Run Owl remotely as hosted on the Streamlit Community Cloud at
[owlplanner.streamlit.app](https://owlplanner.streamlit.app).

1) **Docker Container:** Run Owl locally on your computer using a Docker image.
Follow these <a href="docker/README.md" target="_blank" rel="noopener noreferrer">instructions</a> for using this option.

1) **Self-hosting:** Run Owl locally on your computer using Python code and libraries.
Follow these <a href="INSTALL.md" target="_blank" rel="noopener noreferrer">instructions</a> to install from the source code and self-host on your own computer.


---------------------------------------------------------------
## Documentation

| Document | Description |
|---------|-------------|
| <a href="docs/modeling-capabilities.md" target="_blank" rel="noopener noreferrer">docs/modeling-capabilities.md</a> | Summary of modeled components, assumptions, and limitations |
| <a href="INSTALL.md" target="_blank" rel="noopener noreferrer">INSTALL.md</a> | Installation guide, Python environment setup, and developer build steps |
| <a href="USER_GUIDE.md" target="_blank" rel="noopener noreferrer">USER_GUIDE.md</a> | Python API usage with examples for Jupyter notebooks and scripts |
| <a href="PARAMETERS.md" target="_blank" rel="noopener noreferrer">PARAMETERS.md</a> | Complete reference for TOML case file parameters |
| <a href="RATE_MODELS.md" target="_blank" rel="noopener noreferrer">RATE_MODELS.md</a> | Available rate models (historical, stochastic, bootstrap, etc.) |
| <a href="papers/" target="_blank" rel="noopener noreferrer">papers/owl.pdf</a> | Mathematical foundations |

Documentation for the app user interface is also available from the [Streamlit UI](https://owlplanner.streamlit.app/Documentation).

---------------------------------------------------------------------

## Credits and Acknowledgements
See <a href="CREDITS.md" target="_blank" rel="noopener noreferrer">CREDITS.md</a>.

## Bugs and Feature Requests
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool.

## Privacy
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

---------------------------------------------------------------------

Copyright &copy; 2024-2026 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

Code output has been verified with analytical solutions when applicable, and comparative approaches otherwise.
Nevertheless, accuracy of results is not guaranteed.

--------------------------------------------------------

