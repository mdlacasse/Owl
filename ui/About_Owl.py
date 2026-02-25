"""
About page for Owl retirement planner Streamlit UI.

This module displays information about the Owl application including version,
credits, and links to documentation and source code.

Copyright (C) 2025-2026 The Owlplanner Authors

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

from pathlib import Path

import streamlit as st

import sskeys as kz
import owlbridge as owb


st.markdown("# :material/info: About Owl - Optimal Wealth Lab🦉")
kz.divider("orange")

st.markdown(f"This is Owl version {owb.version()} running on Streamlit {st.__version__}.")
# st.balloons()

credits_md = (Path(__file__).parent.parent / "CREDITS.md").read_text()
credits_md = credits_md.replace(
    "## Credits and Acknowledgements",
    "#### :orange[Credits and Acknowledgements]",
    1,
)

st.markdown(
    """
- Owl is an open-source retirement financial planner capable of optimization through
mixed-integer linear programming.
- Source code is available from a repository on [GitHub](https://github.com/mdlacasse/Owl).
- Mathematical formulation of the linear optimization problem can be
found in this [document](https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf?raw=true).
- [Release notes](https://github.com/mdlacasse/Owl/blob/main/RELEASE_NOTES.md) document changes in each version.

Copyright &copy; 2025-2026 - The Owlplanner [Authors](https://github.com/mdlacasse/Owl/blob/main/AUTHORS)

"""
)

st.markdown(credits_md)

st.markdown(
    """
#### :orange[Bugs and Feature Requests]
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/Owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool. &#x1F44D;

#### :orange[Privacy]
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

#### :orange[License]
This software is released under the
[Gnu General Public License v3](https://www.gnu.org/licenses/gpl-3.0.html#license-text).

#### :orange[Disclaimer]
This program is for educational purposes only and does not constitute financial advice.

"""
)
