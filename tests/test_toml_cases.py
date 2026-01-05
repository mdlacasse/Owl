"""
Tests for TOML case file loading and execution.

Tests verify that example TOML case files can be loaded and executed
correctly with the Owl planner.

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

import os

import owlplanner as owl


def getHFP(exdir, case):
    wac = case.replace("Case_", "HFP_")
    wac = wac.replace("-spending", "")
    wac = wac.replace("-bequest", "")
    wac = os.path.join(exdir,  wac + ".xlsx")
    if os.path.exists(wac):
        return wac
    else:
        return ""


def test_allcases():
    exdir = "./examples/"
    for case in ["Case_john+sally",
                 "Case_jack+jill",
                 "Case_joe",
                 "Case_kim+sam-spending",
                 "Case_kim+sam-bequest"]:
        file = os.path.join(exdir, case)
        p = owl.readConfig(file)
        wac = getHFP(exdir, case)
        if wac != "":
            p.readContributions(wac)
        else:
            assert False
        p.resolve()


def test_historical():
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    wac = getHFP(exdir, case)
    if wac != "":
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runHistoricalRange(objective, options, 1969, 2023)


def test_MC():
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    wac = getHFP(exdir, case)
    if wac != "":
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runMC(objective, options, 20)
