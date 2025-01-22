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


def read(finput, inames, horizons, mylog):
    """
    Read listed parameters from an excel spreadsheet or through
    a dictionary of dataframes through Pandas.
    Use one sheet for each individual with the following columns.
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
    Returs a list of dataframes.
    """

    # Expected headers in each excel sheet, one per individual.
    timeHorizonItems = [
        'year',
        'anticipated wages',
        'ctrb taxable',
        'ctrb 401k',
        'ctrb Roth 401k',
        'ctrb IRA',
        'ctrb Roth IRA',
        'Roth X',
        'big-ticket items',
    ]

    timeLists = {}
    thisyear = date.today().year
    if isinstance(finput, dict):
        dfDict = finput
        finput = 'dictionary of DataFrames'
        filename = 'dictionary of DataFrames'
    else:
        # Read all worksheets in memory but only process those with proper names.
        try:
            dfDict = pd.read_excel(finput, sheet_name=None)
        except Exception as e:
            raise Exception('Could not read file %r: %s.' % (finput, e))
        filename = "file '%s'" % finput

    mylog.vprint('Reading wages, contributions, conversions, and big-ticket items over time...')
    for i, iname in enumerate(inames):
        mylog.vprint('\tfor %s...' % iname)
        endyear = thisyear + horizons[i]
        if iname not in dfDict:
            raise RuntimeError("Could not find a sheet for %s in %s." % (iname, filename))

        df = dfDict[iname]
        # Check all columns.
        for col in timeHorizonItems:
            if col not in df.columns:
                raise ValueError('Missing column %s in dataframe for %s.' % (col, iname))

        # Only consider lines in proper year range.
        df = df[df['year'] >= thisyear]
        df = df[df['year'] < endyear]
        missing = []
        for n in range(horizons[i]):
            year = thisyear + n
            if not (df[df['year'] == year]).any(axis=None):
                df.loc[len(df)] = [year, 0, 0, 0, 0, 0, 0, 0, 0]
                missing.append(year)

        if len(missing) > 0:
            mylog.vprint('\tAdding %d missing years for %s: %r.' % (len(missing), iname, missing))

        df.sort_values('year', inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists[iname] = df

    mylog.vprint("Successfully read time horizons from %s." % filename)

    return finput, timeLists


def check(inames, timeLists, horizons):
    """
    Make sure that time horizons contain all years up to life expectancy.
    """
    if len(inames) == 2:
        # Verify that both sheets start on the same year.
        if timeLists[inames[0]]['year'].iloc[0] != timeLists[inames[1]]['year'].iloc[0]:
            raise RuntimeError('Time horizons not starting on same year.')

    # Verify that year range covers life expectancy for each individual
    thisyear = date.today().year
    for i, iname in enumerate(inames):
        yend = thisyear + horizons[i]
        if timeLists[iname]['year'].iloc[-1] < yend - 1:
            raise RuntimeError(
                'Time horizon for',
                iname,
                'is too short.\n\tIt should end in',
                yend,
                'but ends in',
                timeLists[iname]['year'].iloc[-1],
            )

    timeHorizonItems = [
        'year',
        'anticipated wages',
        'ctrb taxable',
        'ctrb 401k',
        'ctrb Roth 401k',
        'ctrb IRA',
        'ctrb Roth IRA',
        'Roth X',
    ]

    # Verify that all numbers except bti are positive.
    for i, iname in enumerate(inames):
        for item in timeHorizonItems:
            for n in range(horizons[i]):
                assert timeLists[iname][item].iloc[n] >= 0, 'Item %s for %s in year %d is < 0.' % (
                    item,
                    iname,
                    timeLists[iname]['year'].iloc[n],
                )

    return
