"""

Owl/timelists
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Utility functions to read and check timelists.

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

"""

from datetime import date
import pandas as pd

from . import utils as u


# Expected headers in each excel sheet, one per individual.
_timeHorizonItems = [
    "year",
    "anticipated wages",
    "taxable ctrb",
    "401k ctrb",
    "Roth 401k ctrb",
    "IRA ctrb",
    "Roth IRA ctrb",
    "Roth conv",
    "big-ticket items",
]


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


def read(finput, inames, horizons, mylog, filename=None):
    """
    Read listed parameters from an excel spreadsheet or through
    a dictionary of dataframes through Pandas.
    Use one sheet for each individual with the following 9 columns:
    year, anticipated wages, taxable ctrb, 401k ctrb, Roth 401k ctrb,
    IRA ctrb, Roth IRA ctrb, Roth conv, and big-ticket items.
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

    return finput, timeLists, houseLists


def _checkColumns(df, iname, colList):
    """
    Ensure all columns in colList are present. Remove others.
    """
    # Drop all columns not in the list.
    # Make an explicit copy to avoid SettingWithCopyWarning
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")].copy()

    # Collect columns to drop
    cols_to_drop = [col for col in df.columns if col == "" or col not in colList]
    if cols_to_drop:
        df = df.drop(cols_to_drop, axis=1)

    # Check that all columns in the list are present.
    for item in colList:
        if item not in df.columns:
            raise ValueError(f"Column {item} not found for {iname}.")

    return df


def _conditionTimetables(dfDict, inames, horizons, mylog):
    """
    Make sure that time horizons contain all years up to life expectancy,
    and that values are positive (except big-ticket items).
    """
    timeLists = {}
    thisyear = date.today().year
    for i, iname in enumerate(inames):
        endyear = thisyear + horizons[i]

        if iname not in dfDict:
            raise ValueError(f"No sheet found for {iname}.")

        df = dfDict[iname]

        df = _checkColumns(df, iname, _timeHorizonItems)

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
                    if item != "big-ticket items" and year_rows[item].iloc[0] < 0:
                        raise ValueError(f"Item {item} for {iname} in year {year} is < 0.")

        if len(missing) > 0:
            mylog.vprint(f"Adding {len(missing)} missing years for {iname}: {missing}.")

        df.sort_values("year", inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists[iname] = df

        if df["year"].iloc[-1] != endyear - 1:
            raise ValueError(f"""Time horizon for {iname} too short.\n\t
It should end in {endyear}, not {df['year'].iloc[-1]}""")

    return timeLists


def _conditionHouseTables(dfDict, mylog):
    """
    Read debts and fixed assets from Household Financial Profile workbook.
    """
    houseDic = {}

    items = {"Debts" : _debtItems, "Fixed Assets": _fixedAssetItems}
    types = {"Debts" : _debtTypes, "Fixed Assets": _fixedAssetTypes}
    for page in items.keys():
        if page in dfDict:
            df = dfDict[page]
            df = _checkColumns(df, page, items[page])
            # Check categorical variables.
            isInList = df["type"].isin(types[page])
            df = df[isInList]

            # Convert percentage columns from decimal to percentage if needed
            # UI uses 0-100 range for percentages (e.g., 4.5 = 4.5%)
            # If Excel read percentage-formatted cells, values might be decimals (0.045)
            # Convert values < 1.0 to percentage format (multiply by 100)
            if page == "Debts" and "rate" in df.columns:
                # If rate values are less than 1, assume they're decimals (0.045 = 4.5%)
                # and convert to percentages (4.5) to match UI format (0-100 range)
                mask = (df["rate"] < 1.0) & (df["rate"] > 0)
                if mask.any():
                    df.loc[mask, "rate"] = df.loc[mask, "rate"] * 100.0
                    mylog.vprint(f"Converted {mask.sum()} rate value(s) from decimal to percentage in Debts table.")

            elif page == "Fixed Assets":
                # Convert rate and commission if they're decimals
                # Both should be in 0-100 range to match UI format
                if "rate" in df.columns:
                    mask = (df["rate"] < 1.0) & (df["rate"] > 0)
                    if mask.any():
                        df.loc[mask, "rate"] = df.loc[mask, "rate"] * 100.0
                        mylog.vprint(
                            f"Converted {mask.sum()} rate value(s) from decimal "
                            f"to percentage in Fixed Assets table."
                        )
                if "commission" in df.columns:
                    mask = (df["commission"] < 1.0) & (df["commission"] > 0)
                    if mask.any():
                        df.loc[mask, "commission"] = df.loc[mask, "commission"] * 100.0
                        mylog.vprint(
                            f"Converted {mask.sum()} commission value(s) from decimal "
                            f"to percentage in Fixed Assets table."
                        )
                # Validate and reset "year" column (acquisition year) if in the past
                if "year" in df.columns:
                    thisyear = date.today().year
                    mask = df["year"] < thisyear
                    if mask.any():
                        df.loc[mask, "year"] = thisyear
                        mylog.vprint(
                            f"Reset {mask.sum()} acquisition year value(s) to {thisyear} "
                            f"in Fixed Assets table (years cannot be in the past)."
                        )

            # Convert "active" column to boolean if it exists.
            # Excel may read booleans as strings ("True"/"False") or numbers (1/0).
            if "active" in df.columns:
                df["active"] = df["active"].apply(u.convert_to_bool).astype(bool)

            houseDic[page] = df
            mylog.vprint(f"Found {len(df)} valid row(s) in {page} table.")
        else:
            houseDic[page] = pd.DataFrame(columns=items[page])
            mylog.vprint(f"Table for {page} not found. Assuming empty table.")

    return houseDic


def conditionDebtsAndFixedAssetsDF(df, tableType):
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

    if df is None or df.empty:
        df = pd.DataFrame(columns=columnItems)

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
                def convert_to_string(val):
                    if pd.isna(val) or val is None:
                        return ""
                    if isinstance(val, list):
                        # If it's a list, join the elements (handles Streamlit data_editor edge cases)
                        # Filter out None/NaN values before joining
                        cleaned = [str(x) for x in val if x is not None and not pd.isna(x)]
                        return " ".join(cleaned) if cleaned else ""
                    return str(val)

                df[col] = df[col].apply(convert_to_string).astype(str)
                # Replace "nan" string with empty string
                df[col] = df[col].replace("nan", "").replace("None", "")
            elif col in int_cols:
                # Integer columns: convert to int64, fill NaN with 0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif col in float_cols:
                # Float columns: convert to float64, fill NaN with 0.0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float64")

    # For Fixed Assets, validate and reset "year" column if in the past
    if tableType == "Fixed Assets" and "year" in df.columns and len(df) > 0:
        thisyear = date.today().year
        mask = df["year"] < thisyear
        if mask.any():
            df.loc[mask, "year"] = thisyear

    return df


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
