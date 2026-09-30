"""
The UI must solve with the solver options it would save.

getSolveParameters() builds the options a UI run passes to Plan.solve(); ui_to_config() builds
the solver_options written to the case file. They translate the UI-only settings separately, so a
setting handled in one and forgotten in the other was ignored by the run, or dropped from the file
saved after it (issue #156: stopRothConversions and includeMedicarePartD).

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

import glob

import pytest

import ui.sskeys as kz
from owlplanner.config.toml_io import load_toml
from owlplanner.config.ui_bridge import config_to_ui, ui_to_config

EXAMPLES = sorted(glob.glob("examples/Case_*.toml"))


def _run_and_file_options(monkeypatch, uidic):
    monkeypatch.setattr(kz, "getCaseKey", uidic.get)
    _, run_opts = kz.getSolveParameters()
    return run_opts, ui_to_config(uidic)["solver_options"]


@pytest.mark.toml
@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.split("Case_")[1][:-5])
def test_ui_run_uses_the_options_it_saves(monkeypatch, path):
    run_opts, file_opts = _run_and_file_options(monkeypatch, config_to_ui(load_toml(path)[0]))
    assert run_opts == file_opts


@pytest.mark.toml
def test_ui_run_passes_stop_roth_conversions_and_part_d(monkeypatch):
    uidic = config_to_ui(load_toml("examples/Case_john+sally.toml")[0])
    uidic["stopRothConversionsEnabled"] = True
    uidic["stopRothConversions"] = 2040
    uidic["includeMedicarePartD"] = False
    run_opts, file_opts = _run_and_file_options(monkeypatch, uidic)
    assert run_opts["stopRothConversions"] == 2040
    assert run_opts["includeMedicarePartD"] is False
    assert run_opts == file_opts
