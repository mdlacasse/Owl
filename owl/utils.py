'''

Owl/utils
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

This file for handling error messages.

Copyright -- Martin-D. Lacasse (2024)

Disclaimer: This program comes with no guarantee. Use at your own risk.

'''

######################################################################
import sys
import numpy as np


######################################################################
verbose = True


def setVerbose(val, ret=False):
    '''
    Set verbose to True if you want the module to be chatty.
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
    Conditional print depending on the value of the verbose variable.
    '''
    global verbose
    if verbose:
        print(*args)
    sys.stdout.flush()

    return


def xprint(*args, **kwargs):
    '''
    Print and exit. Use to print error messages on stderr.
    The exit() used throws an exception.
    '''
    print("ERROR:", *args, file=sys.stderr, **kwargs)
    print("Exiting...", file=sys.stderr)
    sys.stderr.flush()
    sys.exit(-1)


def d(value, f=0) -> str:
    '''
    Return a string formatting number in $ currency.
    '''
    mystr = '${:,.' + str(f) + 'f}'

    return mystr.format(value)


def pc(value, f=1, mul=100) -> str:
    '''
    Return a string formatting number in percent.
    '''
    mystr = '{:.' + str(f) + 'f}%'

    return mystr.format(mul * value)


def rescale(vals, fac):
    '''
    Rescale elements of a list or array by factor fac.
    '''
    if isinstance(vals, (float, int)) or isinstance(vals, np.ndarray):
        return vals * fac
    else:
        for i in range(len(vals)):
            vals[i] *= fac

    return vals


def getUnits(units) -> int:
    '''
    Return proper factor for units.
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


def krond(a, b) -> int:
    '''
    Kronecker scalar delta function.
    '''
    if a == b:
        return 1
    else:
        return 0


def getGitRevisionShortHash() -> str:
    '''
    Return git version.
    '''
    import subprocess

    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()


def roundCents(n, decimals=2):
    '''
    Round values in numpy array down to second decimal.
    '''
    multiplier = 10**decimals

    return np.floor(n * multiplier + 0.5) / multiplier
