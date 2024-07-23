'''
Utility functions to read and check timelists.
'''

from datetime import date
import pandas as pd

from owl import utils as u


def read(filename, N_i, horizons):
    '''
    Read listed parameters from an excel spreadsheet through pandas.
    Use one sheet for each individual with the following columns.
    Supports xls, xlsx, xlsm, xlsb, odf, ods, and odt file extensions.
    '''

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
        'big ticket items',
    ]

    timeLists = []
    names = []
    thisyear = date.today().year
    # Read all worksheets in memory but only process first n.
    dfDict = pd.read_excel(filename, sheet_name=None)
    i = 0
    for name in dfDict.keys():
        u.vprint('Reading time horizon for', name, '...')
        names.append(name)
        endyear = thisyear + horizons[i]
        df = dfDict[name]
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
            u.vprint('\tAdding %d missing year for %s.' % (missing, name))

        df.sort_values('year', inplace=True)
        # Replace empty (NaN) cells with 0 value.
        df.fillna(0, inplace=True)

        timeLists.append({})
        # Transfer values from dataframe to lists
        for item in timeHorizonItems:
            timeLists[i][item] = df[item].tolist()

        i += 1
        if i >= N_i:
            break

    u.vprint('Successfully read time horizons from file', filename)

    return names, timeLists


def check(names, timeLists, horizons):
    '''
    Make sure that time horizons contain all years up to life expectancy.
    '''
    if len(names) == 2:
        # Verify that both sheets start on the same year.
        if timeLists[0]['year'][0] != timeLists[1]['year'][0]:
            u.xprint('Time horizons not starting on same year.')

    # Verify that year range covers life expectancy for each individual
    thisyear = date.today().year
    for i in range(len(names)):
        yend = thisyear + horizons[i]
        if timeLists[i]['year'][-1] < yend - 1:
            u.xprint(
                'Time horizon for',
                names[i],
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
    for i in range(len(names)):
        for n in range(horizons[i]):
            for item in timeHorizonItems:
                assert timeLists[i][item][n] >= 0, 'Item %s for %s in year %d is < 0.' % (
                    item,
                    names[i],
                    n,
                )

    return
