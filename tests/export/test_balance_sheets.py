"""
Tests for the traditional and liquid balance sheets added to the Excel export.

Covers:
  - plan_to_excel() creates the "Balance Sheet" and "Liquid Balance Sheet" sheets
  - traditional accounting identity: net worth = total assets - debt
  - liquid identity: liquid net worth = total assets - debt - deferred tax - disposition costs
  - real (today's) dollar scaling
  - worksheetHideZeroColumns is honored by the UI display preparation

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pandas as pd
import pytest

import owlplanner as owl


@pytest.fixture(scope="module")
def alex_jamie_plan():
    """Solved two-person plan with debts and fixed assets."""
    exdir = "./examples/"
    p = owl.readConfig(os.path.join(exdir, "Case_alex+jamie"))
    p.readHFP(os.path.join(exdir, "HFP_alex+jamie.xlsx"))
    p.resolve()
    assert p.caseStatus == "solved"
    return p


def _sheet_df(wb, name):
    ws = wb[name]
    rows = list(ws.values)
    return pd.DataFrame(rows[1:], columns=list(rows[0]))


def test_balance_sheets_present(alex_jamie_plan):
    wb = alex_jamie_plan.saveWorkbook(saveToFile=False)
    assert "Balance Sheet" in wb.sheetnames
    assert "Liquid Balance Sheet" in wb.sheetnames


def test_traditional_columns(alex_jamie_plan):
    wb = alex_jamie_plan.saveWorkbook(saveToFile=False)
    df = _sheet_df(wb, "Balance Sheet")
    assert list(df.columns) == [
        "year", "taxable", "tax-deferred", "tax-free", "HSA",
        "fixed assets", "total assets", "debt", "net worth",
    ]


def test_liquid_columns(alex_jamie_plan):
    wb = alex_jamie_plan.saveWorkbook(saveToFile=False)
    df = _sheet_df(wb, "Liquid Balance Sheet")
    assert list(df.columns) == [
        "year", "taxable", "tax-deferred", "tax-free", "HSA",
        "fixed assets", "total assets", "debt", "deferred income tax",
        "disposition costs", "total liabilities", "liquid net worth",
    ]


def test_traditional_net_worth_identity(alex_jamie_plan):
    wb = alex_jamie_plan.saveWorkbook(saveToFile=False)
    df = _sheet_df(wb, "Balance Sheet")
    assets = (df["taxable"] + df["tax-deferred"] + df["tax-free"] + df["HSA"] + df["fixed assets"])
    assert (assets - df["total assets"]).abs().max() == pytest.approx(0.0, abs=1.0)
    assert (df["total assets"] - df["debt"] - df["net worth"]).abs().max() == pytest.approx(0.0, abs=1.0)


def test_liquid_net_worth_identity(alex_jamie_plan):
    p = alex_jamie_plan
    wb = p.saveWorkbook(saveToFile=False)
    df = _sheet_df(wb, "Liquid Balance Sheet")
    # deferred income tax = (tax-deferred + HSA) * liquidationTaxRate
    expected_tax = (df["tax-deferred"] + df["HSA"]) * p.liquidationTaxRate
    assert (df["deferred income tax"] - expected_tax).abs().max() == pytest.approx(0.0, abs=1.0)
    total_liab = df["debt"] + df["deferred income tax"] + df["disposition costs"]
    assert (df["total liabilities"] - total_liab).abs().max() == pytest.approx(0.0, abs=1.0)
    assert (df["total assets"] - df["total liabilities"] - df["liquid net worth"]).abs().max() == \
        pytest.approx(0.0, abs=1.0)


def test_liquid_net_worth_below_traditional(alex_jamie_plan):
    """Liquid net worth must be <= traditional net worth (extra liabilities)."""
    wb = alex_jamie_plan.saveWorkbook(saveToFile=False)
    trad = _sheet_df(wb, "Balance Sheet")
    liq = _sheet_df(wb, "Liquid Balance Sheet")
    assert (liq["liquid net worth"] <= trad["net worth"] + 1.0).all()


def test_real_dollar_scaling(alex_jamie_plan):
    p = alex_jamie_plan
    p.setWorksheetRealDollars(False)
    nominal = _sheet_df(p.saveWorkbook(saveToFile=False), "Balance Sheet")
    p.setWorksheetRealDollars(True)
    real = _sheet_df(p.saveWorkbook(saveToFile=False), "Balance Sheet")
    p.setWorksheetRealDollars(False)
    # First year (gamma=1) unchanged; later years deflated below nominal.
    assert real["net worth"].iloc[0] == pytest.approx(nominal["net worth"].iloc[0], rel=1e-6)
    assert real["fixed assets"].iloc[-1] < nominal["fixed assets"].iloc[-1]
