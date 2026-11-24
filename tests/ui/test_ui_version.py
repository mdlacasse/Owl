"""
The About page names the engine: the version, plus the git commit when there is one.

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

import owlplanner as owl
import owlplanner.version as owl_version
import ui.owlbridge as owb


def test_engine_label_includes_the_commit_from_a_checkout(monkeypatch):
    monkeypatch.setattr(owl_version, "engine_commit", lambda: "5afa4a6b")
    assert owb.engine_label() == f"{owl.__version__} (commit 5afa4a6b)"


def test_engine_label_is_the_version_alone_without_git(monkeypatch):
    """A pip install has no commit to report, so nothing is appended."""
    monkeypatch.setattr(owl_version, "engine_commit", lambda: None)
    assert owb.engine_label() == owl.__version__
