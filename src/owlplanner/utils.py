'''

Owl/utils

This file contains for handling error messages.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.

'''

######################################################################
import sys
import numpy as np


######################################################################
verbose = True


def _setVerbose(val, ret=False):
    '''
    Set verbose to True if you want the module to be chatty,
    or False to make it silent.
    '''
    global verbose
    prevState = verbose
    verbose = val
    vprint("Setting verbose to", verbose)

    if ret:
        return prevState

    return


def vprint(*args, **kwargs):
    '''
    Conditional printing depending on the value of the verbose variable
    previously set.
    '''
    global verbose
    if verbose:
        print(*args)
    sys.stdout.flush()

    return


def xprint(*args, **kwargs):
    '''
    Print message and exit. Use to print error messages on stderr.
    The exit() used throws an exception in an interactive environment.
    '''
    print("ERROR:", *args, file=sys.stderr, **kwargs)
    print("Exiting...", file=sys.stderr)
    sys.stderr.flush()
    sys.exit(-1)


def d(value, f=0, latex=False) -> str:
    '''
    Return a string formatting value in $ currency.
    Number of decimals controlled by `f` which defaults to 0.
    '''
    if np.isnan(value):
        return 'NaN'

    if latex:
        mystr = '\\${:,.' + str(f) + 'f}'
    else:
        mystr = '${:,.' + str(f) + 'f}'

    return mystr.format(value)


def pc(value, f=1, mul=100) -> str:
    '''
    Return a string formatting decimal value in percent.
    Number of decimals of percent controlled by `f` which defaults to 1.
    '''
    mystr = '{:.' + str(f) + 'f}%'

    return mystr.format(mul * value)


def rescale(vals, fac):
    '''
    Rescale all elements of a list or a NumPy array by factor fac.
    '''
    if isinstance(vals, (float, int)) or isinstance(vals, np.ndarray):
        return vals * fac
    else:
        for i in range(len(vals)):
            vals[i] *= fac

    return vals


def getUnits(units) -> int:
    '''
    Translate multiplication factor for units as expressed by an abbreviation
    expressed in a string. Returns an integer.
    '''
    if units is None or units == 1 or units == '1' or units == 'one':
        fac = 1
    elif units in {'k', 'K'}:
        fac = 1000
    elif units in {'m', 'M'}:
        fac = 1000000
    else:
        xprint('Unknown units', units)

    return fac


# Could be a one-line lambda function:
# krond = lambda a, b: 1 if a == b else 0
def krond(a, b) -> int:
    '''
    Kronecker integer delta function.
    '''
    return (1 if a == b else 0)


def roundCents(values, decimals=2):
    '''
    Round values in NumPy array down to second decimal.
    Using fix which is floor towards zero.
    Default is to round to cents (decimals = 2).
    '''
    multiplier = 10**decimals

    arr = np.fix(values * multiplier + 0.5) / multiplier
    # Remove negative zero-like values.
    arr = np.where((-.009 < arr) & (arr <= 0), 0, arr)

    return arr
