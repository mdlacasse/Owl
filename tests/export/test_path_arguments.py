"""
Every file a plan reads or writes can be named with a pathlib.Path as well as a str (#190).

owlcli run passed a Path to saveWorkbook, and adding "_real" to it as if it were text stopped the
save of a real-dollar workbook. The same mistake sat in the other entry points.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import pathlib

import pytest

import owlplanner as owl

_CASE = pathlib.Path(__file__).resolve().parents[2] / "examples" / "Case_bill.toml"


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    p = owl.readConfig(str(_CASE), verbose=False, logstreams=[io.StringIO()])
    p.setRates("conservative")
    p.solve(p.objective, {**p.solverOptions, "withMedicare": "None"})
    assert p.caseStatus == "solved"
    return p


@pytest.mark.toml
def test_config_round_trip(solved, tmp_path):
    solved.saveConfig(tmp_path / "case_bill_copy")
    p = owl.readConfig(tmp_path / "case_bill_copy.toml", verbose=False, logstreams=[io.StringIO()],
                       loadHFP=False)
    assert p.inames == solved.inames


@pytest.mark.toml
@pytest.mark.parametrize("name, expected", [("bill", "HFP_bill.xlsx"), ("mine.xlsx", "mine.xlsx")])
def test_hfp_round_trip(solved, tmp_path, monkeypatch, name, expected):
    monkeypatch.chdir(tmp_path)
    solved.saveHFP(pathlib.Path(name), overwrite=True)
    assert (tmp_path / expected).is_file()
    assert solved.readHFP(tmp_path / expected)


@pytest.mark.toml
@pytest.mark.parametrize("real", [False, True])
@pytest.mark.parametrize("name, expected", [("bill", "workbook_bill{}.xlsx"), ("out.xlsx", "out{}.xlsx")])
def test_workbook(solved, tmp_path, monkeypatch, real, name, expected):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(solved, "worksheetRealDollars", real)
    saved = solved.saveWorkbook(basename=pathlib.Path(name), overwrite=True)
    assert saved == expected.format("_real" if real else "")
    assert (tmp_path / saved).is_file()


@pytest.mark.toml
def test_csv(solved, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    solved.saveWorkbookCSV(pathlib.Path("bill"))
    assert (tmp_path / "worksheet_bill.csv").is_file()
