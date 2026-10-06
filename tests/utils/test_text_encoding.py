"""
Text files are read and written as UTF-8 on every platform.

Without an explicit encoding, open(), Path.open(), read_text() and write_text() use the platform's
locale encoding: UTF-8 on macOS and Linux, cp1252 on Windows. Owl's sources, data and case files
are UTF-8 (TOML requires it), so on Windows a file holding a character outside cp1252 failed to
read, and a case saved there could not be read back on another machine.

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

import ast
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
_DIRS = ("src", "ui", "tests")


def _mode(call):
    """The mode argument of an open() call, or "r" when absent; None when it is not a literal."""
    if len(call.args) >= 2:
        arg = call.args[1]
    else:
        arg = next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
    if arg is None:
        return "r"
    return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


def _is_unencoded_text_io(node):
    """True for an open()/Path.open()/read_text()/write_text() call in text mode without encoding=."""
    if not isinstance(node, ast.Call) or any(kw.arg == "encoding" for kw in node.keywords):
        return False
    f = node.func
    if isinstance(f, ast.Name) and f.id == "open":
        mode = _mode(node)
    elif isinstance(f, ast.Attribute) and f.attr == "open" and not (
        isinstance(f.value, ast.Name) and f.value.id in ("os", "gzip", "zipfile", "Image", "webbrowser")
    ):
        # Path.open(mode): its mode is the first argument.
        arg = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
        mode = "r" if arg is None else (arg.value if isinstance(arg, ast.Constant) else None)
    elif isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
        mode = "r"
    else:
        return False
    return mode is not None and "b" not in mode  # binary, or a mode we cannot read statically, is fine


def _unencoded_text_io(tree):
    for node in ast.walk(tree):
        if _is_unencoded_text_io(node):
            yield node.lineno


def test_text_io_names_its_encoding():
    offenders = []
    for d in _DIRS:
        for path in sorted((_REPO / d).rglob("*.py")):
            if ".venv" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            offenders += [f"{path.relative_to(_REPO)}:{line}" for line in _unencoded_text_io(tree)]
    assert not offenders, "text I/O without encoding='utf-8':\n  " + "\n  ".join(offenders)
