'''

Python file for handling error messages.

Copyright -- Martin-D. Lacasse (2023)

Disclaimer: This program comes with no guarantee. Use at your own risk.

'''

######################################################################
import sys


######################################################################
verbose = False


def setVerbose(val):
    '''
    Set verbose to True if you want the module to be chatty.
    '''
    global verbose
    prevState = verbose
    verbose = val
    vprint("Setting verbose to", verbose)

    return prevState


def vprint(*args, **kwargs):
    '''
    Conditional print depending on the value of the verbose variable.
    '''
    global verbose
    if verbose:
        print(*args)

    return


def xprint(*args, **kwargs):
    '''
    Print and exit. Use to print error messages on stderr.
    '''
    print("ERROR:", *args, file=sys.stderr, **kwargs)
    print("Exiting...", file=sys.stderr)
    sys.exit(-1)


def d(value, f=0):
    '''
    Return a string formatting number in $ currency.
    '''
    mystr = '${:,.' + str(f) + 'f}'

    return mystr.format(value)


def pc(value, f=1, mul=100):
    '''
    Return a string formatting number in percent.
    '''
    mystr = '{:.' + str(f) + 'f}%'

    return mystr.format(mul * value)


def rescale(vals, fac):
    '''
    Rescale elements of a list by factor fac.
    '''
    for i in range(len(vals)):
        vals[i] *= fac

    return


def getUnits(units):
    '''
    Return proper factor for units.
    '''
    if units is None or units == 1 or units =='1':
        fac = 1
    elif units in {'k', 'K'}:
        fac = 1000
    elif units in {'m', 'M'}:
        fac = 1000000
    else:
        xprint('Unknown units', units)

    return fac

def krond(a, b):
    '''
    Kronecker scalar delta function.
    '''
    if a == b:
        return 1
    else:
        return 0
