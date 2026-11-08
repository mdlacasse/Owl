"""
A case file with CRLF line endings loads whole, from a path and from an upload.

toml 0.10.2's string parser, which read uploads, dropped a triple-quoted string and every key
after it on CRLF text, with no error; Create Case then failed with "'basic_info'" (#248).
A Git-for-Windows checkout writes the examples with CRLF.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from io import BytesIO, StringIO
from pathlib import Path

import pytest

from owlplanner.config import load_toml

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("Case_*.toml"))


@pytest.mark.toml
@pytest.mark.parametrize("case", EXAMPLES, ids=lambda p: p.stem)
def test_crlf_case_loads_whole(case, tmp_path):
    text = case.read_text(encoding="utf-8")
    assert "\r" not in text
    crlf = text.replace("\n", "\r\n")
    expected, _, _ = load_toml(StringIO(text))

    path = tmp_path / case.name
    path.write_bytes(crlf.encode("utf-8"))
    for source in (StringIO(crlf), BytesIO(crlf.encode("utf-8")), str(path)):
        diconf, _, _ = load_toml(source)
        assert diconf == expected, type(source).__name__
