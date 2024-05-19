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
    # Force the use of the verbose variable through this following call.
    vprint("Setting verbose to", val)

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
