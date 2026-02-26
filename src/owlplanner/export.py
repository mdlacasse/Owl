"""
Excel and summary export utilities for Plan.

This module provides plan_to_excel, plan_to_csv, and summary construction
functions. Formatting helpers are also exported for use by saveContributions.

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

import numpy as np
import pandas as pd
from io import StringIO
from os.path import isfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

from . import config
from . import utils as u
from . import tax2026 as tx
from .rate_models.constants import RATE_DISPLAY_NAMES_SHORT


def _save_workbook(wb, basename, overwrite, mylog):
    """Save workbook to file with overwrite prompt."""
    if Path(basename).suffixes == []:
        fname = "workbook" + "_" + basename + ".xlsx"
    else:
        fname = basename

    if not overwrite and isfile(fname):
        mylog.print(f'File "{fname}" already exists.')
        key = input("Overwrite? [Ny] ")
        if key != "y":
            mylog.print("Skipping save and returning.")
            return None

    for _ in range(3):
        try:
            mylog.vprint(f'Saving plan as "{fname}".')
            wb.save(fname)
            break
        except PermissionError:
            mylog.print(f'Failed to save "{fname}": Permission denied.')
            key = input("Close file and try again? [Yn] ")
            if key == "n":
                break
        except Exception as e:
            raise Exception(f"Unanticipated exception {e}.") from e

    return None


def _format_spreadsheet(ws, ftype):
    """Beautify spreadsheet worksheet with appropriate number formatting."""
    if ftype == "currency":
        fstring = "$#,##0_);[Red]($#,##0)"
    elif ftype == "percent2":
        fstring = "#.00%"
    elif ftype == "percent1":
        fstring = "#.0%"
    elif ftype == "percent0":
        fstring = "#0%"
    elif ftype == "pct_value":
        fstring = "0.00"
    elif ftype == "summary":
        for col in ws.columns:
            column = col[0].column_letter
            width = max(len(str(col[0].value)) + 20, 40)
            ws.column_dimensions[column].width = width
            return None
    else:
        raise RuntimeError(f"Unknown format: {ftype}.")

    for cell in ws[1] + ws["A"]:
        cell.style = "Pandas"
    for col in ws.columns:
        column = col[0].column_letter
        width = max(len(str(col[0].value)) + 4, 10)
        ws.column_dimensions[column].width = width
        if column == "A":
            for cell in col:
                cell.number_format = "0"
        else:
            for cell in col:
                cell.number_format = fstring

    return None


def _format_debts_sheet(ws):
    """Format Debts sheet with appropriate column formatting."""
    from openpyxl.utils import get_column_letter

    for cell in ws[1]:
        cell.style = "Pandas"

    header_row = ws[1]
    col_map = {}
    for idx, cell in enumerate(header_row, start=1):
        col_letter = get_column_letter(idx)
        col_name = str(cell.value).lower() if cell.value else ""
        col_map[col_letter] = col_name
        width = max(len(str(cell.value)) + 4, 10)
        ws.column_dimensions[col_letter].width = width

    for col_letter, col_name in col_map.items():
        if col_name in ["year", "term"]:
            fstring = "0"
        elif col_name in ["rate"]:
            fstring = "#,##0.00"
        elif col_name in ["amount"]:
            fstring = "$#,##0_);[Red]($#,##0)"
        else:
            continue

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column_letter == col_letter:
                    cell.number_format = fstring

    return None


def _format_fixed_assets_sheet(ws):
    """Format Fixed Assets sheet with appropriate column formatting."""
    from openpyxl.utils import get_column_letter

    for cell in ws[1]:
        cell.style = "Pandas"

    header_row = ws[1]
    col_map = {}
    for idx, cell in enumerate(header_row, start=1):
        col_letter = get_column_letter(idx)
        col_name = str(cell.value).lower() if cell.value else ""
        col_map[col_letter] = col_name
        width = max(len(str(cell.value)) + 4, 10)
        ws.column_dimensions[col_letter].width = width

    for col_letter, col_name in col_map.items():
        if col_name in ["yod"]:
            fstring = "0"
        elif col_name in ["rate", "commission"]:
            fstring = "#,##0.00"
        elif col_name in ["basis", "value"]:
            fstring = "$#,##0_);[Red]($#,##0)"
        else:
            continue

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column_letter == col_letter:
                    cell.number_format = fstring

    return None


def _format_federal_income_tax_sheet(ws):
    """Format Federal Income Tax sheet with currency for $ columns and percent for SS % taxed."""
    from openpyxl.utils import get_column_letter

    for cell in ws[1]:
        cell.style = "Pandas"

    header_row = ws[1]
    col_map = {}
    for idx, cell in enumerate(header_row, start=1):
        col_letter = get_column_letter(idx)
        col_name = str(cell.value) if cell.value else ""
        col_map[col_letter] = col_name
        width = max(len(str(cell.value)) + 4, 10)
        ws.column_dimensions[col_letter].width = width

    currency_fmt = "$#,##0_);[Red]($#,##0)"
    percent_fmt = "#.0%"
    for col_letter, col_name in col_map.items():
        if col_name == "year":
            fstring = "0"
        elif col_name == "SS % taxed":
            fstring = percent_fmt
        else:
            fstring = currency_fmt

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column_letter == col_letter:
                    cell.number_format = fstring

    return None


def build_summary_dic(plan, N=None):
    """Return dictionary containing summary of plan values."""
    if N is None:
        N = plan.N_n
    if not (0 < N <= plan.N_n):
        raise ValueError(f"Value N={N} is out of reange")

    now = plan.year_n[0]
    dic = {}
    dic["Case name"] = plan._name
    dic["Net yearly spending basis" + 26 * " ."] = u.d(plan.g_n[0] / plan.xi_n[0])
    dic[f"Net spending for year {now}"] = u.d(plan.g_n[0])
    dic[f"Net spending remaining in year {now}"] = u.d(plan.g_n[0] * plan.yearFracLeft)

    totSpending = np.sum(plan.g_n[:N], axis=0)
    totSpendingNow = np.sum(plan.g_n[:N] / plan.gamma_n[:N], axis=0)
    dic[" Total net spending"] = f"{u.d(totSpendingNow)}"
    dic["[Total net spending]"] = f"{u.d(totSpending)}"

    totRoth = np.sum(plan.x_in[:, :N], axis=(0, 1))
    totRothNow = np.sum(np.sum(plan.x_in[:, :N], axis=0) / plan.gamma_n[:N], axis=0)
    dic[" Total Roth conversions"] = f"{u.d(totRothNow)}"
    dic["[Total Roth conversions]"] = f"{u.d(totRoth)}"

    taxPaid = np.sum(plan.T_n[:N], axis=0)
    taxPaidNow = np.sum(plan.T_n[:N] / plan.gamma_n[:N], axis=0)
    dic[" Total tax paid on ordinary income"] = f"{u.d(taxPaidNow)}"
    dic["[Total tax paid on ordinary income]"] = f"{u.d(taxPaid)}"
    for t in range(plan.N_t):
        taxPaid = np.sum(plan.T_tn[t, :N], axis=0)
        taxPaidNow = np.sum(plan.T_tn[t, :N] / plan.gamma_n[:N], axis=0)
        tname = tx.taxBracketNames[t] if t < len(tx.taxBracketNames) else f"Bracket {t}"
        dic[f"»  Subtotal in tax bracket {tname}"] = f"{u.d(taxPaidNow)}"
        dic[f"» [Subtotal in tax bracket {tname}]"] = f"{u.d(taxPaid)}"

    penaltyPaid = np.sum(plan.P_n[:N], axis=0)
    penaltyPaidNow = np.sum(plan.P_n[:N] / plan.gamma_n[:N], axis=0)
    dic["»  Subtotal in early withdrawal penalty"] = f"{u.d(penaltyPaidNow)}"
    dic["» [Subtotal in early withdrawal penalty]"] = f"{u.d(penaltyPaid)}"

    taxPaid = np.sum(plan.U_n[:N], axis=0)
    taxPaidNow = np.sum(plan.U_n[:N] / plan.gamma_n[:N], axis=0)
    dic[" Total tax paid on gains and dividends"] = f"{u.d(taxPaidNow)}"
    dic["[Total tax paid on gains and dividends]"] = f"{u.d(taxPaid)}"

    taxPaid = np.sum(plan.J_n[:N], axis=0)
    taxPaidNow = np.sum(plan.J_n[:N] / plan.gamma_n[:N], axis=0)
    dic[" Total net investment income tax paid"] = f"{u.d(taxPaidNow)}"
    dic["[Total net investment income tax paid]"] = f"{u.d(taxPaid)}"

    taxPaid = np.sum(plan.m_n[:N] + plan.M_n[:N], axis=0)
    taxPaidNow = np.sum((plan.m_n[:N] + plan.M_n[:N]) / plan.gamma_n[:N], axis=0)
    dic[" Total Medicare premiums paid"] = f"{u.d(taxPaidNow)}"
    dic["[Total Medicare premiums paid]"] = f"{u.d(taxPaid)}"

    totDebtPayments = np.sum(plan.debt_payments_n[:N], axis=0)
    if totDebtPayments > 0:
        totDebtPaymentsNow = np.sum(plan.debt_payments_n[:N] / plan.gamma_n[:N], axis=0)
        dic[" Total debt payments"] = f"{u.d(totDebtPaymentsNow)}"
        dic["[Total debt payments]"] = f"{u.d(totDebtPayments)}"

    if plan.N_i == 2 and plan.n_d < plan.N_n and N == plan.N_n:
        p_j = plan.partialEstate_j * (1 - plan.phi_j)
        p_j[1] *= 1 - plan.nu
        nx = plan.n_d - 1
        ynx = plan.year_n[nx]
        ynxNow = 1.0 / plan.gamma_n[nx + 1]
        totOthers = np.sum(p_j)
        q_j = plan.partialEstate_j * plan.phi_j
        totSpousal = np.sum(q_j)
        iname_s = plan.inames[plan.i_s]
        iname_d = plan.inames[plan.i_d]
        dic["Year of partial bequest"] = f"{ynx}"
        dic[f" Sum of spousal transfer to {iname_s}"] = f"{u.d(ynxNow * totSpousal)}"
        dic[f"[Sum of spousal transfer to {iname_s}]"] = f"{u.d(totSpousal)}"
        dic[f"»  Spousal transfer to {iname_s} - taxable"] = f"{u.d(ynxNow * q_j[0])}"
        dic[f"» [Spousal transfer to {iname_s} - taxable]"] = f"{u.d(q_j[0])}"
        dic[f"»  Spousal transfer to {iname_s} - tax-def"] = f"{u.d(ynxNow * q_j[1])}"
        dic[f"» [Spousal transfer to {iname_s} - tax-def]"] = f"{u.d(q_j[1])}"
        dic[f"»  Spousal transfer to {iname_s} - tax-free"] = f"{u.d(ynxNow * q_j[2])}"
        dic[f"» [Spousal transfer to {iname_s} - tax-free]"] = f"{u.d(q_j[2])}"
        dic[f" Sum of post-tax non-spousal bequest from {iname_d}"] = f"{u.d(ynxNow * totOthers)}"
        dic[f"[Sum of post-tax non-spousal bequest from {iname_d}]"] = f"{u.d(totOthers)}"
        dic[f"»  Post-tax non-spousal bequest from {iname_d} - taxable"] = f"{u.d(ynxNow * p_j[0])}"
        dic[f"» [Post-tax non-spousal bequest from {iname_d} - taxable]"] = f"{u.d(p_j[0])}"
        dic[f"»  Post-tax non-spousal bequest from {iname_d} - tax-def"] = f"{u.d(ynxNow * p_j[1])}"
        dic[f"» [Post-tax non-spousal bequest from {iname_d} - tax-def]"] = f"{u.d(p_j[1])}"
        dic[f"»  Post-tax non-spousal bequest from {iname_d} - tax-free"] = f"{u.d(ynxNow * p_j[2])}"
        dic[f"» [Post-tax non-spousal bequest from {iname_d} - tax-free]"] = f"{u.d(p_j[2])}"

    if N == plan.N_n:
        estate = np.sum(plan.b_ijn[:, :, plan.N_n], axis=0)
        heirsTaxLiability = estate[1] * plan.nu
        estate[1] *= 1 - plan.nu
        endyear = plan.year_n[-1]
        lyNow = 1.0 / plan.gamma_n[-1]
        debts = plan.remaining_debt_balance
        savingsEstate = np.sum(estate)
        totEstate = savingsEstate - debts + plan.fixed_assets_bequest_value

        dic["Year of final bequest"] = f"{endyear}"
        dic[" Total after-tax value of final bequest"] = f"{u.d(lyNow * totEstate)}"
        dic["» After-tax value of savings assets"] = f"{u.d(lyNow * savingsEstate)}"
        dic["» Fixed assets liquidated at end of plan"] = f"{u.d(lyNow * plan.fixed_assets_bequest_value)}"
        dic["» With heirs assuming tax liability of"] = f"{u.d(lyNow * heirsTaxLiability)}"
        dic["» After paying remaining debts of"] = f"{u.d(lyNow * debts)}"
        dic["[Total after-tax value of final bequest]"] = f"{u.d(totEstate)}"
        dic["[» After-tax value of savings assets]"] = f"{u.d(savingsEstate)}"
        dic["[» Fixed assets liquidated at end of plan]"] = f"{u.d(plan.fixed_assets_bequest_value)}"
        dic["[» With heirs assuming tax liability of]"] = f"{u.d(heirsTaxLiability)}"
        dic["[» After paying remaining debts of]"] = f"{u.d(debts)}"
        dic["»  Post-tax final bequest account value - taxable"] = f"{u.d(lyNow * estate[0])}"
        dic["» [Post-tax final bequest account value - taxable]"] = f"{u.d(estate[0])}"
        dic["»  Post-tax final bequest account value - tax-def"] = f"{u.d(lyNow * estate[1])}"
        dic["» [Post-tax final bequest account value - tax-def]"] = f"{u.d(estate[1])}"
        dic["»  Post-tax final bequest account value - tax-free"] = f"{u.d(lyNow * estate[2])}"
        dic["» [Post-tax final bequest account value - tax-free]"] = f"{u.d(estate[2])}"

    dic["Case starting date"] = str(plan.startDate)
    dic["Cumulative inflation factor at end of final year"] = f"{plan.gamma_n[N]:.2f}"
    for i in range(plan.N_i):
        dic[f"{plan.inames[i]:>14}'s life horizon"] = f"{now} -> {now + plan.horizons[i] - 1}"
        dic[f"{plan.inames[i]:>14}'s years planned"] = f"{plan.horizons[i]}"

    dic["Case name"] = plan._name
    dic["Number of decision variables"] = str(plan.A.nvars)
    dic["Number of constraints"] = str(plan.A.ncons)
    dic["Convergence"] = plan.convergenceType
    dic["Case executed on"] = str(plan._timestamp)

    return dic


def build_summary_list(plan, N=None):
    """Return summary as list of key: value strings."""
    dic = build_summary_dic(plan, N)
    return [f"{key}: {value}" for key, value in dic.items()]


def build_summary_string(plan, N=None):
    """Return summary as formatted string."""
    dic = build_summary_dic(plan, N)
    string = "Synopsis\n"
    for key, value in dic.items():
        string += f"{key:>77}: {value}\n"
    return string


def plan_to_excel(plan, overwrite=False, *, basename=None, saveToFile=True, with_config="no"):
    """
    Build Excel workbook from plan. Optionally save to file.

    Returns wb if saveToFile is False, else None.
    """
    wb = Workbook()

    def add_config_sheet(position):
        if with_config == "no":
            return
        if with_config not in {"no", "first", "last"}:
            raise ValueError(f"Invalid with_config option '{with_config}'.")
        if position != with_config:
            return

        config_buffer = StringIO()
        config.saveConfig(plan, config_buffer, plan.mylog)
        config_buffer.seek(0)

        ws_config = wb.create_sheet(title="Config (.toml)", index=0 if position == "first" else None)
        for row_idx, line in enumerate(config_buffer.getvalue().splitlines(), start=1):
            ws_config.cell(row=row_idx, column=1, value=line)

    def fillsheet(sheet, dic, datatype, op=lambda x: x):
        rawData = {}
        rawData["year"] = plan.year_n
        if datatype == "currency":
            for key in dic:
                rawData[key] = u.roundCents(op(dic[key]))
        else:
            for key in dic:
                rawData[key] = op(dic[key])
        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            sheet.append(row)
        _format_spreadsheet(sheet, datatype)

    add_config_sheet("first")

    ws = wb.active
    ws.title = "Income"
    incomeDic = {
        "net spending": plan.g_n,
        "taxable ord. income": plan.G_n,
        "taxable gains/divs": plan.Q_n,
        "Tax bills + Med.": plan.T_n + plan.U_n + plan.m_n + plan.M_n + plan.J_n,
    }
    fillsheet(ws, incomeDic, "currency")

    cashFlowDic = {
        "net spending": plan.g_n,
        "all wages": np.sum(plan.omega_in, axis=0),
        "all other inc": np.sum(plan.other_inc_in, axis=0),
        "all pensions": np.sum(plan.piBar_in, axis=0),
        "all soc sec": np.sum(plan.zetaBar_in, axis=0),
        "all BTI's": np.sum(plan.Lambda_in, axis=0),
        "FA ord inc": plan.fixed_assets_ordinary_income_n,
        "FA cap gains": plan.fixed_assets_capital_gains_n,
        "FA tax-free": plan.fixed_assets_tax_free_n,
        "debt pmts": -plan.debt_payments_n,
        "all wdrwls": np.sum(plan.w_ijn, axis=(0, 1)),
        "all deposits": -np.sum(plan.d_in, axis=0),
        "ord taxes": -plan.T_n - plan.J_n,
        "div taxes": -plan.U_n,
        "Medicare": -plan.m_n - plan.M_n,
    }
    ws = wb.create_sheet("Cash Flow")
    fillsheet(ws, cashFlowDic, "currency")

    srcDic = {
        "wages": plan.sources_in["wages"],
        "other inc": plan.sources_in["other inc"],
        "social sec": plan.sources_in["ssec"],
        "pension": plan.sources_in["pension"],
        "txbl acc wdrwl": plan.sources_in["txbl acc wdrwl"],
        "RMDs": plan.sources_in["RMD"],
        "+distributions": plan.sources_in["+dist"],
        "Roth conv": plan.sources_in["RothX"],
        "tax-free wdrwl": plan.sources_in["tax-free wdrwl"],
        "big-ticket items": plan.sources_in["BTI"],
    }
    for i in range(plan.N_i):
        ws = wb.create_sheet(plan.inames[i] + "'s Sources")
        fillsheet(ws, srcDic, "currency", op=lambda x, i=i: x[i])

    householdSrcDic = {
        "FA ord inc": plan.sources_in["FA ord inc"],
        "FA cap gains": plan.sources_in["FA cap gains"],
        "FA tax-free": plan.sources_in["FA tax-free"],
        "debt pmts": plan.sources_in["debt pmts"],
    }
    ws = wb.create_sheet("Household Sources")
    fillsheet(ws, householdSrcDic, "currency", op=lambda x: x[0])

    accDic = {
        "taxable bal": plan.b_ijn[:, 0, :-1],
        "taxable ctrb": plan.kappa_ijn[:, 0, :plan.N_n],
        "taxable dep": plan.d_in,
        "taxable wdrwl": plan.w_ijn[:, 0, :],
        "tax-deferred bal": plan.b_ijn[:, 1, :-1],
        "tax-deferred ctrb": plan.kappa_ijn[:, 1, :plan.N_n],
        "tax-deferred wdrwl": plan.w_ijn[:, 1, :],
        "(included RMDs)": plan.rmd_in[:, :],
        "Roth conv": plan.x_in,
        "tax-free bal": plan.b_ijn[:, 2, :-1],
        "tax-free ctrb": plan.kappa_ijn[:, 2, :plan.N_n],
        "tax-free wdrwl": plan.w_ijn[:, 2, :],
    }
    for i in range(plan.N_i):
        ws = wb.create_sheet(plan.inames[i] + "'s Accounts")
        fillsheet(ws, accDic, "currency", op=lambda x, i=i: x[i])
        lastRow = [
            plan.year_n[-1] + 1,
            plan.b_ijn[i][0][-1],
            0, 0, 0,
            plan.b_ijn[i][1][-1],
            0, 0, 0, 0,
            plan.b_ijn[i][2][-1],
            0, 0,
        ]
        ws.append(lastRow)
        _format_spreadsheet(ws, "currency")

    TxDic = {}
    for t in range(plan.N_t):
        tname = tx.taxBracketNames[t] if t < len(tx.taxBracketNames) else f"Bracket {t}"
        TxDic[tname] = plan.T_tn[t, :]
    TxDic["total"] = plan.T_n
    TxDic["NIIT"] = plan.J_n
    TxDic["LTCG"] = plan.U_n
    TxDic["10% penalty"] = plan.P_n
    ss_n = np.sum(plan.zetaBar_in, axis=0)
    TxDic["SS % taxed"] = np.where(ss_n > 0, plan.Psi_n, 0)
    ws = wb.create_sheet("Federal Income Tax")
    rawData = {"year": plan.year_n}
    for key in TxDic:
        if key == "SS % taxed":
            rawData[key] = TxDic[key]
        else:
            rawData[key] = u.roundCents(TxDic[key])
    df = pd.DataFrame(rawData)
    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)
    _format_federal_income_tax_sheet(ws)

    jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2}
    kDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}
    year_n = np.append(plan.year_n, [plan.year_n[-1] + 1])
    for i in range(plan.N_i):
        ws = wb.create_sheet(plan.inames[i] + "'s Allocations")
        rawData = {}
        rawData["year"] = year_n
        for jkey in jDic:
            for kkey in kDic:
                rawData[jkey + "/" + kkey] = 100 * plan.alpha_ijkn[i, jDic[jkey], kDic[kkey], :]
        df = pd.DataFrame(rawData)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)
        _format_spreadsheet(ws, "pct_value")

    ratesDic = {name: 100 * plan.tau_kn[k] for k, name in enumerate(RATE_DISPLAY_NAMES_SHORT)}
    ws = wb.create_sheet("Rates")
    fillsheet(ws, ratesDic, "pct_value")

    ws = wb.create_sheet("Summary")
    summary_key = "SUMMARY ==========================================================================="
    rawData = {summary_key: build_summary_list(plan, plan.N_n)}
    df = pd.DataFrame(rawData)
    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)
    _format_spreadsheet(ws, "summary")
    add_config_sheet("last")

    if saveToFile:
        if basename is None:
            basename = plan._name
        _save_workbook(wb, basename, overwrite, plan.mylog)
        return None

    return wb


def plan_to_csv(plan, basename, mylog):
    """Build plan data and write to CSV file."""
    planData = {}
    planData["year"] = plan.year_n
    planData["net spending"] = plan.g_n
    planData["taxable ord. income"] = plan.G_n
    planData["taxable gains/divs"] = plan.Q_n
    planData["Tax bills + Med."] = plan.T_n + plan.U_n + plan.m_n + plan.M_n + plan.J_n
    planData["all wages"] = np.sum(plan.omega_in, axis=0)
    planData["all other inc"] = np.sum(plan.other_inc_in, axis=0)
    planData["all pensions"] = np.sum(plan.piBar_in, axis=0)
    planData["all soc sec"] = np.sum(plan.zetaBar_in, axis=0)
    planData["all BTI's"] = np.sum(plan.Lambda_in, axis=0)
    planData["FA ord inc"] = plan.fixed_assets_ordinary_income_n
    planData["FA cap gains"] = plan.fixed_assets_capital_gains_n
    planData["FA tax-free"] = plan.fixed_assets_tax_free_n
    planData["debt pmts"] = -plan.debt_payments_n
    planData["all wdrwls"] = np.sum(plan.w_ijn, axis=(0, 1))
    planData["all deposits"] = -np.sum(plan.d_in, axis=0)
    planData["ord taxes"] = -plan.T_n - plan.J_n
    planData["div taxes"] = -plan.U_n
    planData["Medicare"] = -plan.m_n - plan.M_n

    for i in range(plan.N_i):
        planData[plan.inames[i] + " txbl bal"] = plan.b_ijn[i, 0, :-1]
        planData[plan.inames[i] + " txbl dep"] = plan.d_in[i, :]
        planData[plan.inames[i] + " txbl wrdwl"] = plan.w_ijn[i, 0, :]
        planData[plan.inames[i] + " tx-def bal"] = plan.b_ijn[i, 1, :-1]
        planData[plan.inames[i] + " tx-def ctrb"] = plan.kappa_ijn[i, 1, :plan.N_n]
        planData[plan.inames[i] + " tx-def wdrl"] = plan.w_ijn[i, 1, :]
        planData[plan.inames[i] + " (RMD)"] = plan.rmd_in[i, :]
        planData[plan.inames[i] + " Roth conv"] = plan.x_in[i, :]
        planData[plan.inames[i] + " tx-free bal"] = plan.b_ijn[i, 2, :-1]
        planData[plan.inames[i] + " tx-free ctrb"] = plan.kappa_ijn[i, 2, :plan.N_n]
        planData[plan.inames[i] + " tax-free wdrwl"] = plan.w_ijn[i, 2, :]
        planData[plan.inames[i] + " big-ticket items"] = plan.Lambda_in[i, :]

    for k, name in enumerate(RATE_DISPLAY_NAMES_SHORT):
        planData[name] = 100 * plan.tau_kn[k]

    df = pd.DataFrame(planData)

    while True:
        try:
            fname = "worksheet" + "_" + basename + ".csv"
            df.to_csv(fname)
            break
        except PermissionError:
            mylog.print(f'Failed to save "{fname}": Permission denied.')
            key = input("Close file and try again? [Yn] ")
            if key == "n":
                break
        except Exception as e:
            raise Exception(f"Unanticipated exception: {e}.") from e

    return None
