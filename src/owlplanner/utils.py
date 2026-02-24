"""
Utility functions for data formatting and manipulation.

This module provides helper functions for formatting currency, percentages,
and other data transformations used throughout the retirement planner.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

######################################################################
import numpy as np
import pandas as pd


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
        fac = 1_000_000
    else:
        raise ValueError(f"Unknown units {units}.")

    return fac


def get_numeric_option(options, key, default, *, min_value=None) -> float:
    value = options.get(key, default)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} {value} is not a number.")
    if min_value is not None and value < min_value:
        raise ValueError(f"{key} must be >= {min_value}.")
    return float(value)


def get_numeric_list_option(options, key, min_length, *, min_value=None) -> list[float]:
    """
    Get and validate a list of numeric values from options.

    Args:
        options: Options dictionary (caller must ensure key is present).
        key: Key to look up.
        min_length: Minimum required length of the list.
        min_value: Optional minimum value for each element (e.g. 0 for non-negative).

    Returns:
        List of floats. None and empty string elements become 0.

    Raises:
        ValueError: If value is not a list/tuple, too short, or contains non-numeric elements.
    """
    value = options[key]
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            f"{key} must be a list or tuple, got {type(value).__name__}."
        )
    if len(value) < min_length:
        raise ValueError(
            f"{key} must have at least {min_length} elements, got {len(value)}."
        )

    result = []
    for i, val in enumerate(value):
        if val is None or val == "":
            result.append(0.0)
        else:
            if not isinstance(val, (int, float)):
                raise ValueError(f"{key}[{i}] {val!r} is not a number.")
            f = float(val)
            if min_value is not None and f < min_value:
                raise ValueError(
                    f"{key}[{i}] must be >= {min_value}, got {f}."
                )
            result.append(f)
    return result


def get_monetary_option(options, key, default, *, min_value=None) -> float:
    """Like get_numeric_option but scales the result by the 'units' entry in options."""
    units = getUnits(options.get("units", "k"))
    return units * get_numeric_option(options, key, default, min_value=min_value)


def get_monetary_list_option(options, key, min_length, *, min_value=None) -> list[float]:
    """Like get_numeric_list_option but scales every element by the 'units' entry in options."""
    units = getUnits(options.get("units", "k"))
    return [units * v for v in get_numeric_list_option(options, key, min_length, min_value=min_value)]


# Next two functions could be a one-line lambda functions.
# e.g., krond = lambda a, b: 1 if a == b else 0
def krond(a, b) -> int:
    """
    Kronecker integer delta function.
    """
    return 1 if a == b else 0


def heaviside(x) -> int:
    """
    Heaviside step function.
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


def is_row_active(row):
    """
    Check if a DataFrame row should be processed based on 'active' column.

    This function handles the common pattern of checking whether a row in a DataFrame
    should be processed based on its 'active' column value. The logic is:
    - If 'active' column doesn't exist, the row is considered active (default behavior)
    - If 'active' value is NaN or None, the row is considered active (default behavior)
    - If 'active' value is explicitly False (or falsy), the row is considered inactive
    - Otherwise (True or truthy), the row is considered active

    Parameters
    ----------
    row : pd.Series
        A pandas Series representing a row from a DataFrame. The row should have
        an 'active' column (or index entry) if the active/inactive status is to be checked.

    Returns
    -------
    bool
        True if the row should be processed (is active), False if it should be skipped (is inactive).
    """
    if "active" not in row.index:
        return True  # Default to active if column doesn't exist
    active_value = row["active"]
    if pd.isna(active_value) or active_value is None:
        return True  # NaN/None means active
    return bool(active_value)


def is_dataframe_empty(df):
    """
    Check if a DataFrame is None or empty.

    This function consolidates the common pattern of checking
    `df is None or df.empty` throughout the codebase.

    Parameters
    ----------
    df : pd.DataFrame or None
        The DataFrame to check. Can be None or an empty DataFrame.

    Returns
    -------
    bool
        True if df is None or empty, False otherwise.
    """
    return df is None or df.empty


def ensure_dataframe(df, default_empty=None):
    """
    Ensure DataFrame is not None or empty, return default if needed.

    This function checks if a DataFrame is None or empty and returns a default
    value if so. This consolidates the common pattern of checking
    `df is None or df.empty` throughout the codebase.

    Parameters
    ----------
    df : pd.DataFrame or None
        The DataFrame to check. Can be None or an empty DataFrame.
    default_empty : any, optional
        The value to return if df is None or empty. Default is None.
        Common values are 0.0, np.zeros(N_n), or a default DataFrame.

    Returns
    -------
    any
        Returns default_empty if df is None or empty, otherwise returns df.
    """
    if is_dataframe_empty(df):
        return default_empty
    return df


def get_empty_array_or_value(N_n, default_value=0.0):
    """
    Return empty array or single value based on context.

    This helper function returns either a numpy array of zeros with length N_n
    if N_n is provided, or a single default value if N_n is None.

    Parameters
    ----------
    N_n : int or None
        Length of the array to create. If None, returns default_value instead.
    default_value : float, optional
        Default value to return if N_n is None. Default is 0.0.

    Returns
    -------
    np.ndarray or float
        Returns np.zeros(N_n) if N_n is not None, otherwise returns default_value.
    """
    if N_n is not None:
        return np.zeros(N_n)
    return default_value


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
    # Check for None first (before pd.isna which can fail on some types)
    if val is None:
        return True  # Default to True for None

    # Check for NaN, but handle cases where pd.isna might fail (e.g., empty lists)
    try:
        if pd.isna(val):
            return True  # Default to True for NaN
    except (ValueError, TypeError):
        # pd.isna can raise ValueError for empty arrays/lists
        # or TypeError for unhashable types - treat as non-NaN and continue
        pass
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
