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


def read(filename, inames, horizons, mylog):
    """
    Read listed parameters from an excel spreadsheet through Pandas.
    Use one sheet for each individual with the following columns.
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
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

    timeLists = []
    thisyear = date.today().year
    # Read all worksheets in memory but only process first n.
    try:
        dfDict = pd.read_excel(filename, sheet_name=None)
    except Exception as e:
        raise Exception('Could not read file %r: %s.' % (filename, e))

    mylog.vprint('Reading wages, contributions, conversions, and big-ticket items over time...')
    for i, iname in enumerate(inames):
        mylog.vprint('\tfor %s...' % iname)
        endyear = thisyear + horizons[i]
        if iname not in dfDict:
            raise RuntimeError('Could not find a sheet for %s in file %s.' % (iname, filename))

        df = dfDict[iname]
        # Only consider lines in proper year range.
        df = df[df['year'] >= thisyear]
        df = df[df['year'] < endyear]
        missing = 0
        for n in range(horizons[i]):
            year = thisyear + n
            if not (df[df['year'] == year]).any(axis=None):
                df.loc[len(df)] = [year, 0, 0, 0, 0, 0, 0, 0, 0]
                missing += 1

        if missing > 0:
            mylog.vprint('\tAdding %d missing year for %s.' % (missing, iname))

        df.sort_values('year', inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists.append({})
        # Transfer values from dataframe to lists.
        for item in timeHorizonItems:
            timeLists[i][item] = df[item].tolist()

    mylog.vprint('Successfully read time horizons from file "%s".' % filename)

    return timeLists


def check(inames, timeLists, horizons):
    """
    Make sure that time horizons contain all years up to life expectancy.
    """
    if len(inames) == 2:
        # Verify that both sheets start on the same year.
        if timeLists[0]['year'][0] != timeLists[1]['year'][0]:
            raise RuntimeError('Time horizons not starting on same year.')

    # Verify that year range covers life expectancy for each individual
    thisyear = date.today().year
    for i, iname in enumerate(inames):
        yend = thisyear + horizons[i]
        if timeLists[i]['year'][-1] < yend - 1:
            raise RuntimeError(
                'Time horizon for',
                iname,
                'is too short.\n\tIt should end in',
                yend,
                'but ends in',
                timeLists[i]['year'][-1],
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
                assert timeLists[i][item][n] >= 0, 'Item %s for %s in year %d is < 0.' % (
                    item,
                    iname,
                    timeLists[i]['year'][n],
                )

    return
