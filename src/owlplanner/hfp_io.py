"""
Time horizon data validation and processing utilities.

This module provides utility functions to read and validate timelist data
from Excel files, including wage, contribution, and other time-based parameters.

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

from datetime import date
import numpy as np
import pandas as pd

from . import utils as u


# Expected headers in each excel sheet, one per individual (all required).
# Unused concepts should be filled with 0; see examples/HFP_template.xlsx.
_timeHorizonItems = [
    "year",
    "anticipated wages",
    "other inc",
    "net inv",
    "taxable ctrb",
    "401k ctrb",
    "Roth 401k ctrb",
    "IRA ctrb",
    "Roth IRA ctrb",
    "HSA ctrb",
    "Roth conv",
    "big-ticket items",
]
_requiredTimeHorizonItems = list(_timeHorizonItems)


_debtItems = [
    "active",
    "name",
    "type",
    "year",
    "term",
    "amount",
    "rate",
]


_debtTypes = [
    "loan",
    "mortgage",
]


_fixedAssetItems = [
    "active",
    "name",
    "type",
    "year",
    "basis",
    "value",
    "rate",
    "yod",
    "commission",
]


_fixedAssetTypes = [
    "collectibles",
    "fixed annuity",
    "precious metals",
    "real estate",
    "residence",
    "stocks",
]


def _convert_to_string(val):
    """
    Convert value to string for DataFrame string columns.
    Handles None, NaN, lists (e.g. from Streamlit data_editor).
    """
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, list):
        cleaned = [str(x) for x in val if x is not None and not pd.isna(x)]
        return " ".join(cleaned) if cleaned else ""
    return str(val)


def read(finput, inames, horizons, mylog, filename=None):
    """
    Read listed parameters from an excel spreadsheet or through
    a dictionary of dataframes through Pandas.
    Use one sheet for each individual with required columns (exact header text):
    year, anticipated wages, other inc, net inv, taxable ctrb, 401k ctrb,
    Roth 401k ctrb, IRA ctrb, Roth IRA ctrb, HSA ctrb, Roth conv,
    big-ticket items. Column order may vary; omitting a column is an error
    (use 0 for unused rows). Legacy header "other inc." is accepted as "other inc".
    "anticipated wages" is expected net of all contribution columns except
    "HSA ctrb" (see Plan.readHFP).
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
    Return a dictionary of dataframes by individual's names.

    Parameters
    ----------
    finput : file-like object, str, or dict
        Input file or dictionary of DataFrames
    inames : list
        List of individual names
    horizons : list
        List of time horizons
    mylog : logger
        Logger instance
    filename : str, optional
        Explicit filename for logging purposes. If provided, this will be used
        instead of trying to extract it from finput.
    """

    mylog.vprint("Reading wages, contributions, conversions, and big-ticket items over time...")

    if isinstance(finput, dict):
        dfDict = finput
        finput = "dictionary of DataFrames"
        streamName = "dictionary of DataFrames"
    else:
        if filename is not None:
            streamName = f"file '{filename}'"
        elif hasattr(finput, "name"):
            streamName = f"file '{finput.name}'"
        else:
            streamName = finput

        # Read all worksheets in memory but only process those with proper names.
        try:
            # dfDict = pd.read_excel(finput, sheet_name=None, usecols=_timeHorizonItems)
            dfDict = pd.read_excel(finput, sheet_name=None)
        except Exception as e:
            raise Exception(f"Could not read file {streamName}: {e}.") from e

    timeLists = _conditionTimetables(dfDict, inames, horizons, mylog)
    mylog.vprint(f"Successfully read time horizons from {streamName}.")

    houseLists = _conditionHouseTables(dfDict, mylog)
    mylog.vprint(f"Successfully read household tables from {streamName}.")

    return finput, timeLists, houseLists, dfDict


def _checkColumns(df, iname, colList, required_cols=None):
    """
    Ensure required columns are present. Keep allowed columns. Remove others.
    If required_cols is None, colList is treated as required.
    """
    # Drop all columns not in the list (and unnamed columns).
    # Make an explicit copy to avoid SettingWithCopyWarning
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")].copy()

    cols_to_drop = [col for col in df.columns if col == "" or col not in colList]
    if cols_to_drop:
        df = df.drop(cols_to_drop, axis=1)

    required = required_cols if required_cols is not None else colList
    missing = [item for item in required if item not in df.columns]
    if missing:
        raise ValueError(
            f"HFP sheet {iname!r} is missing required column(s): {missing}. "
            "Every listed header must be present; enter 0 where a concept does not apply. "
            "See examples/HFP_template.xlsx."
        )

    return df


def _conditionTimetables(dfDict, inames, horizons, mylog):
    """
    Make sure that time horizons contain all years up to life expectancy,
    and that values are positive (except big-ticket items and Roth conv).
    """
    timeLists = {}
    thisyear = date.today().year
    for i, iname in enumerate(inames):
        endyear = thisyear + horizons[i]

        if iname not in dfDict:
            raise ValueError(f"No sheet found for {iname}.")

        df = dfDict[iname]

        # Backward compatibility: old HFP files used "other inc."; normalize to "other inc"
        if "other inc." in df.columns and "other inc" not in df.columns:
            df = df.rename(columns={"other inc.": "other inc"})

        df = _checkColumns(df, iname, _timeHorizonItems, required_cols=_requiredTimeHorizonItems)

        # Ensure columns are in the correct order
        df = df[_timeHorizonItems].copy()

        # Only consider lines in proper year range. Go back 5 years for Roth maturation.
        df = df[df["year"] >= (thisyear - 5)]
        df = df[df["year"] < endyear]
        df = df.drop_duplicates("year")
        missing = []
        for n in range(-5, horizons[i]):
            year = thisyear + n
            year_rows = df[df["year"] == year]
            if year_rows.empty:
                # Create a new row as a dictionary to ensure correct column mapping.
                new_row = {col: 0 for col in _timeHorizonItems}
                new_row["year"] = year
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                missing.append(year)
            else:
                for item in _timeHorizonItems:
                    if year_rows[item].iloc[0] < 0:
                        if item == "big-ticket items":
                            continue
                        # Negative "Roth conv" is a useRothConvOverrides sentinel
                        # ("force conversion to 0 this year") and only applies to
                        # current/future years (n >= 0). The n < 0 tail feeds the
                        # 5-year seasoning rule and must stay non-negative.
                        if item == "Roth conv" and n >= 0:
                            continue
                        raise ValueError(f"Item {item} for {iname} in year {year} is < 0.")

        if len(missing) > 0:
            mylog.vprint(f"Adding {len(missing)} missing years for {iname}: {missing}.")

        df.sort_values("year", inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists[iname] = df

        last_expected = endyear - 1
        if df["year"].iloc[-1] != last_expected:
            raise ValueError(
                f"Time horizon for {iname} inconsistent after conditioning: last year is "
                f"{df['year'].iloc[-1]}, expected {last_expected} (inclusive end of plan for this person)."
            )

    return timeLists


def _conditionHouseTables(dfDict, mylog):
    """
    Read debts and fixed assets from Household Financial Profile workbook.
    """
    houseDic = {}

    items = {"Debts": _debtItems, "Fixed Assets": _fixedAssetItems}
    types = {"Debts": _debtTypes, "Fixed Assets": _fixedAssetTypes}
    for page in items.keys():
        if page in dfDict:
            df = dfDict[page]
            df = _checkColumns(df, page, items[page])
            # Check categorical variables.
            isInList = df["type"].isin(types[page])
            df = df[isInList]

            houseDic[page] = conditionDebtsAndFixedAssetsDF(df, page, mylog=mylog, convert_decimal_pct=True)
        else:
            houseDic[page] = pd.DataFrame(columns=items[page])
            mylog.vprint(f"Table for {page} not found. Assuming empty table.")

    return houseDic


_pctCols = {
    "Debts": ["rate"],
    "Fixed Assets": ["rate", "commission"],
}


def conditionDebtsAndFixedAssetsDF(df, tableType, mylog=None, convert_decimal_pct=False):
    """
    Condition a DataFrame for Debts or Fixed Assets by:
    - Creating an empty DataFrame with proper columns if df is None or empty
    - Resetting the index
    - Filling NaN values with 0 while preserving boolean columns (like "active")

    Parameters
    ----------
    df : pandas.DataFrame or None
        The DataFrame to condition, or None/empty to create a new empty DataFrame
    tableType : str
        Type of table: "Debts" or "Fixed Assets"
    mylog : logger, optional
        Logger instance for optional UI/log output
    convert_decimal_pct : bool, optional
        When True, percentage columns (see _pctCols) with values in (0, 1) are
        multiplied by 100 to convert Excel decimal fractions to percent format.

    Returns
    -------
    pandas.DataFrame
        Conditioned DataFrame with proper columns and no NaN values (except boolean columns default to True)
    """
    # Map table type to column items
    items = {"Debts": _debtItems, "Fixed Assets": _fixedAssetItems}
    if tableType not in items:
        raise ValueError(f"tableType must be 'Debts' or 'Fixed Assets', got '{tableType}'")

    columnItems = items[tableType]

    df = u.ensure_dataframe(df, pd.DataFrame(columns=columnItems))

    df = df.copy()
    df.reset_index(drop=True, inplace=True)

    # Ensure all required columns exist
    for col in columnItems:
        if col not in df.columns:
            df[col] = None

    # Only keep the columns we need, in the correct order
    df = df[columnItems].copy()

    # Define which columns are integers vs floats
    if tableType == "Debts":
        int_cols = ["year", "term"]
        float_cols = ["amount", "rate"]
    else:  # Fixed Assets
        int_cols = ["year", "yod"]
        float_cols = ["basis", "value", "rate", "commission"]

    # Handle empty DataFrame by setting dtypes directly
    if len(df) == 0:
        dtype_dict = {}
        dtype_dict["active"] = bool
        for col in ["name", "type"]:
            dtype_dict[col] = "object"  # string columns
        for col in int_cols:
            dtype_dict[col] = "int64"
        for col in float_cols:
            dtype_dict[col] = "float64"
        df = df.astype(dtype_dict)
    else:
        # Fill NaN values and ensure proper types for non-empty DataFrame
        for col in df.columns:
            if col == "active":
                # Ensure "active" column is boolean, handling strings/numbers from Excel
                df[col] = df[col].apply(u.convert_to_bool).astype(bool)
            elif col in ["name", "type"]:
                # String columns: ensure they are strings, not lists
                # Streamlit data_editor can return lists for string columns in some cases
                df[col] = df[col].apply(_convert_to_string).astype(str)
                # Replace "nan" string with empty string
                df[col] = df[col].replace("nan", "").replace("None", "")
            elif col in int_cols:
                # Integer columns: convert to int64, fill NaN with 0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif col in float_cols:
                # Float columns: convert to float64, fill NaN with 0.0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float64")

    # Convert decimal percentages to percent format if requested (e.g. 0.045 → 4.5)
    if convert_decimal_pct and len(df) > 0 and tableType in _pctCols:
        for col in _pctCols[tableType]:
            if col in df.columns:
                mask = (df[col] > 0) & (df[col] < 1)
                if mask.any():
                    df.loc[mask, col] = df.loc[mask, col] * 100.0
                    if mylog is not None:
                        mylog.vprint(
                            f"Converted {mask.sum()} {col} value(s) from decimal to percentage in {tableType} table."
                        )

    # For Fixed Assets, validate and reset "year" column if in the past
    if tableType == "Fixed Assets" and "year" in df.columns and len(df) > 0:
        thisyear = date.today().year
        mask = df["year"] < thisyear
        if mask.any():
            df.loc[mask, "year"] = thisyear
            if mylog is not None:
                mylog.vprint(
                    f"Reset {mask.sum()} reference year value(s) to {thisyear} "
                    f"in Fixed Assets table (years cannot be in the past)."
                )

    if mylog is not None:
        mylog.vprint(f"Found {len(df)} valid row(s) in {tableType} table.")

    return df


def build_hfp_dataframes(plan):
    """
    Reconstruct HFP time lists and household tables from a plan's internal arrays.

    This is used to export an HFP workbook from a Plan that was populated
    programmatically (i.e., without readHFP or setContributions). Values are
    read from the plan's arrays (omega_in, other_inc_in, netinv_in, Lambda_in,
    kappa_ijn, myRothX_in), including the 5 lead-in years preceding the current
    year that feed the Roth 5-year maturation rule.

    Note that the internal arrays merge '401k ctrb' with 'IRA ctrb'
    (tax-deferred) and 'Roth 401k ctrb' with 'Roth IRA ctrb' (tax-free);
    the original column split cannot be recovered. Merged amounts are written
    to the '401k ctrb' and 'Roth IRA ctrb' columns respectively.

    Parameters
    ----------
    plan : Plan
        The plan to extract HFP data from.

    Returns
    -------
    tuple of (dict, dict)
        (timeLists, houseLists): timeLists maps each individual's name to a
        DataFrame with _timeHorizonItems columns; houseLists contains the
        'Debts' and 'Fixed Assets' DataFrames.
    """
    # Rows 0..4 are the 5 lead-in years before thisyear; row 5+n = plan year n.
    # This mirrors the layout produced by read() and consumed by Plan.setContributions().
    lead_in = 5
    thisyear = date.today().year
    timeLists = {}
    for i, iname in enumerate(plan.inames):
        h = int(plan.horizons[i])
        years = list(range(thisyear - lead_in, thisyear + h))
        df = pd.DataFrame(0.0, index=range(len(years)), columns=_timeHorizonItems)
        df["year"] = years
        for n in range(h):
            row = lead_in + n
            df.at[row, "anticipated wages"] = float(plan.omega_in[i, n])
            df.at[row, "other inc"] = float(plan.other_inc_in[i, n])
            df.at[row, "net inv"] = float(plan.netinv_in[i, n])
            df.at[row, "big-ticket items"] = float(plan.Lambda_in[i, n])
            df.at[row, "taxable ctrb"] = float(plan.kappa_ijn[i, 0, n])
            df.at[row, "401k ctrb"] = float(plan.kappa_ijn[i, 1, n])
            df.at[row, "Roth IRA ctrb"] = float(plan.kappa_ijn[i, 2, n])
            df.at[row, "HSA ctrb"] = float(plan.kappa_ijn[i, 3, n])
            df.at[row, "Roth conv"] = float(plan.myRothX_in[i, n])
        # Lead-in years live in the last 5 slots of kappa_ijn and myRothX_in.
        for r in range(lead_in):
            slot = plan.N_n + r
            df.at[r, "taxable ctrb"] = float(plan.kappa_ijn[i, 0, slot])
            df.at[r, "401k ctrb"] = float(plan.kappa_ijn[i, 1, slot])
            df.at[r, "Roth IRA ctrb"] = float(plan.kappa_ijn[i, 2, slot])
            df.at[r, "HSA ctrb"] = float(plan.kappa_ijn[i, 3, slot])
            df.at[r, "Roth conv"] = float(plan.myRothX_in[i, slot])
        timeLists[iname] = df

    houseLists = {
        "Debts": plan.houseLists.get("Debts", pd.DataFrame(columns=_debtItems)),
        "Fixed Assets": plan.houseLists.get("Fixed Assets", pd.DataFrame(columns=_fixedAssetItems)),
    }

    return timeLists, houseLists


def time_lists_agree(a, b):
    """
    Check whether two time-list dictionaries represent the same values.

    Columns that are merged in the plan's internal arrays ('401k ctrb' +
    'IRA ctrb', and 'Roth 401k ctrb' + 'Roth IRA ctrb') are compared as sums.
    Used by Plan.saveHFP() to detect time lists that are stale with respect
    to the plan's arrays (e.g., when a plan was populated by writing directly
    into the arrays).

    Parameters
    ----------
    a, b : dict
        Dictionaries mapping individual names to time-list DataFrames.

    Returns
    -------
    bool
        True if both represent the same values.
    """
    if a is None or b is None or set(a.keys()) != set(b.keys()):
        return False

    plainCols = [
        "anticipated wages",
        "other inc",
        "net inv",
        "taxable ctrb",
        "HSA ctrb",
        "Roth conv",
        "big-ticket items",
    ]
    mergedCols = [("401k ctrb", "IRA ctrb"), ("Roth 401k ctrb", "Roth IRA ctrb")]
    allCols = plainCols + [col for pair in mergedCols for col in pair] + ["year"]
    for iname in a:
        dfa, dfb = a[iname], b[iname]
        if any(col not in df.columns for df in (dfa, dfb) for col in allCols):
            return False
        if len(dfa) != len(dfb) or not np.array_equal(dfa["year"].to_numpy(), dfb["year"].to_numpy()):
            return False
        for col in plainCols:
            if not np.allclose(dfa[col].to_numpy(dtype=float), dfb[col].to_numpy(dtype=float)):
                return False
        for col1, col2 in mergedCols:
            suma = dfa[col1].to_numpy(dtype=float) + dfa[col2].to_numpy(dtype=float)
            sumb = dfb[col1].to_numpy(dtype=float) + dfb[col2].to_numpy(dtype=float)
            if not np.allclose(suma, sumb):
                return False

    return True


def getTableTypes(tableType):
    """
    Get the list of valid types for a given table type.

    Parameters
    ----------
    tableType : str
        Type of table: "Debts" or "Fixed Assets"

    Returns
    -------
    list
        List of valid types for the specified table
    """
    types = {"Debts": _debtTypes, "Fixed Assets": _fixedAssetTypes}
    if tableType not in types:
        raise ValueError(f"tableType must be 'Debts' or 'Fixed Assets', got '{tableType}'")

    return types[tableType]
