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
    "name",
    "type",
    "basis",
    "value",
    "rate",
    "yod",
    "commission",
]


_fixedAssetTypes = [
    "annuity",
    "collectibles",
    "precious metals",
    "real estate",
    "residence",
    "stocks",
]


def read(finput, inames, horizons, mylog):
    """
    Read listed parameters from an excel spreadsheet or through
    a dictionary of dataframes through Pandas.
    Use one sheet for each individual with the following 9 columns:
    year, anticipated wages, taxable ctrb, 401k ctrb, Roth 401k ctrb,
    IRA ctrb, Roth IRA ctrb, Roth conv, and big-ticket items.
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
    Return a dictionary of dataframes by individual's names.
    """

    mylog.vprint("Reading wages, contributions, conversions, and big-ticket items over time...")

    if isinstance(finput, dict):
        dfDict = finput
        finput = "dictionary of DataFrames"
        streamName = "dictionary of DataFrames"
    else:
        # Read all worksheets in memory but only process those with proper names.
        try:
            # dfDict = pd.read_excel(finput, sheet_name=None, usecols=_timeHorizonItems)
            dfDict = pd.read_excel(finput, sheet_name=None)
        except Exception as e:
            raise Exception(f"Could not read file {finput}: {e}.") from e
        streamName = f"file '{finput}'"

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
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    for col in df.columns:
        if col == "" or col not in colList:
            df.drop(col, axis=1, inplace=True)

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

        # Only consider lines in proper year range. Go back 5 years for Roth maturation.
        df = df[df["year"] >= (thisyear - 5)]
        df = df[df["year"] < endyear]
        df = df.drop_duplicates("year")
        missing = []
        for n in range(-5, horizons[i]):
            year = thisyear + n
            year_rows = df[df["year"] == year]
            if year_rows.empty:
                df.loc[len(df)] = [year, 0, 0, 0, 0, 0, 0, 0, 0]
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
            houseDic[page] = df[isInList]
            mylog.vprint(f"Found {len(df)} valid row(s) in {page} table.")
        else:
            houseDic[page] = pd.DataFrame(columns=items[page])
            mylog.vprint(f"Table for {page} not found. Assuming empty table.")

    return houseDic
