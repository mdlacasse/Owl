"""
Shim keeping pytest-benchmark working under pytest 9.2.

pytest-benchmark 5.3.0 reads the private ``node._nodeid`` (fixture.py), which pytest 9.2.0
replaced with ``_id``; the public ``nodeid`` is unchanged. Without the shim every benchmark
errors at setup with ``AttributeError: 'Function' object has no attribute '_nodeid'``.
Upstream: ionelmc/pytest-benchmark#321 and PR #323. Delete this file once a pytest-benchmark
release reads ``nodeid``.

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


def pytest_collection_modifyitems(items):
    for item in items:
        if not hasattr(item, "_nodeid"):
            item._nodeid = item.nodeid
