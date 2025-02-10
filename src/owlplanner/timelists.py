"""

Owl/timelists
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

Utility functions to read and check timelists.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

from datetime import date
import pandas as pd


# Expected headers in each excel sheet, one per individual.
timeHorizonItems = [
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


def read(finput, inames, horizons, mylog):
    """
    Read listed parameters from an excel spreadsheet or through
    a dictionary of dataframes through Pandas.
    Use one sheet for each individual with the following 9 columns:
    year, anticipated wages, taxable ctrb, 401k ctrb, Roth 401k ctrb,
    IRA ctrb, Roth IRA ctrb, Roth conv, and big-ticket items.
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
    Returs a dictionary of dataframes by individual's names.
    """

    mylog.vprint("Reading wages, contributions, conversions, and big-ticket items over time...")

    if isinstance(finput, dict):
        timeLists = finput
        finput = "dictionary of DataFrames"
        streamName = "dictionary of DataFrames"
    else:
        # Read all worksheets in memory but only process those with proper names.
        try:
            dfDict = pd.read_excel(finput, sheet_name=None)
        except Exception as e:
            raise Exception("Could not read file %r: %s." % (finput, e))
        streamName = "file '%s'" % finput

        timeLists = condition(dfDict, inames, horizons, mylog)

    mylog.vprint("Successfully read time horizons from %s." % streamName)

    return finput, timeLists


def condition(dfDict, inames, horizons, mylog):
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

        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        for col in df.columns:
            if col == "" or col not in timeHorizonItems:
                df.drop(col, axis=1)

        for item in timeHorizonItems:
            if item not in df.columns:
                raise ValueError(f"Item {item} not found for {iname}.")

        # Only consider lines in proper year range.
        df = df[df["year"] >= thisyear]
        df = df[df["year"] < endyear]
        missing = []
        for n in range(horizons[i]):
            year = thisyear + n
            if not (df[df["year"] == year]).any(axis=None):
                df.loc[len(df)] = [year, 0, 0, 0, 0, 0, 0, 0, 0]
                missing.append(year)
            else:
                for item in timeHorizonItems:
                    if item != "big-ticket items" and df[item].iloc[n] < 0:
                        raise ValueError("Item %s for %s in year %d is < 0." % (item, iname, df["year"].iloc[n]))

        if len(missing) > 0:
            mylog.vprint("Adding %d missing years for %s: %r." % (len(missing), iname, missing))

        df.sort_values("year", inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists[iname] = df

        if df["year"].iloc[-1] != endyear - 1:
            raise ValueError(
                "Time horizon for",
                iname,
                "is too short.\n\tIt should end in",
                endyear,
                "but ends in",
                df["year"].iloc[-1],
            )

    return timeLists
