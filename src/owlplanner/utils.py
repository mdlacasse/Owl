"""

Owl/utils

This file contains functions for handling data.

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

"""

######################################################################
import numpy as np


def d(value, f=0, latex=False) -> str:
    """
    Return a string formatting value in $ currency.
    Number of decimals controlled by `f` which defaults to 0.
    """
    if np.isnan(value):
        return "NaN"

    if latex:
        mystr = "\\${:,." + str(f) + "f}"
    else:
        mystr = "${:,." + str(f) + "f}"

    return mystr.format(value)


def pc(value, f=1, mul=100) -> str:
    """
    Return a string formatting decimal value in percent.
    Number of decimals of percent controlled by `f` which defaults to 1.
    """
    mystr = "{:." + str(f) + "f}%"

    return mystr.format(mul * value)


def rescale(vals, fac):
    """
    Rescale all elements of a list or a NumPy array by factor fac.
    """
    if isinstance(vals, (float, int)) or isinstance(vals, np.ndarray):
        return vals * fac
    else:
        for i in range(len(vals)):
            vals[i] *= fac

    return vals


def getUnits(units) -> int:
    """
    Translate multiplication factor for units as expressed by an abbreviation
    expressed in a string. Returns an integer.
    """
    if units is None or units == 1 or units == "1" or units == "one":
        fac = 1
    elif units in {"k", "K"}:
        fac = 1000
    elif units in {"m", "M"}:
        fac = 1000000
    else:
        raise ValueError(f"Unknown units {units}.")

    return fac


# Next two functions could be a one-line lambda functions.
# e.g., krond = lambda a, b: 1 if a == b else 0
def krond(a, b) -> int:
    """
    Kronecker integer delta function.
    """
    return 1 if a == b else 0


def heavyside(x) -> int:
    """
    Heavyside step function.
    """
    return 1 if x >= 0 else 0


def roundCents(values, decimals=2):
    """
    Round values in NumPy array down to second decimal.
    Using fix which is floor towards zero.
    Default is to round to cents (decimals = 2).
    """
    multiplier = 10**decimals

    newvalues = values * multiplier + 0.5 * np.sign(values)

    arr = np.fix(newvalues) / multiplier
    # Remove negative zero-like values.
    arr = np.where((-0.009 < arr) & (arr <= 0), 0, arr)

    return arr


def parseDobs(dobs):
    """
    Parse a list of dates and return int32 arrays of year, months, days.
    """
    icount = len(dobs)
    yobs = []
    mobs = []
    tobs = []
    for i in range(icount):
        ls = dobs[i].split("-")
        if len(ls) != 3:
            raise ValueError(f"Date {dobs[i]} not in ISO format.")
        if not 1 <= int(ls[1]) <= 12:
            raise ValueError(f"Month in date {dobs[i]} not valid.")
        if not 1 <= int(ls[2]) <= 31:
            raise ValueError(f"Day in date {dobs[i]} not valid.")

        yobs.append(ls[0])
        mobs.append(ls[1])
        tobs.append(ls[2])

    return np.array(yobs, dtype=np.int32), np.array(mobs, dtype=np.int32), np.array(tobs, dtype=np.int32)


def convert_to_bool(val):
    """
    Convert various input types to boolean.

    Handles conversion from strings, numbers, booleans, and NaN values.
    Excel may read booleans as strings ("True"/"False") or numbers (1/0),
    so this function provides robust conversion.

    Parameters
    ----------
    val : any
        Value to convert to boolean. Can be:
        - bool: returned as-is
        - str: "True", "False", "1", "0", "yes", "no", etc.
        - numeric: 1/0 or other numeric values
        - None/NaN: defaults to True

    Returns
    -------
    bool
        Boolean value. NaN/None and unknown values default to True.
    """
    import pandas as pd

    if pd.isna(val) or val is None:
        return True  # Default to True for NaN/None
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        # Handle string representations
        val_lower = val.lower().strip()
        if val_lower in ("true", "1", "yes", "y"):
            return True
        elif val_lower in ("false", "0", "no", "n"):
            return False
        else:
            # Unknown string, default to True
            return True
    # Handle numeric values (1/0)
    try:
        num_val = float(val)
        return bool(num_val) if num_val != 0 else False
    except (ValueError, TypeError):
        # Can't convert, default to True
        return True
