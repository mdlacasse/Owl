## Credits and Acknowledgements
- Original author:
Martin-D. Lacasse (mdlacasse)

- Contributors (alphabetical order):
 Robert E. Anderson (NH-RedAnt) for bug fixes and suggestions,
 Clark Jefcoat (hubcity) for fruitful interactions,
 kg333 for fixing an error in Docker's instructions,
 John Leonard (jleonard99) for great suggestions, website, improved logger,
 stochastic rate generation, reproducibility, testing, and more to come...
 Benjamin Quinn (blquinn) for improvements and bug fixes,
 Dale Seng (sengsational) for great insights, testing, bug fixes, and suggestions,
 Eric Stratten (mechovision) for expanded IRS joint table,
 Josh Williams (noimjosh) for Docker image code,
 Gene Wood (gene1wood) for improvements and bug fixes.

- Greg Grothaus for developing [ssa.tools](https://ssa.tools) and providing an integration with Owl.
- [MOSEK](https://mosek.com) for providing a free license of their commercial software for Owl's
deployment on the Community Cloud server.
- [Aswath Damodaran](https://pages.stern.nyu.edu/~adamodar/) for sharing his analyses of historical rates.
- [HiGHS](https://highs.dev) for the open-source HiGHS linear and mixed-integer optimization
solver, used from Python via [highspy](https://pypi.org/project/highspy/).
- Owl planner relies on the following [Python](https://python.org) packages:
    [click](https://click.palletsprojects.com),
    [highspy](https://pypi.org/project/highspy),
    [loguru](https://github.com/Delgan/loguru),
    [Matplotlib](https://matplotlib.org),
    [Numpy](https://numpy.org),
    [odfpy](https://pypi.org/project/odfpy),
    [openpyxl](https://openpyxl.readthedocs.io),
    [Pandas](https://pandas.pydata.org),
    [Plotly](https://plotly.com),
    [pydantic](https://docs.pydantic.dev),
    [Scipy](https://scipy.org),
    [Seaborn](https://seaborn.pydata.org),
    [toml](https://toml.io),
and [Streamlit](https://streamlit.io) for the front-end.
- Optional [Jupyter](https://jupyter.org) supports the tutorial notebooks in the `notebooks/`
directory; it is not installed by default. From a source checkout, use
`pip install -e ".[notebooks]"` (see [INSTALL.md](https://github.com/mdlacasse/Owl/blob/main/INSTALL.md)).
- Owl image is from [freepik](https://freepik.com).
